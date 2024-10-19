import logging
import os
import pathlib
import tempfile

import click
import numpy as np
import typer
from rich.console import Console
from rich.logging import RichHandler

TEMP_DIR = tempfile.TemporaryDirectory()
console = Console()
app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console, markup=True)]
)

log = logging.getLogger("highlighter")

__all__ = ['video', 'audio', 'common']

from . import video, audio, common

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
        analyzer = audio.AudioAnalysis('', target, output, accuracy, before, after, maximum_depth=max_highlights)
        analyzer.convert_from_video(input)
        log.info(analyzer)
    else:
        log.info(f'minimum luminance to highlight a moment: {target_brightness}')
        analyzer = video.VideoAnalysis(input, target_brightness, output, before, after,
                                          maximum_depth=max_highlights)

    log.info('now analyzing for any moments ...')
    analyzer.analyze()

    log.info(f'[green]success! all clips should be found in the {output} folder.[/]')

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

    analyzer = audio.AudioAnalysis('', 0.0, '', accuracy, 0, 0)
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

