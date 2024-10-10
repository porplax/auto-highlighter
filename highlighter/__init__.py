import atexit
import glob
import logging
import os
import pathlib
import platform
import tempfile
from signal import *

import click
import numpy as np
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Confirm
from vosk import Model, SetLogLevel

TEMP_DIR = tempfile.TemporaryDirectory()
console = Console()
app = typer.Typer()
model = None

SetLogLevel(0)
FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console, markup=True)]
)

log = logging.getLogger("highlighter")

__all__ = ['analysis', 'generator']

from . import analysis, generator

def exit_handler(*args):
    try:
        # check if the temporary folder is empty. if so, shut up and just delete it.
        if os.listdir(TEMP_DIR.name):
            log.warning('attempting to delete temporary folder ...')
            TEMP_DIR.cleanup()
            log.info('successful ...')
        else:
            TEMP_DIR.cleanup()
    except PermissionError as permError:
        log.error(f"i couldn't delete {TEMP_DIR.name} because of permissions! ({permError})\n"
                  f"it is recommended that you delete it manually.")
    except Exception as e:
        # so usually if the program couldn't delete the temporary folder; it is because of permissions.
        # but if it was something else this can be a major issue.
        # in testing, the highlighter would take up ~30.0GB of data and Windows refused to clean it up automatically.
        # so this is here! tysm windows! :D (i fucking hate windows)
        if platform.system() == 'Windows':
            console.print(f"[blink reverse]ERROR.[/] - couldn't delete the temporary folder. ({e})\n"
                          "this takes up [bold]A LOT[/] of disk space! on windows, this to be done manually.\n"
                          f"go to \"C:/Users/{os.getlogin()}/AppData/Local/Temp\" and delete it's contents.\n"
                          "close all applications that is currently using it.\n"
                          f"or you can instead just delete the temporary folder: \"{TEMP_DIR.name}\"")
        else:
            console.print(f"[blink reverse]ERROR.[/] - couldn't delete the temporary folder. ({e})\n"
                          f"this takes up [bold]A LOT[/] of disk space! this is handled automatically in most cases.\n"
                          "but if for whatever reason it doesn't clear up, you have to do so manually.\n"
                          f"find your system's temporary folder and delete it's contents.\n"
                          "close all applications that is currently using it.\n"
                          f"or you can instead just delete the temporary folder: \"{TEMP_DIR.name}\"")

atexit.register(exit_handler)

for sig in (SIGABRT, SIGFPE,  SIGTERM):
    signal(sig, exit_handler)

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
@click.option('--compile/--skip-compile',
              help='whether or not i should create clips from detected moments.', default=True)
@click.option('--detect-with-video',
              help='instead of detecting with audio, detect with video based on brightness.',
              is_flag=True)
@click.option('--target-brightness',
              help='target brightness required to highlight a moment. (0-255)',
              type=int, required=False, default=125,
              show_default=True)
@click.option('--just-in-time-compilation', '-jit',
              help='instead of compiling after analysis, compile as it find highlights. (only available with video detection)',
              is_flag=True)
@click.option('--disable-ffmpeg-output', '--no-ffmpeg', '-nf',
              help='disables ffmpeg from outputting to terminal.')
@click.option('--keywords', '-k',
              help='uses vosk speech recognition to spot any keywords. highly experimental.',
              multiple=True, required=False, default=None)
def analyze(input, output, target, before, after, accuracy, compile, max_highlights, detect_with_video,
            target_brightness, just_in_time_compilation, disable_ffmpeg_output, keywords):
    """analyze VOD for any highlights."""
    # todo: may be better to detect video length and then determine if the set target dB will be a problem.
    console.clear()
    if keywords:
        global model
        model = Model(lang='en-us')
        log.info(f'[yellow italic]using speech recognition {keywords} ...')


    if 60.0 > target > 50.0:
        log.warning(f'[red italic]target dB: {target} < 60.0 is probably [bold]too low[/] !!![/]\n'
                    '[red bold reverse]this might cause the highlighter to create too many clips and could eat up disk space![/]\n\n'
                    'if this is wanted, ignore this warning.\n'
                    "if you're unsure what this message means, you might want to set it higher\n"
                    "or find the video's reference dB with the [code]find-reference[/] command.\n\n"
                    "[italic]additionally, you can force the program to terminate if the amount of found highlights exceeds a certain amount.")
        confirm = Confirm.ask('continue?')
        if not confirm:
            exit(1)
    elif target < 50.0 and target != 0.0:
        log.warning(f'[red italic]target dB: {target} < 50.0 is [bold]extremely low[/] !!![/]\n'
                    '[red bold reverse blink]THIS WILL CAUSE THE HIGHLIGHTER TO CONSUME ASTRONOMICAL AMOUNTS OF DISK SPACE IF THE VIDEO IS LONG ENOUGH![/]\n\n'
                    'if this is wanted, ignore this warning.\n'
                    "if you're unsure what this message means, you might want to set it higher\n"
                    "or find the video's reference dB with the [code]find-reference[/] command.\n\n"
                    "[italic]additionally, you can force the program to terminate if the amount of found highlights exceeds a certain amount.")
        confirm = Confirm.ask('continue?')
        if not confirm:
            exit(1)
    elif target == 0.0:
        log.error(f'[red italic]target dB: {target} is [bold]way too low and invalid.[/]')
        exit(1)

    log.info(f'using [bold]"{input}"[/] as [cyan]input[/] ...')
    if compile:
        log.info(f'will compile to {output} ...')
    if not detect_with_video:
        log.info(f'minimum decibels to highlight a moment: {target}, [dim italic]with accuracy: {accuracy}[/]')

        log.info(f'converting [bold]"{input}"[/] to [purple].wav[/] file ...')
        analyzer = analysis.AudioAnalysis('', target, output, accuracy, before, after, maximum_depth=max_highlights,
                                          keywords=keywords)
        analyzer.convert_from_video(input)
        log.info(analyzer)
    else:
        log.info(f'minimum luminance to highlight a moment: {target_brightness}')
        analyzer = analysis.VideoAnalysis(input, target_brightness, output, before, after, just_in_time_compilation,
                                          maximum_depth=max_highlights)

    log.info('now analyzing for any moments ...')
    moments = analyzer.analyze_cli()

    if compile and not just_in_time_compilation:
        path = pathlib.Path(output)

        if not path.exists():
            path.mkdir()


        if os.listdir(output):
            deletion = Confirm.ask(f'[bold]"{output}"[/][red italic] is not empty![/]\ndelete contents of {output}?')
            if deletion:
                files = glob.glob(output + '/*')
                for f in files:
                    os.remove(f)

        log.info(f'i am now compiling to {output}')
        compiler = generator.Compiler(input, output, before, after)
        compiler.compile_all(moments)

    log.info('[green]finished![/]')


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

    analyzer = analysis.AudioAnalysis('', 0.0, '', accuracy, 0, 0)
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
