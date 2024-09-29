import os
import glob
import pathlib
import tempfile
import subprocess
import datetime
import json
import struct
import wave
import typer
import numpy as np
import click
import logging
import cv2
import atexit
import platform

from rich.progress import Progress
from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Confirm
from PIL import Image
from signal import *

TEMP_DIR = tempfile.TemporaryDirectory()
console = Console()
app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console, markup=True)]
)

log = logging.getLogger("highlighter")

def exit_handler(*args):
    try:
        # check if the temporary folder is empty. if so, shut up and just delete it.
        if os.listdir(TEMP_DIR.name):
            log.warning('attempting to delete temporary folder ...')
            TEMP_DIR.cleanup()
            log.info('successful ...')
        else:
            TEMP_DIR.cleanup()
    except PermissionError as permError:
        log.error(f"i couldn't delete {TEMP_DIR.name} because of permissions! ({permError})\n"
                  f"it is recommended that you delete it manually.")
    except Exception as e:
        # so usually if the program couldn't delete the temporary folder; it is because of permissions.
        # but if it was something else this can be a major issue.
        # in testing, the highlighter would take up ~30.0GB of data and Windows refused to clean it up automatically.
        # so this is here! tysm windows! :D (i fucking hate windows)
        if platform.system() == 'Windows':
            console.print(f"[blink reverse]ERROR.[/] - couldn't delete the temporary folder. ({e})\n"
                          "this takes up [bold]A LOT[/] of disk space! on windows, this to be done manually.\n"
                          f"go to \"C:/Users/{os.getlogin()}/AppData/Local/Temp\" and delete it's contents.\n"
                          "close all applications that is currently using it.\n"
                          f"or you can instead just delete the temporary folder: \"{TEMP_DIR.name}\"")
        else:
            console.print(f"[blink reverse]ERROR.[/] - couldn't delete the temporary folder. ({e})\n"
                          f"this takes up [bold]A LOT[/] of disk space! this is handled automatically in most cases.\n"
                          "but if for whatever reason it doesn't clear up, you have to do so manually.\n"
                          f"find your system's temporary folder and delete it's contents.\n"
                          "close all applications that is currently using it.\n"
                          f"or you can instead just delete the temporary folder: \"{TEMP_DIR.name}\"")

atexit.register(exit_handler)

for sig in (SIGABRT, SIGFPE,  SIGTERM):
    signal(sig, exit_handler)

