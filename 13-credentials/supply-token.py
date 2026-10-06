#!/usr/bin/env python3
"""Run refunds.wes with the ops token, read without echo and passed to wes on standard input.

Usage: python3 supply-token.py --home DIR [--binary PATH]
The token never appears in a command line, a file or the shell history.
"""
import argparse
import json
import subprocess
import sys
from getpass import getpass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
TOKEN_REFERENCE = 'tutorial/orders/ops-token'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=default_binary())
    args = parser.parse_args()
    token = getpass('ops token: ')
    if not token:
        parser.error('the token must not be empty')
    result = subprocess.run(
        [str(args.binary), '--home', str(args.home), '--env-file', str(HERE / 'environments.yaml'),
         '--env', 'ops', '--credentials-stdin', '--grant-provider', 'orders',
         '--file', str(HERE / 'refunds.wes')],
        input=json.dumps({TOKEN_REFERENCE: token}), text=True, check=False)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
