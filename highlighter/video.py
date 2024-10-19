import datetime
import subprocess

import cv2
import numpy as np
from PIL import Image
from rich.progress import Progress

from . import log


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
