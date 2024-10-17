import atexit
import logging
import os
import pathlib
import platform
import glob
import subprocess
import tempfile
import random

import requests
from signal import *

import click
import numpy as np
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Confirm
from seleniumwire import webdriver
TEMP_DIR = tempfile.TemporaryDirectory()
console = Console()
app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="ERROR", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console, markup=True)]
)

log = logging.getLogger("highlighter")

__all__ = ['analysis']

from . import analysis

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
    # todo: may be better to detect video length and then determine if the set target dB will be a problem.
    path = pathlib.Path(output)

    if not path.exists():
        path.mkdir()

    if os.listdir(output):
        log.error(f'[bold]"{output}"[/][red italic] is not empty![/]')
        exit(1)

    log.info(f'i am now compiling to {output}')


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
        analyzer = analysis.AudioAnalysis('', target, output, accuracy, before, after, maximum_depth=max_highlights)
        analyzer.convert_from_video(input)
        log.info(analyzer)
    else:
        log.info(f'minimum luminance to highlight a moment: {target_brightness}')
        analyzer = analysis.VideoAnalysis(input, target_brightness, output, before, after,
                                          maximum_depth=max_highlights)

    log.info('now analyzing for any moments ...')
    analyzer.analyze_cli()

    log.info('[green]finished![/]')


"""@click.command()
def watch():
    driver = webdriver.Firefox()
    driver.get('https://www.twitch.tv/nickmercs')
    c = 0
    while True:
        files = []
        for idx, request in enumerate(driver.requests):
            if request.response:
                print(request.url)
                if request.url.endswith('m3u8'):
                    r = requests.get(request.url)
                    name = random.randint(1000, 9999999)
                    filename = TEMP_DIR.name + f'/{name}.m3u8'
                    files.append(filename)
                    with open(filename, 'xb') as f:
                        f.write(r.content)
                elif request.url.endswith('ts'):
                    r = requests.get(request.url)
                    name = random.randint(1000, 9999999)
                    filename = TEMP_DIR.name + f'/{name}.ts'
                    files.append(filename)
                    with open(filename, 'xb') as f:
                        f.write(r.content)
        cmd = '|'.join(files)
        with open('out.bat', 'w+') as f:
            f.write(f"ffmpeg -protocol_whitelist concat,file,http,https,tcp,tls,crypto -y -i \"concat:{cmd.replace(' ', '')}\" -c copy ./segments/chunk{c}.mp4")
        subprocess.Popen(
            "out.bat"
            , shell=True)
        c += 1"""

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
typer_click_object.add_command(watch, "watch")

def cli():
    typer_click_object()

if __name__ == '__main__':
    cli()
