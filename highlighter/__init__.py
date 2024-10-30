import typer
import tempfile
import pathlib
import glob

from rich.console import Console
from rich.prompt import Prompt

from loguru import logger
from typing_extensions import Annotated

console = Console()

__all__ = ['processor', 'common', 'analyzer']
from . import processor, common, analyzer

DEFAULT_TEMP_DIR = tempfile.TemporaryDirectory()

app = typer.Typer()

@app.command()
def analyze(
    path_to_video: Annotated[str, typer.Argument(help='path to the video file to analyze.'),], 
    output_directory: Annotated[str, typer.Argument(help='path to the output directory.'),], 
    decibel_threshold: float):
    
    video_as_path = pathlib.Path(path_to_video)
    output_as_path = pathlib.Path(output_directory)
    
    if not video_as_path.exists():
        logger.error(f'File does not exist: {path_to_video}')
        
        files_in_video_path = glob.glob(f'{video_as_path.parent}/*')
        related_file = None
        
        
        for file in files_in_video_path:
            if common.similarity(file, path_to_video) > 0.90:
                logger.info(f'Found similar file: {file}')
                confirm = Prompt.ask('Did you mean this file? ([italic]skip if this is a mistake.[/])', choices=['yes', 'no', 'skip'])
                if confirm == 'yes':
                    related_file = file
                    break
                elif confirm == 'skip':
                    break
                else:
                    logger.critical('no related file found. exiting...')
                    exit(1)
                    
        if related_file:
            logger.info(f'Using related file: {related_file}')
            path_to_video = related_file
            
    if not output_as_path.exists():
        logger.critical('output directory does not exist.')
        exit()
    
    audio = processor.extract_audio_from_video(path_to_video, DEFAULT_TEMP_DIR.name)
    _a = analyzer.AudioAnalysis(path_to_video, audio, output_directory, decibel_threshold=decibel_threshold)
    _a.crest_ceiling_algorithm()
    _a.export()
    _a.generate_all_highlights()

def cli():
    app()
    
if __name__ == "__main__":
    cli()