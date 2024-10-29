import librosa
import datetime
import subprocess
import numpy as np
import time
import json
import os

from rich.progress import Progress
from rich.panel import Panel

from loguru import logger
from sklearn import linear_model

from . import processor, common, dataset, console

class AudioAnalysisProgress(Progress):
    def get_renderables(self):
        yield Panel.fit(self.make_tasks_table(self.tasks))

class AudioAnalysis:
    def __init__(self, video_path: str, audio_path: str, output_path: str, decibel_threshold=-5.0):
        self.video_path = video_path
        self.audio_path = audio_path
        self.output_path = output_path
        self.decibel_threshold = decibel_threshold
        
        self.start_point = 20
        self.end_point = 20
        
        # internal use
        self._processor = processor.AudioProcessor(audio_path)
        self._captured_result = {}
        self._recent = np.array([])
        self._subprocesses = []
    
    def _already_captured(self, pos: int):
        if not any(previous in self._recent for previous in range(pos - self.start_point, pos + self.end_point)):
            self._recent = np.append(self._recent, pos)
            return False
        return True
    
    def _add_highlight(self, position: int, decibel: float):
        highlight = common.HighlightedMoment(position=str(datetime.timedelta(seconds=position)), decibel=decibel)
        self._captured_result[position] = highlight
    
    def analyze_as_machine_learning(self):
        data = iter(self._processor.amp_iter())
        
        active_dataset = dataset.AudioDataSet(r'C:\Users\sayne\Programming\auto-highlighter-py\dataset\active', 1.0)
        passive_dataset = dataset.AudioDataSet(r'C:\Users\sayne\Programming\auto-highlighter-py\dataset\passive', 0.0)
        
        combined_dataset_samples, combined_dataset_labels = np.concatenate((active_dataset.samples, passive_dataset.samples)), np.concatenate((active_dataset.labels, passive_dataset.labels))
        
        logr = linear_model.LogisticRegression()
        logr.fit(combined_dataset_samples, combined_dataset_labels)
        
        stream = np.array([])
        
        for point in data:
            frame = point[0]
            position = point[1]
            
            stream = np.concatenate((stream, frame))            
            
            if stream.size >= self._processor.sample_rate * 10:
                logger.debug(f'stream size: {stream.size}\nstream: {stream}')
                stream_audio = np.mean(librosa.feature.mfcc(y=stream, sr=self._processor.sample_rate).reshape(-1, 1))
                logger.debug(logr.predict(stream_audio.reshape(-1, 1)).reshape(-1, 1))
                stream = np.array([])
        exit(1)
    
    def analyze_as_decibel(self):
        data = iter(self._processor.decibel_iter())
        
        t0 = time.time()
        with AudioAnalysisProgress(console=console, transient=True, refresh_per_second=60) as progress:
            task = progress.add_task('[dim]analyzing audio...', total=self._processor.duration)
            
            for point in data:
                decibel_array = point[0]
                position = point[1]
                
                max_decibel = np.max(decibel_array)
                
                if max_decibel >= self.decibel_threshold:
                    if not self._already_captured(int(position)):
                        self._add_highlight(int(position), max_decibel)
                        progress.update(task, description=f'[dim]captured[/] [yellow bold]{len(self._captured_result)}[/] [dim]highlights so far ...')
                
                progress.update(task, advance=1.0)
            progress.update(task, completed=True)
            progress.remove_task(task)
        t1 = time.time()
        logger.info(f'analysis completed in {t1 - t0}s')
            
    def export(self):
        filename = os.path.join(self.output_path, 'index.json')
        with open(filename, 'w') as f:
            json.dump(self._captured_result, f, indent=4, default=common.json_encoder)
        logger.info(f'exported to {filename}')
        
    def generate_all_highlights(self):
        highlights = self._captured_result.keys()
        
        for h in highlights:
            self.generate_from_highlight(h)
        
        while self._subprocesses:
            for p in self._subprocesses:
                if p.poll() is not None:
                    self._subprocesses.remove(p)
                    break
    
    def generate_from_highlight(self, position):
        highlight = self._captured_result[position]
        point = str(highlight.position).replace(':', ' ')
        
        start = int(position - self.start_point)
        end = int(position + self.end_point)
        
        output = os.path.join(self.output_path, f'{common.unique_id()} - {point}.mp4')
        
        if start < 0:
            start = 0
        
        if end > self._processor.duration:
            end = self._processor.duration
        
        # the ffmpeg module was buggin', so i had to resort to subprocess 😭
        # todo: find a way to use ffmpeg module instead of subprocess 
        p = subprocess.Popen(f'ffmpeg -i \"{self.video_path}\" -ss {start} -to {end} -c copy \"{output}\"')
        self._subprocesses.append(p)
        