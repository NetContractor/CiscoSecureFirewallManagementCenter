"""Console input helpers."""

import getpass
import sys


def read_secret(prompt):
    """Password prompt. getpass hangs in IDE consoles (e.g. PyCharm Run window) on Windows, so input() is used there."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    print(
        "WARNING: not running in a terminal - the value will be visible. "
        "In PyCharm enable 'Emulate terminal in output console' in the Run configuration to hide it."
    )
    return input(prompt)
