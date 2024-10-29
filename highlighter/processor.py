import os
import librosa
import numpy as np
import ffmpeg

from loguru import logger

BITRATE = '160k'
SAMPLING_RATE = 48000
CHANNELS = 1 # 1 = mono, 2 = stereo
SPLIT_FRAMES = 1000

def extract_audio_from_video(video_path: str, output_path: str):
    """Convert a video file to an audio file.

    Args:
        video_path (str): path to the video file
        output_path (str): path to the output audio file
    """
    file_base = os.path.splitext(os.path.basename(video_path))[0].replace(':', ' ')
    audio_path = os.path.join(output_path, f'{file_base}.wav')
    
    (
        ffmpeg
        .input(video_path)
        .output(audio_path, **{'ab': BITRATE, 'ar': SAMPLING_RATE, 'ac': CHANNELS})
        .run()
    )
    
    logger.info(f'audio extracted from {video_path} to {audio_path}')
    
    return audio_path
    
    
class AudioProcessor:
    def __init__(self, audio_path):
        self.audio, self.sample_rate = librosa.load(audio_path, mono=True, sr=None)
        self.duration = librosa.get_duration(y=self.audio, sr=self.sample_rate)
        
        # internal use
        self._pos = 0
        
        logger.info(f'audio loaded from {audio_path} with duration {self.duration}s')
        logger.debug(f'frames: {self.audio.size}, sample rate: {self.sample_rate}')
    
    def _seek(self, pos):
        self._pos += pos
    
    def _read(self):
        """read a second of audio data.

        Returns:
            np.array: second of audio data
        """
        frames = self.audio[self._pos:self._pos + self.sample_rate]
        self._seek(self.sample_rate)
        return frames
    
    def _split(self, f):
        """split an array into multiple arrays.

        Args:
            f (np.array): array to split.

        Returns:
            np.array[np.array]: array of split arrays.
        """
        return np.array_split(f, SPLIT_FRAMES)
    
    def _into_decibels(self, c):
        """convert an array of audio data into decibels.

        Args:
            c (np.array): array of audio data.

        Returns:
            np.array: array of decibels.
        """
        return [20 * np.log10(np.sqrt(np.mean(chunk ** 2))) for chunk in c]
    
    def amp_iter(self):
        self._pos = 0
        while True:
            frames = self._read()
            
            if frames.size == 0:
                break
            
            current = 0
            
            try:
                current = self._pos / self.sample_rate
                current = current - 1
            except ZeroDivisionError:
                pass
            
            yield frames, current
    
    def decibel_iter(self):
        self._pos = 0
        while True:
            frames = self._read()
            
            if frames.size == 0:
                break
            
            chunks = self._split(frames)
            decibels = self._into_decibels(chunks)
            current = 0
            
            try:
                current = self._pos / self.sample_rate
                current = current - 1
            except ZeroDivisionError:
                pass
            
            yield decibels, current