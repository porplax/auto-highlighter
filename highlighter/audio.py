import datetime
import math
import shlex
import struct
import subprocess
import tempfile
import threading
import wave

import numpy as np
from rich.progress import Progress

from . import log, console


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

    def _get_decibel_from_chunks(self, chunks):
        decibels = []
        for chunk in chunks:
            result = 20 * np.log10(math.sqrt(np.mean(chunk ** 2)))
            if not result == float('-inf') and result > 0:
                decibels.append(result)
        return decibels

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

    def analyze(self):
        result = {}
        captured = []

        try:
            with Progress(console=console, refresh_per_second=4) as progress:
                duration_task = progress.add_task('[dim]processing audio ...', total=int(self.length))
                for _i in range(0, int(self.length)):
                    # read each second of the audio file, and split it for better accuracy.
                    buffered = self._read()
                    chunks = self._split(buffered[1])
                    decibels = self._get_decibel_from_chunks(chunks)

                    if not max(decibels, default=0) >= self.target_decibel:
                        progress.update(duration_task, advance=1.0)
                        continue

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
                                break
                            else:
                                point = datetime.timedelta(seconds=_i)
                                if not _i in captured:
                                    t1 = threading.Thread(target=self._generate, args=(_i,))
                                    t1.start()

                                captured.append(_i)

                                result[_i] = {
                                    'time': f"{point}",
                                    'time_with_ms': f'{point}.{ms}',
                                    'decibels': db
                                }

                                progress.update(duration_task,
                                                description=f'[yellow bold]{len(list(result.keys()))}[/] [dim]highlighted moments so far ...')
                                break
                    progress.update(duration_task, advance=1.0)
        except:
            self.wave_data.close()
            return result
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
