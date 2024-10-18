import atexit
import datetime
import logging
import os
import pathlib
import platform
import shlex
import struct
import subprocess
import tempfile
import wave
from signal import *

import click
import cv2
import numpy as np
import typer
from PIL import Image
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress

TEMP_DIR = tempfile.TemporaryDirectory()
console = Console()
app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console, markup=True)]
)

log = logging.getLogger("highlighter")


class VideoAnalysis:
    def __init__(self,
                 filename: str,
                 target_brightness: int,
                 compile_output: str,
                 start_point, end_point, **kwargs):
        self.filename = filename
        self.target_brightness = target_brightness
        self.compile_output = compile_output
        self.start_point = start_point
        self.end_point = end_point

        self.prioritize_speed = None
        if 'prioritize_speed' in kwargs.keys():
            self.prioritize_speed = kwargs['prioritize_speed']

        self.maximum_depth = None
        if 'maximum_depth' in kwargs.keys():
            if kwargs['maximum_depth'] != 0:
                self.maximum_depth = kwargs['maximum_depth']

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
            try:
                while success:
                    if frame_count % fps == 0:
                        # todo: counting seconds this way is not accurate. using opencv's way created errors, so i'll look into fixing this in the future.
                        # this will do for now.
                        second += 1
                        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        image_pil = Image.fromarray(image)
                        image_reduced = image_pil.reduce(100)  # this is reduced to improve speed.
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
                        luminance = np.sqrt((0.299 * r ** 2) + (0.587 * g ** 2) + (0.114 * b ** 2))

                        if not self.maximum_depth is None:
                            if len(list(result.keys())) == self.maximum_depth:
                                log.warning('max amount of highlights reached.')
                                progress.update(duration_task, completed=True)
                                return result

                        if luminance >= self.target_brightness:
                            if any(previous in captured for previous in range(second - self.start_point, second)):
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
                                progress.update(duration_task,
                                                description=f'[bold yellow]{len(list(result.keys()))}[/] [dim]highlighted moments so far ...')

                    success, image = self.vidcap.read()
                    progress.update(duration_task, advance=1.0)
                    frame_count += 1
            except KeyboardInterrupt:
                return result
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
        self.compile_output = compile_output.replace('\\', '/')
        self.accuracy = accuracy
        self.start_point = start_point
        self.end_point = end_point
        self.seek = 0
        self.temp_dir = tempfile.TemporaryDirectory()

        self.maximum_depth = None
        if 'maximum_depth' in kwargs.keys():
            if kwargs['maximum_depth'] != 0:
                self.maximum_depth = kwargs['maximum_depth']

        self.keywords = []
        if 'keywords' in kwargs.keys():
            self.keywords = list(kwargs['keywords'])

        if self.filename:
            self.wave_data = wave.open(filename, 'r')
            self.length = self.wave_data.getnframes() / self.wave_data.getframerate()

    def __repr__(self):
        return str(self.wave_data.getparams())

    def _read(self):
        frames = self.wave_data.readframes(self.wave_data.getframerate())
        unpacked = struct.unpack(f'<{int(len(frames) / self.wave_data.getnchannels())}h', frames)
        return frames, unpacked

    def _split(self, buffer):
        return np.array_split(np.array(buffer), self.accuracy)

    def _generate(self, second: int):
        where = str(datetime.timedelta(seconds=second)).replace(":", " ")
        p = subprocess.Popen(shlex.split(
            f'ffmpeg -i \"{self.video_path}\" -ss {second - self.start_point} -to {second + self.end_point} -c copy \"{self.compile_output}/{second}-({where}).mp4\"'),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT,
                             shell=False)
        p.wait()
        p.kill()

    def convert_from_video(self, video_path):
        """
        Converts a video to .wav format using ffmpeg,
        saves it to a temporary folder and opens it as wave file.

        Be careful of memory consumption. Close it when it is discarded.

        Returns
        -------------------
        `wave_data` - wave file object.

        :param video_path:
        :return:
        """
        video_path = str(video_path).replace('\\', '/')
        audio_out = str(self.temp_dir.name + '/audio.wav').replace('\\', '/')
        self.video_path = video_path
        p = subprocess.Popen(shlex.split(f'ffmpeg -i \"{video_path}\" -ab 160k -ac 2 -ar 44100 -vn {audio_out}'),
                             shell=False)
        self.filename = audio_out
        p.wait()
        p.kill()
        console.clear()

        self.wave_data = wave.open(self.filename, 'r')
        self.length = self.wave_data.getnframes() / self.wave_data.getframerate()
        return self.wave_data

    def capture(self):
        """
        A generator that captures a highlight.

        If a possible highlight was detected, it will return the second
        of where it happened in the video. Otherwise, it will return
        None.

        Upon finishing, it will raise a StopIteration exception.

        Returns
        -------------------
        `second` - time in video where the highlight occurred.
        """
        captured = []

        for _i in range(0, int(self.length)):
            buffered = self._read()
            chunks = self._split(buffered[1])

            # todo: not important, but this is expensive. could probably be less so.
            """
            decibels:

            The algorithm below converts 1000 chunks into a readable dB.
            But to do this, it first does a bunch of operations.

            Square it then, get the mean, get the square root, then log10 over each one.

            I'm leaving this comment here as I could possibly improve this in the future. :P
            """
            decibels = [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in chunks]
            decibels_iter = iter(decibels)

            for ms, db in enumerate(decibels_iter):
                if db >= self.target_decibel:
                    if any(previous in captured for previous in range(_i - self.start_point, _i)):
                        # avoid highlighting moments that are too close to each other.
                        captured.append(_i)
                        yield -1
                    else:
                        captured.append(_i)
                        yield _i
            yield -1
            self.seek = _i

        self.wave_data.close()

    # todo: the below function is obsolete and taking up space, instead use the above function and integrate into `__init__.py`
    def analyze_cli(self):
        result = {}
        captured = []

        with Progress(console=console, refresh_per_second=15) as progress:
            duration_task = progress.add_task('[dim]processing audio ...', total=int(self.length))
            for _i in range(0, int(self.length)):
                # read each second of the audio file, and split it for better accuracy.
                buffered = self._read()
                chunks = self._split(buffered[1])

                decibels = [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in chunks]

                decibels_iter = iter(decibels)
                for ms, db in enumerate(decibels_iter):
                    if not self.maximum_depth is None:
                        if len(list(result.keys())) == self.maximum_depth:
                            log.warning('max amount of highlights reached.')
                            progress.update(duration_task, completed=True)
                            self.wave_data.close()
                            return result

                    if db >= self.target_decibel:
                        if any(previous in captured for previous in range(_i - self.start_point, _i)):
                            # avoid highlighting moments that are too close to each other.
                            captured.append(_i)
                            progress.update(duration_task,
                                            description=f'[italic dim]skipping redundant highlight at [/][green]{datetime.timedelta(seconds=_i)}[/] ([bold yellow]{len(list(result.keys()))}[/] [dim]highlights so far[/])')
                        else:
                            point = datetime.timedelta(seconds=_i)
                            if not _i in captured:
                                self._generate(_i)

                            captured.append(_i)

                            result[_i] = {
                                'time': f"{point}",
                                'time_with_ms': f'{point}.{ms}',
                                'decibels': db
                            }

                            progress.update(duration_task,
                                            description=f'[yellow bold]{len(list(result.keys()))}[/] [dim]highlighted moments so far ...')

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
                chunks = self._split(buffered[1])

                decibels = [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in chunks]
                average = np.mean(decibels, dtype=np.float64)

                for db in decibels:
                    if db > greatest_db:
                        greatest_db = db

                average_db_array = np.append(average_db_array, average)
                progress.update(duration_task, advance=1.0)

        return average_db_array, greatest_db


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
@click.option('--detect-with-video',
              help='instead of detecting with audio, detect with video based on brightness.',
              is_flag=True)
