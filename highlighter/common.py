import atexit
import os
import platform
import warnings
from signal import *

from . import TEMP_DIR, log, console

warnings.filterwarnings("ignore")


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

for sig in (SIGABRT, SIGFPE, SIGTERM):
    signal(sig, exit_handler)
