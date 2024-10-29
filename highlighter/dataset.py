import tempfile
import glob
import librosa
import numpy as np

from loguru import logger

from . import processor


class AudioDataSet:
    def __init__(self, directory: str, label: str) -> None:
        self.directory = directory
        self.files = glob.glob(f'{directory}/*.mp4')
        
        self.samples = []
        self.labels = np.array([])
        
        logger.info(f'found {len(self.files)} files in {directory}')
        
        # create a temp directory to store audio files.
        temp_dir = tempfile.TemporaryDirectory()
        for file in self.files:
            audio = processor.AudioProcessor(processor.extract_audio_from_video(file, temp_dir.name))
            self.samples.append(np.mean(librosa.feature.mfcc(y=audio.audio, sr=audio.sample_rate).reshape(-1,1)))
            self.labels = np.append(self.labels, label)
            
            logger.info(f'audio processed from {file}')
            logger.debug(f'samples: {len(self.samples)}, labels: {self.labels.size}')
        
        self.samples = np.asarray(self.samples).reshape(-1, 1)
        logger.debug(f'\n{self.samples}')
        
        temp_dir.cleanup()
    
    def __call__(self):
        return self.samples, self.labels