@click.option('--target-brightness',
              help='target brightness required to highlight a moment. (0-255)',
              type=int, required=False, default=125,
              show_default=True)
def analyze(input, output, target, before, after, accuracy, max_highlights, detect_with_video,
            target_brightness):
    """analyze VOD for any highlights."""
    path = pathlib.Path(output)

    if not path.exists():
        path.mkdir()

    if os.listdir(output):
        log.error(f'[bold]"{output}"[/][red italic] is not empty![/]')
        exit(1)

    log.info(f'i am compiling to {output}')
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
        analyzer = VideoAnalysis(input, target_brightness, output, before, after,
                                          maximum_depth=max_highlights)

    log.info('now analyzing for any moments ...')
    analyzer.analyze_cli()

    log.info('[green]finished![/]')


"""@click.command()
def watch():
    driver = webdriver.Firefox()
    driver.get('https://www.twitch.tv/nickmercs') # watching nickmercs lol
    c = 0
    while True:
        files = []
        for idx, request in enumerate(driver.requests):
            if request.response:
                print(request.url)
                if request.url.endswith('m3u8'):
                    r = requests.get(request.url)
                    name = random.randint(1000, 9999999)
                    filename = TEMP_DIR.name + f'/{name}.m3u8'
                    files.append(filename)
                    with open(filename, 'xb') as f:
                        f.write(r.content)
                elif request.url.endswith('ts'):
                    r = requests.get(request.url)
                    name = random.randint(1000, 9999999)
                    filename = TEMP_DIR.name + f'/{name}.ts'
                    files.append(filename)
                    with open(filename, 'xb') as f:
                        f.write(r.content)
        cmd = '|'.join(files)
        with open('out.bat', 'w+') as f:
            f.write(f"ffmpeg -protocol_whitelist concat,file,http,https,tcp,tls,crypto -y -i \"concat:{cmd.replace(' ', '')}\" -c copy ./segments/chunk{c}.mp4")
        subprocess.Popen(
            "out.bat"
            , shell=True)
        c += 1"""

@click.command()
@click.option('--input', '-i',
              help='video file to process.', required=True)
@click.option('--accuracy', '-a',
              help='how accurate the highlighter is. (recommended to NOT mess with this)',
              type=int, required=False, default=1000)
def find_reference(input, accuracy):
    """find average decibel in video. [italic dim](if you're unsure what target decibel to aim for, use this)"""
    console.clear()
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
    typer_click_object()

if __name__ == '__main__':
    cli()