class VideoAnalysis:
    def __init__(self,
                 filename: str,
                 target_brightness: int,
                 compile_output: str,
                 start_point, end_point,
                 jit, **kwargs):
        self.filename = filename
        self.target_brightness = target_brightness
        self.compile_output = compile_output
        self.start_point = start_point
        self.end_point = end_point
        self.jit = jit

        self.prioritize_speed = None
        if 'prioritize_speed' in kwargs.keys():
            self.prioritize_speed = kwargs['prioritize_speed']

        self.maximum_depth = None
        if 'maximum_depth' in kwargs.keys():
            if kwargs['maximum_depth'] != 0:
                self.maximum_depth = kwargs['maximum_depth']

        if self.jit:
            path = pathlib.Path(compile_output)
            if not path.exists():
                path.mkdir()

            if os.listdir(compile_output):
                deletion = Confirm.ask(
                    f'[bold]"{compile_output}"[/][red italic] is not empty![/]\ndelete contents of {compile_output}?> ')
                if deletion:
                    files = glob.glob(compile_output + '/*')
                    for f in files:
                        os.remove(f)

        self.vidcap = cv2.VideoCapture(filename)

    def analyze(self):
        result = {}
        captured = []

        success, image = self.vidcap.read()
        frame_count = 0

        length = int(self.vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = int(self.vidcap.get(cv2.CAP_PROP_FPS))
        second = 0
        with Progress() as progress:
            duration_task = progress.add_task('[dim]processing video ...', total=int(length))
            while success:
                if frame_count % fps == 0:
                    # todo: counting seconds this way is not accurate. using opencv's way created errors, so i'll look into fixing this in the future.
                    # this will do for now.
                    second += 1
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    image_pil = Image.fromarray(image)
                    image_reduced = image_pil.reduce(100) # this is reduced to improve speed.
                    image_array = np.asarray(image_reduced)

                    average_r = []
                    average_g = []
                    average_b = []
                    for row in image_array:
                        # todo: this is EXTREMELY inefficient! please find another method soon.
                        for color in row:
                            r, g, b = color[0], color[1], color[2]
                            average_r.append(r)
                            average_g.append(g)
                            average_b.append(b)

                    # get average of all RGB values in the array.
                    r = np.mean(average_r)
                    g = np.mean(average_g)
                    b = np.mean(average_b)

                    # todo: not really important but this calculation is expensive.
                    # maybe add an option for the user to prioritize speed over accuracy.
                    luminance = np.sqrt((0.299 * r**2) + (0.587 * g**2) + (0.114 * b**2))
                    if luminance >= self.target_brightness:
                        if not self.maximum_depth is None:
                            if len(list(result.keys())) == self.maximum_depth:
                                log.warning('max amount of highlights reached.')
                                progress.update(duration_task, completed=True)
                                self.wave_data.close()
                                return result
                        if not self.jit:
                            if any(previous in captured for previous in range(second-self.start_point, second)):
                                # avoid highlighting moments that are too close to each other.
                                captured.append(second)
                                progress.update(duration_task,
                                                description=f'[bold red]redundancy found at [/][green]{datetime.timedelta(seconds=second)}[/] ([italic]still at[/] [bold yellow]{len(list(result.keys()))}[/]) [dim]skipping ...')
                            else:
                                captured.append(second)
                                result[second] = {
                                    'time': f'{second}',
                                    'luminance': luminance
                                }
                        else:
                            if any(previous in captured for previous in range(second-self.start_point, second)):
                                captured.append(second)
                                progress.update(duration_task,
                                                description=f'[bold red]redundancy found at [/][green]{datetime.timedelta(seconds=second)}[/] ([italic]still at[/] [bold yellow]{len(list(result.keys()))}[/]) [dim]skipping ...')
                            else:
                                captured.append(second)
                                result[second] = {
                                    'time': f'{second}',
                                    'luminance': luminance
                                }
                                p = subprocess.Popen(
                                    f'ffmpeg -i \"{self.filename}\" -ss {second - self.start_point} -to {second + self.end_point} -c copy {self.compile_output}/{second}-({str(datetime.timedelta(seconds=second)).replace(":", " ")}).mp4',
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
                                p.wait()
                                p.kill()
                                progress.update(duration_task, description=f'[bold yellow]{len(list(result.keys()))}[/] [dim]highlighted moments so far ...')

                success, image = self.vidcap.read()
                progress.update(duration_task, advance=1.0)
                frame_count += 1
        return result


class AudioAnalysis:
    def __init__(self,
                 filename: str,
                 target_decibel: float,
                 compile_output: str,
                 accuracy: int, start_point, end_point, **kwargs):
        self.video_path = ''
        self.filename = filename
        self.target_decibel = target_decibel
        self.compile_output = compile_output
        self.accuracy = accuracy
        self.start_point = start_point
        self.end_point = end_point

        self.maximum_depth = None
        if 'maximum_depth' in kwargs.keys():
            if kwargs['maximum_depth'] != 0:
                self.maximum_depth = kwargs['maximum_depth']

        if self.filename:
            self.wave_data = wave.open(filename, 'r')
            self.length = self.wave_data.getnframes() / self.wave_data.getframerate()

    def __repr__(self):
        return str(self.wave_data.getparams())

    def _read(self):
        frames = self.wave_data.readframes(self.wave_data.getframerate())
        unpacked = struct.unpack(f'<{int(len(frames) / self.wave_data.getnchannels())}h', frames)
        return unpacked

    def _split(self, buffer):
        return np.array_split(np.array(buffer), self.accuracy)

    def convert_from_video(self, video_path):
        audio_out = TEMP_DIR.name + '/audio.wav'
        self.video_path = video_path

        p = subprocess.Popen(f'ffmpeg -i \"{video_path}\" -ab 160k -ac 2 -ar 44100 -vn {audio_out}',
                             shell=False)
        self.filename = audio_out
        p.wait()

        self.wave_data = wave.open(self.filename, 'r')
        self.length = self.wave_data.getnframes() / self.wave_data.getframerate()

    def analyze(self):
        result = {}
        captured = []

        with Progress() as progress:
            duration_task = progress.add_task('[dim]processing audio ...', total=int(self.length))
            for _i in range(0, int(self.length)):
                # read each second of the audio file, and split it for better accuracy.
                buffered = self._read()
                chunks = self._split(buffered)

                decibels = [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in chunks]

                decibels_iter = iter(decibels)
                for ms, db in enumerate(decibels_iter):
                    if db >= self.target_decibel:
                        if not self.maximum_depth is None:
                            if len(list(result.keys())) == self.maximum_depth:
                                log.warning('max amount of highlights reached.')
                                progress.update(duration_task, completed=True)
                                self.wave_data.close()
                                return result
                        if any(previous in captured for previous in range(_i-self.start_point, _i)):
                            # avoid highlighting moments that are too close to each other.
                            captured.append(_i)
                            progress.update(duration_task, description=f'[bold red]redundancy found at [/][green]{datetime.timedelta(seconds=_i)}[/] ([italic]still at[/] [bold yellow]{len(list(result.keys()))}[/]) [dim]skipping ...')
                        else:
                            point = datetime.timedelta(seconds=_i)
                            captured.append(_i)

                            result[_i] = {
                                'time': f"{point}",
                                'time_with_ms': f'{point}.{ms}',
                                'decibels': db
                            }
                            progress.update(duration_task, description=f'[yellow bold]{len(list(result.keys()))}[/] [dim]highlighted moments so far ...')

                progress.update(duration_task, advance=1.0)
        progress.update(duration_task, completed=True)
        self.wave_data.close()
        return result

    def get_ref(self):
        average_db_array = np.array([], dtype=np.float64)
        greatest_db = -0.0

        with Progress() as progress:
            duration_task = progress.add_task('[dim]getting reference dB ...', total=int(self.length))
            for _i in range(0, int(self.length)):
                buffered = self._read()
                chunks = self._split(buffered)

                decibels = [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in chunks]
                average = np.mean(decibels, dtype=np.float64)

                if average > greatest_db:
                    greatest_db = average

                average_db_array = np.append(average_db_array, average)
                progress.update(duration_task, advance=1.0)

        return average_db_array, greatest_db


class Compiler:
    def __init__(self, input, output, start_point, end_point):
        self.video_path = input
        self.compile_output = output
        self.start_point = start_point
        self.end_point = end_point

    def compile(self, result: dict):
        highlights_json = open(self.compile_output + '/highlights.json', 'x')
        highlights_json.write(json.dumps(result, indent=4))
        highlights_json.close()

        captured = []
        points = sorted(list(result.keys()))

        print(points)
        for key in points:
            time = int(key)
            captured.append(time)

            console.print(
                f'[dim]compiling[/] [bold]{result[key]["time"]}[/][dim] into video[/]\n' + ' ' * 4 + f'| to: [cyan italic]{self.compile_output}/{time}.mp4[/]')

            p = subprocess.Popen(
                f'ffmpeg -i \"{self.video_path}\" -ss {time - self.start_point} -to {time + self.end_point} -c copy \"{self.compile_output}/{time}-({result[key]["time"].replace(":", " ")}).mp4\"')
            p.wait()
            p.kill()


@app.callback()
def callback():
    pass


@click.command()
@click.option('--input', '-i',
              help='video file to process.',
              type=str, required=True)
@click.option('--output', '--output-path', '-o',
              help='path that will contain the highlighted clips from the video.',
              type=str, required=False, default='./highlights',
              show_default=True)
@click.option('--target', '--target-decibel',
              '--decibel', '-t', '-td', '-d',
              help='target decibel required to highlight a moment.',
              type=float, required=False, default=85.0,
              show_default=True)
@click.option('--before',
              help='how many seconds to capture before the detected highlight occurs.',
              type=int, required=False, default=20)
@click.option('--after',
              help='how many seconds to capture after the detected highlight occurs.',
              type=int, required=False, default=20)
@click.option('--accuracy', '-a',
              help='how accurate the highlighter is. (recommended to NOT mess with this)',
              type=int, required=False, default=1000)
@click.option('--max-highlights', '-m',
              help='stops highlighting if the amount of found highlights exceed this amount.',
              type=int, required=False, default=0)
@click.option('--compile/--skip-compile',
              help='whether or not i should create clips from detected moments.', default=True)
@click.option('--detect-with-video',
              help='instead of detecting with audio, detect with video based on brightness.',
              is_flag=True)
@click.option('--target-brightness',
              help='target brightness required to highlight a moment. (0-255)',
              type=int, required=False, default=125,
              show_default=True)
@click.option('--just-in-time-compilation', '-jit',
              help='instead of compiling after analysis, compile as it find highlights (only available with video detection)',
              is_flag=True)
def analyze(input, output, target, before, after, accuracy, compile, max_highlights, detect_with_video, target_brightness, just_in_time_compilation):
    """analyze VOD for any highlights."""

    # todo: may be better to detect video length and then determine if the set target dB will be a problem.
    if 60.0 > target > 50.0:
        log.warning(f'[red italic]target dB: {target} < 60.0 is probably [bold]too low[/] !!![/]\n'
                    '[red bold reverse]this might cause the highlighter to create too many clips and could eat up disk space![/]\n\n'
                    'if this is wanted, ignore this warning.\n'
                    "if you're unsure what this message means, you might want to set it higher\n"
                    "or find the video's reference dB with the [code]find-reference[/] command.\n\n"
                    "[italic]additionally, you can force the program to terminate if the amount of found highlights exceeds a certain amount.")
        confirm = Confirm.ask('continue?')
        if not confirm:
            exit(1)
    elif target < 50.0 and target != 0.0:
        log.warning(f'[red italic]target dB: {target} < 50.0 is [bold]extremely low[/] !!![/]\n'
                    '[red bold reverse blink]THIS WILL CAUSE THE HIGHLIGHTER TO CONSUME ASTRONOMICAL AMOUNTS OF DISK SPACE IF THE VIDEO IS LONG ENOUGH![/]\n\n'
                    'if this is wanted, ignore this warning.\n'
                    "if you're unsure what this message means, you might want to set it higher\n"
                    "or find the video's reference dB with the [code]find-reference[/] command.\n\n"
                    "[italic]additionally, you can force the program to terminate if the amount of found highlights exceeds a certain amount.")
        confirm = Confirm.ask('continue?')
        if not confirm:
            exit(1)
    elif target == 0.0:
        log.error(f'[red italic]target dB: {target} is [bold]way too low and invalid.[/]')
        exit(1)

    log.info(f'using [bold]"{input}"[/] as [cyan]input[/] ...')
    if compile:
        log.info(f'will compile to {output} ...')
    if not detect_with_video:
        log.info(f'minimum decibels to highlight a moment: {target}, [dim italic]with accuracy: {accuracy}[/]')

        log.info(f'converting [bold]"{input}"[/] to [purple].wav[/] file ...')
        analyzer = AudioAnalysis('', target, output, accuracy, before, after, maximum_depth=max_highlights)
        analyzer.convert_from_video(input)
        log.info(analyzer)
    else:
        log.info(f'minimum luminance to highlight a moment: {target_brightness}')
        analyzer = VideoAnalysis(input, target_brightness, output, before, after, just_in_time_compilation, maximum_depth=max_highlights)

    log.info('now analyzing for any moments ...')
    moments = analyzer.analyze()

    if compile and not just_in_time_compilation:
        path = pathlib.Path(output)

        if not path.exists():
            path.mkdir()


        if os.listdir(output):
            deletion = Confirm.ask(f'[bold]"{output}"[/][red italic] is not empty![/]\ndelete contents of {output}?')
            if deletion:
                files = glob.glob(output + '/*')
                for f in files:
                    os.remove(f)

        log.info(f'i am now compiling to {output}')
        compiler = Compiler(input, output, before, after)
        compiler.compile(moments)

    log.info('[green]finished![/]')


@click.command()
@click.option('--input', '-i',
              help='video file to process.', required=True)
@click.option('--accuracy', '-a',
              help='how accurate the highlighter is. (recommended to NOT mess with this)',
              type=int, required=False, default=1000)
def find_reference(input, accuracy):
    """find average decibel in video. [italic dim](if you're unsure what target decibel to aim for, use this)"""
    log.info(f'using [bold]"{input}"[/] as [cyan]input[/] ...')
    log.info(f'converting [bold]"{input}"[/] to [purple].wav[/] file ...')

    analyzer = AudioAnalysis('', 0.0, '', accuracy, 0, 0)
    analyzer.convert_from_video(input)
    log.info(analyzer)

    average, greatest = analyzer.get_ref()

    # https://stackoverflow.com/questions/49867345/how-to-deal-with-inf-values-when-computting-the-average-of-values-of-a-list-in-p
    log.info(f'[cyan]average dB:[/] {np.mean(average[np.isfinite(average)], dtype=np.float64)} ...')
    log.info(f'[blue]greatest dB:[/] {greatest} ...')

    console.rule(title='[dim]using this info[/]', align='left')
    console.print('it is recommended to have your [green]target dB[/] set close to that of the [blue]greatest dB[/].\n'
                  f'for example, start off at a [green]target dB[/] of {float(round(greatest) - 1)}. [dim](based on the [/][orange]greatest dB[/][dim] found)[/]\n'
                  "setting the [green]target dB[/] closer to the [blue]greatest dB[/] will give you better results.\n\n"
                  "[italic]however[/] setting your [green]target dB[/] too close to the [blue]greatest dB[/] will highlight less and less results.\n"
                  "setting it higher than your [blue]greatest dB[/] will give no results at all.\n\n"
                  "having it closer to your [cyan]average dB[/] will create more results.\n"
                  "and having it too close could potientially consume a lot of disk space.")
    console.rule()




app.rich_markup_mode = "rich"
typer_click_object = typer.main.get_command(app)
typer_click_object.add_command(analyze, "analyze")
typer_click_object.add_command(find_reference, "find-reference")

def cli():
    console.clear()
    typer_click_object()

if __name__ == '__main__':
    cli()

