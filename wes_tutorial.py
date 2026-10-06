"""Shared helpers for the chapter checks: where the tutorial lives and which wes binary to run.

The tutorial is a separate repository. A check finds wes in this order:
1. the WES environment variable (a path to the wes executable);
2. a wes checkout next to this repository (../wes/target/debug/wes), or WES_CHECKOUT;
3. wes on PATH.
"""
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent
WES_CHECKOUT = Path(os.environ.get('WES_CHECKOUT', REPO.parent / 'wes'))
DEBUG_BINARY = Path('target', 'debug', 'wes')


def default_binary():
    """The wes executable a check runs when --binary is not given."""
    explicit = os.environ.get('WES')
    if explicit:
        return Path(explicit)
    sibling = WES_CHECKOUT / DEBUG_BINARY
    if sibling.is_file():
        return sibling
    found = shutil.which('wes')
    return Path(found) if found else sibling
