#!/usr/bin/env python3
"""Run every program of tutorial chapter 1 in an isolated home and verify its documented results."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 30
SUMMARY = {'service': 'orders-api', 'window': '5m', 'requests': 1250, 'errors': 30, 'errorRate': 2.4}
SERVICES = [
    {'service': 'orders-api', 'requests': 1250, 'errors': 30},
    {'service': 'billing-worker', 'requests': 480, 'errors': 2},
    {'service': 'auth-gateway', 'requests': 3100, 'errors': 0},
]
SUCCEEDS = {
    'main.wes': [1250, 1250, 30, 1220, 2.4, SUMMARY, True, SERVICES],
    'rename.wes': [1250, 2500, 1400, 2800],
    'result-id.wes': [1250, 1220],
    'pure.wes': [1250, 30, 2.4],
    'exercises.wes': [1250, 30, 1220, SERVICES, 97.6, False, 2],
    'fixes.wes': [1250, 12, 1262, 30, True, True, True, 0.3, 'http://127.0.0.1:8080/health'],
}
# Program -> (text the error must contain, values produced before or despite the failure).
FAILS = {
    'failures/unknown-reference.wes': ("CAL010: unknown workspace output '$retries'", [1250]),
    'failures/mixed-numbers.wes': (
        'CAL004: mixed operands require explicit conversion; received Decimal and Int', [1250, 30]),
    'failures/division-by-zero.wes': ('CAL005: division by zero', [0]),
    'failures/pure-call.wes': ('CAL009: pure calculation contains a possible external provider call', []),
    'failures/mixed-comparison.wes': (
        'CAL004: comparison requires matching kinds and explicit conversion; received Decimal and Int',
        [{'service': 'orders-api', 'errorRate': 2.4}]),
    'failures/hyphen-name.wes': (
        'PAR003: Binding names may contain only letters, digits and underscores; '
        'use error_rate instead of error-rate.', []),
}
# Runtime failures report the failing expression's position in the program file.
LOCATIONS = {'failures/division-by-zero.wes': 'at division-by-zero.wes: line 2, column 16'}


def run(binary, program):
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-01-') as home:
        return subprocess.run([str(binary), '--home', home, '--file', str(HERE / program)],
                              text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


def values(stdout):
    return [json.loads(line.partition(': ')[2]) for line in stdout.splitlines()
            if line.startswith('id') and ': ' in line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()

    for program, expected in SUCCEEDS.items():
        result = run(binary, program)
        assert result.returncode == 0, f'{program}: {result.stdout}{result.stderr}'
        assert values(result.stdout) == expected, f'{program}: {result.stdout}'

    for program, (error, expected) in FAILS.items():
        result = run(binary, program)
        output = result.stdout + result.stderr
        assert result.returncode != 0, f'{program} unexpectedly succeeded: {output}'
        assert error in output, f'{program}: {output}'
        assert values(result.stdout) == expected, f'{program}: {result.stdout}'

    for program, location in LOCATIONS.items():
        output = run(binary, program).stderr.replace(str(HERE) + '/', '')
        assert location in output, f'{program}: {output}'

    print(f'PASS tutorial 01: {len(SUCCEEDS)} programs and {len(FAILS)} documented failures')


if __name__ == '__main__':
    main()
