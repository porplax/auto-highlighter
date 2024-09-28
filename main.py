import tempfile
import sys
import pathlib
import subprocess
import datetime
import json
import struct
import wave
import numpy as np

from rich.progress import Progress
from rich.console import Console

console = Console()

# class to parse all arguments.
class ArgumentParser:
    def __init__(self, args: list):
        args.pop(0)
        self.args = args
        self.current = None
        self.index = 0

        # no arguments were provided, so terminate the program.
        if not self.args:
            console.print("no [bold italic]arguments[/] were provided!")
            sys.exit(1)

        self.current = self.args[self.index]
        self.program = {
            'video': '',
            'target decibel': 85.0
        }
        self._run()

    def _run(self):
        match self.current:
            case '-t' | '--target-decibel':
                if not self._seek():
                    console.print('[red]no target decibel was provided.[/]')
                    sys.exit(1)

                target_decibel = self._next()

                if not isinstance(target_decibel, float):
                    console.print('[red]target decibel is not a float![/]')
                    sys.exit(1)

                self.program['target decibel'] = target_decibel
                console.print(f'[bold]using [cyan]{target_decibel}[/cyan] as target decibel ...[/bold]')
            case '-i' | '--input' | '-v' | '--video':
                # the user did not provide us the video path!
                if not self._seek():
                    console.print('[red]no video was provided.[/]')
                    sys.exit(1)

                video_path = self._next()

                # the video is not a string.
                if not isinstance(video_path, str):
                    console.print('[red]the path is not a string.[/]')
                    sys.exit(1)

                # video does not exist.
                if not pathlib.Path(video_path).exists():
                    console.print(f'[bold italic]{video_path}[/][red] does not exist as a file.[/]')
                    sys.exit(1)

                self.program['video'] = video_path
                console.print(f'[bold]using [cyan]{pathlib.Path(video_path).name}[/cyan] as input ...[/bold]')
            case '-h' | '--help':
                # todo: create help message.
                pass
            case _:
                console.print(f'[bold italic]{self.current}[/][red] is not recognized![/]')
                sys.exit(1)

    def _seek(self):
        if self.index+1 > len(self.args)-1:
            return False
        return self.args[self.index+1]

    def _next(self):
        if self.index > len(self.args)-1:
            return
        self.index += 1
        self.current = self.args[self.index]
        return self.args[self.index]


arguments = ArgumentParser(sys.argv)

temporary_path = tempfile.TemporaryDirectory()
audio_out = temporary_path.name + '/audio.wav'

p = subprocess.Popen(f'ffmpeg -i \"{arguments.program["video"]}\" -ab 160k -ac 2 -ar 44100 -vn {audio_out}',
                     shell=False)
p.wait()
p.kill()

class AudioAnalysis:
    def __init__(self,
                 filename: str,
                 target: float):
        self.filename = filename
        self.target = target

        self.wave_data = wave.open(filename, 'r')
        self.length = self.wave_data.getnframes() / self.wave_data.getframerate()

    def __repr__(self):
        return str(self.wave_data.getparams())

    def _read(self):
        frames = self.wave_data.readframes(self.wave_data.getframerate())
        unpacked = struct.unpack(f'<{int(len(frames) / self.wave_data.getnchannels())}h', frames)
        return unpacked

    def _split_into_milliseconds(self, buffer):
        return np.array_split(np.array(buffer), 1000)

    def analyze(self):
        result = {}
        captured = []

        with Progress() as progress:
            duration_task = progress.add_task('[dim]processing audio ...', total=int(self.length))
            for _i in range(0, int(self.length)):
                buffered = self._read()
                chunks = self._split_into_milliseconds(buffered)

                decibels = [20 * np.log10(np.sqrt(np.mean(chunk**2))) for chunk in chunks]

                decibels_iter = iter(decibels)
                for ms, db in enumerate(decibels_iter):
                    if db >= self.target:
                        if not _i in captured:
                            if _i - 1 in captured:
                                idx = captured.index(_i - 1)
                                del captured[idx]

                            point = datetime.timedelta(seconds=_i)
                            captured.append(_i)

                            result[_i] = {
                                'time': f"{point}",
                                'time_with_ms': f'{point}.{ms}',
                                'decibels': db
                            }

                progress.update(duration_task, advance=1.0)

        self.wave_data.close()
        return result

    def compile(self, result: dict):
        highlights_path = './highlights'

        highlights_json = open(highlights_path + '/highlights.json', 'x')
        highlights_json.write(json.dumps(result, indent=4))
        highlights_json.close()

        original_file = arguments.program['video']

        captured = []
        points = sorted(list(result.keys()))

        # note: this is the dumbest shit.
        for second in points:
            for position, identical in enumerate(points):
                if second <= identical < second+20:
                    points.remove(identical)

        for second in points:
            for position, identical in enumerate(points):
                if second <= identical < second+20:
                    points.remove(identical)

        print(points)
        for key in points:
            time = int(key)
            captured.append(time)

            if time-1 in captured:
                console.print(f'[red]redunant clipping at {time}, skipping ...')
                continue

            console.print(f'[dim]compiling[/] [bold]{result[key]["time"]}[/][dim] into video[/]\n' + ' '*4 + f'| to: [cyan italic]{highlights_path}/{time}.mp4[/]')

            start_point = -10
            end_point = 20

            lengthing = 1
            if time + lengthing in points:
                console.print(f'[yellow]could possibly lengthen[/] [bold]{time}.mp3 ...[/]')
                possible = time+1
                captured.append(possible)
                while possible in points:
                    end_point += 1
                    possible += 1
                    captured.append(possible)

            p = subprocess.Popen(
                f'ffmpeg -i \"{original_file}\" -ss {time+start_point} -to {time+end_point} {highlights_path}/{time}.mp4')
            p.wait()
            p.kill()

analyzer = AudioAnalysis(audio_out, arguments.program['target decibel'])
console.print(analyzer)

highlighted_moments = analyzer.analyze()
console.print_json(json.dumps(highlighted_moments),
                   indent=4, highlight=True)
analyzer.compile(highlighted_moments)

temporary_path.cleanup()