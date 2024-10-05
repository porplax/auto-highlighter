import json
import subprocess

from . import console


class Compiler:
    def __init__(self, video_input, output, start_point, end_point):
        self.video_path = video_input
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
