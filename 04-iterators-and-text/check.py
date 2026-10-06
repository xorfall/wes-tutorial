#!/usr/bin/env python3
"""Run every program of tutorial chapter 4 in an isolated home and verify its documented results."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 60
ACCESS_LOG = (
    '# client method path status durationMs\n'
    '10.0.0.5 GET /orders 200 120\n'
    '10.0.0.7 POST /checkout 503 1250\n'
    '10.0.0.5 GET /orders/17 404 40\n'
    '10.0.0.9 POST /checkout 200 310\n'
    '10.0.0.7 GET /orders 200 105\n'
    '10.0.0.9 POST /checkout 500 990\n'
)
APP_LOG = (
    '{"level": "info", "ms": 12, "msg": "order created"}\n'
    '{"level": "error", "ms": 340, "msg": "payment timeout"}\n'
    '{"level": "warn", "ms": 95, "msg": "retrying payment"}\n'
)
ITER_RECIPE = {'kind': 'iter', 'mode': 'lines', 'itemType': {'kind': 'primitive', 'name': 'TEXT'},
               'itemContract': 'Text', 'stages': 1, 'sourceType': {'kind': 'primitive', 'name': 'TEXT'}}
REQUESTS = [
    {'client': '10.0.0.5', 'method': 'GET', 'path': '/orders', 'status': 200, 'durationMs': 120},
    {'client': '10.0.0.7', 'method': 'POST', 'path': '/checkout', 'status': 503, 'durationMs': 1250},
    {'client': '10.0.0.5', 'method': 'GET', 'path': '/orders/17', 'status': 404, 'durationMs': 40},
    {'client': '10.0.0.9', 'method': 'POST', 'path': '/checkout', 'status': 200, 'durationMs': 310},
    {'client': '10.0.0.7', 'method': 'GET', 'path': '/orders', 'status': 200, 'durationMs': 105},
    {'client': '10.0.0.9', 'method': 'POST', 'path': '/checkout', 'status': 500, 'durationMs': 990},
]
SUCCEEDS = {
    'main.wes': [
        ACCESS_LOG,
        7, ['# client method path status durationMs', '10.0.0.5 GET /orders 200 120'],
        ITER_RECIPE, 6,
        REQUESTS,
        2, ['/orders/17'],
        [{'status': '503', 'durationMs': '1250'}, {'status': '500', 'durationMs': '990'}],
        [{'key': 'timeout', 'value': '30'}, {'key': 'retries', 'value': '3'},
         {'key': 'region', 'value': 'eu-west-1'}],
        {'preview': 'payment provider timed...', 'digits': 2},
        ['x-request-id=req-7f3a', 'x-trace-id=trace-91c2'],
        APP_LOG, ['payment timeout'],
        2,
        {**ITER_RECIPE, 'mode': 'matches', 'itemContract': 'RequestLine'}, 6,
    ],
    'edge-cases.wes': [
        ['GET /a 200', 'GET /b 503'], ['first', '', 'third'], ['status=200', 'status=503'],
        2, [3, 3], 4, ['a', 'b', '', 'c'], ['a', 'b', 'c'], ['zone', 'region'],
        'orders-api, billing-worker',
        [{'level': 'info'}], ['10.0', '0.5'],
        [[{'kind': 'some', 'value': '3'}, {'kind': 'some', 'value': ''}]],
        [[{'kind': 'none'}]],
        [{'level': 'info'}, {'level': 'error'}],
    ],
    'exercises.wes': [ACCESS_LOG, APP_LOG, 2, 1, 2550, 'payment timeout'],
}
# Program -> (text the error must contain, values produced despite the failure).
FAILS = {
    'failures/index-iterator.wes': (
        'CAL004: Iter does not support indexing; use .take(1).collect() for a bounded list, '
        'then index that list', [{**ITER_RECIPE, 'stages': 0}]),
    'failures/length-iterator.wes': (
        'CAL004: length does not accept Iter; use .count() to traverse and count it, '
        'or .take(n).collect() for a bounded list', []),
    'failures/impure-callback.wes': (
        'CAL009: lazy Iter callbacks must be pure and cannot capture mutable outer bindings', []),
    'failures/empty-delimiter.wes': (
        'CAL005: iter.split delimiter must not be empty; use iter.chars for individual characters',
        []),
    'failures/unsupported-regex.wes': (
        'CAL016: invalid Iter regex: error: look-around, including look-ahead and look-behind, '
        'is not supported', []),
    'failures/invalid-regex.wes': ('CAL016: invalid Iter regex: error: unclosed group', []),
    'failures/json-lines-blank.wes': (
        'CAL016: JSONL line 2 is blank; every line must contain JSON. To skip blank lines explicitly, use iter.lines(source).filter(line => iter.words(line).count() > 0).map(line => parseJson(line)).collect()', []),
    'failures/wrong-source.wes': ('CAL004: iter.words expects Text; received Int', []),
    'failures/checked-header.wes': (
        'CAL017: Iter item 0, byte 0: item contract validation failed\n  : TYP005: text does not match ^[0-9.]+ [A-Z]+ /', [ACCESS_LOG]),
    'failures/negative-take.wes': ('CAL015: take count must be nonnegative; received -1', []),
    'failures/too-many-stages.wes': ('CAL006: Iter pipeline exceeds 64 stages', []),
}
PRINTED = {}


def run(binary, program):
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-04-') as home:
        return subprocess.run([str(binary), '--home', home, '--file', str(HERE / program)],
                              text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


def printed(stdout):
    return [line.partition(': ')[2] for line in stdout.splitlines()
            if line.startswith('id') and ': ' in line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()

    for program, expected in SUCCEEDS.items():
        result = run(binary, program)
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

    print(f'PASS tutorial 04: {len(SUCCEEDS)} programs and {len(FAILS)} documented failures')


if __name__ == '__main__':
    main()
