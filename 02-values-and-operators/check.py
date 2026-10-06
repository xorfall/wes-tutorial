#!/usr/bin/env python3
"""Run every program of tutorial chapter 2 in an isolated home and verify its documented results."""
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
NONE = {'kind': 'none'}
RESPONSE = {'content-type': 'application/json', 'x-request-id': 'req-7f3a', 'status': 503}
HEALTH = {'status': 'degraded', 'uptimeSeconds': 86400, 'load': 0.75, 'maintenance': NONE}
SUCCEEDS = {
    'main.wes': [
        10800000, 0.1, 10800, 3.33, [2, 4],
        10800, {'status': 503, 'load': 0.25, 'rate': '2.4'},
        5, 3,
        'orders-api: 2.4% errors',
        {'length': 10, 'first': 'o', 'prefix': 'orders', 'joined': 'orders-api, billing-worker'},
        True,
        RESPONSE,
        {'contentType': 'application/json', 'hasRetryAfter': False,
         'fields': ['content-type', 'x-request-id', 'status'], 'fieldCount': 3},
        [120, 95, 310, 88], {'first': 120, 'last': 88, 'count': 4, 'middle': [95, 310]},
        NONE, {'kind': 'some', 'value': 30}, {'missing': 5, 'present': 30, 'hasMissing': False},
        HEALTH, {'status': 'degraded', 'load': 0.75, 'maintenance': 'none scheduled'},
    ],
    'edge-cases.wes': [
        False, [4.00, 5.000, 10800], True, [-3, -1], [0.12, 0.38],
        [1, 'orders-api', 2.4], True, 'single "quoted" text',
        False, -9223372036854775808, ['zone', 'region'],
        [NONE, {'kind': 'some', 'value': 30}], 'é',
    ],
    'exercises.wes': [10800000, 99.95, 5400, 4, 'billing-worker: 503', True, 'eu-west-1'],
}
# Decimal scale is part of the documented behaviour, so compare the printed JSON text too.
PRINTED = {'edge-cases.wes': {1: '[4.00,5.000,10800]'}, 'main.wes': {1: '0.1', 3: '3.33'}}
# Program -> (text the error must contain, values produced before the failure).
FAILS = {
    'failures/overflow.wes': (
        'CAL005: integer arithmetic overflow; result must fit a signed 64-bit Int', []),
    'failures/nonterminating.wes': (
        'CAL005: division is nonterminating; use roundDiv with an explicit scale', []),
    'failures/inexact-int.wes': (
        'CAL005: int cannot convert Decimal to an exact signed 64-bit integer', []),
    'failures/text-plus-int.wes': (
        'CAL004: mixed operands require explicit conversion; received Text and Int', []),
    'failures/bool-operand.wes': ('CAL004: expected Bool; received Int', []),
    'failures/missing-field.wes': (
        "CAL004: field or method 'retryAfter' is absent on Record", [{'status': 503}]),
    'failures/index-out-of-range.wes': (
        'CAL015: index 4 is out of range; List length is 4; valid indices are 0..3 (inclusive)',
        [[120, 95, 310, 88]]),
    'failures/invalid-json.wes': (
        'CAL016: JSON input: invalid JSON: key must be a string at line 1 column 2', []),
    'failures/duplicate-field.wes': ('CAL014: duplicate record field', []),
    'failures/slice-out-of-range.wes': ('CAL015: slice end 20 exceeds Text character length 10', []),
    'failures/join-non-text.wes': ('CAL004: expected Text; received Int', []),
    'failures/missing-local-field.wes': ("CAL004: record field 'retryAfter' is absent", []),
    'failures/parse-int.wes': (
        'CAL016: int cannot parse Text as an exact signed 64-bit integer; use integer numeric '
        'Text within the Int range', []),
    'failures/multiline-text.wes': ('CAL001: unescaped control character in string', []),
}


def run(binary, program, structured=False):
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-02-') as home:
        # --json prints each Decimal with its scale, which the chapter documents.
        options = ['--json'] if structured else []
        return subprocess.run([str(binary), '--home', home, *options, '--file', str(HERE / program)],
                              text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


def printed(stdout):
    return [line.partition(': ')[2] for line in stdout.splitlines()
            if line.startswith('id') and ': ' in line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()

    for program, expected in SUCCEEDS.items():
        result = run(binary, program, structured=True)
        assert result.returncode == 0, f'{program}: {result.stdout}{result.stderr}'
        lines = printed(result.stdout)
        assert [json.loads(line) for line in lines] == expected, f'{program}: {result.stdout}'
        for index, text in PRINTED.get(program, {}).items():
            assert lines[index] == text, f'{program} value {index}: {lines[index]} != {text}'

    for program, (error, expected) in FAILS.items():
        result = run(binary, program)
        output = result.stdout + result.stderr
        assert result.returncode != 0, f'{program} unexpectedly succeeded: {output}'
        assert error in output, f'{program}: {output}'
        assert [json.loads(line) for line in printed(result.stdout)] == expected, f'{program}: {output}'

    print(f'PASS tutorial 02: {len(SUCCEEDS)} programs and {len(FAILS)} documented failures')


if __name__ == '__main__':
    main()
