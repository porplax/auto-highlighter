import datetime
import struct
import subprocess
import tempfile
import wave
import shlex

import cv2
import numpy as np
from PIL import Image
from rich.progress import Progress

from . import console, log


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
        p = subprocess.Popen(shlex.split(f'ffmpeg -i \"{self.video_path}\" -ss {second - self.start_point} -to {second + self.end_point} -c copy \"{self.compile_output}/{second}-({where}).mp4\"'),
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