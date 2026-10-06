#!/usr/bin/env python3
"""Run every program of tutorial chapter 3 in an isolated home and verify its documented results."""
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
SAMPLES = [
    {'route': '/orders', 'status': 200, 'durationMs': 120},
    {'route': '/orders', 'status': 201, 'durationMs': 95},
    {'route': '/orders/{id}', 'status': 404, 'durationMs': 40},
    {'route': '/checkout', 'status': 503, 'durationMs': 1250},
    {'route': '/checkout', 'status': 200, 'durationMs': 310},
    {'route': '/orders/{id}', 'status': 200, 'durationMs': 88},
    {'route': '/checkout', 'status': 500, 'durationMs': 990},
    {'route': '/orders', 'status': 200, 'durationMs': 105},
]
SUCCEEDS = {
    'main.wes': [
        SAMPLES,
        3,
        {'attempts': 5, 'totalMs': 3100},
        ['2xx', '2xx', '4xx', '5xx', '2xx', '2xx', '5xx', '2xx'],
        {'kind': 'some', 'value': '/checkout'},
        {'failures': 2, 'meanMs': 374.8, 'maxMs': 1250},
        1250,
        [
            {'route': '/checkout', 'status': 503, 'durationMs': 1250},
            {'route': '/checkout', 'status': 500, 'durationMs': 990},
            {'route': '/checkout', 'status': 200, 'durationMs': 310},
        ],
        [
            {'route': '/orders', 'requests': 3, 'failures': 0},
            {'route': '/orders/{id}', 'requests': 2, 'failures': 0},
            {'route': '/checkout', 'requests': 3, 'failures': 2},
        ],
        [250, 500, 750],
        3200,
    ],
    'limits.wes': [50000, 600000, 126],
    # The consumer of an unused failure output does not run; the CLI explains why.
    'failure-output-success.wes': [{'status': 'ok'}],
    'watch-out.wes': [SAMPLES, {'ok': 6, 'failed': 2}, [100, 200, 400, 800, 1600],
                      'status, retryAfter'],
    'exercises.wes': [SAMPLES, 5, ['/checkout', '/checkout', '/checkout'], 66.7, 10],
}
# Program -> (text the error must contain, values produced despite the failure).
FAILS = {
    'failure-output.wes': (
        'CAL016: JSON input: invalid JSON: EOF while parsing an object at line 1 column 17',
        ['health check failed: CAL016 JSON input: invalid JSON: '
         'EOF while parsing an object at line 1 column 17']),
    'failures/missing-return.wes': (
        'CAL013: calculation/function reaches its end without returning a value; add return', []),
    'failures/missing-return-at-run-time.wes': (
        'CAL013: calculation or anonymous function completed without return', [0]),
    'failures/use-before-declaration.wes': (
        "CAL013: local 'double' is used before initialization; keep declarations before their use",
        []),
    'failures/let-without-value.wes': ('CAL001: binding declarations require an initial value', []),
    'failures/assign-const.wes': ('CAL011: cannot assign a const binding; use let for a variable that needs rebinding', []),
    'failures/assign-list-item.wes': ('CAL001: only local let bindings may be assigned; record fields and list items are immutable values', []),
    'failures/non-bool-condition.wes': ('CAL004: condition requires Bool; received Int', []),
    'failures/filter-non-bool.wes': ('CAL004: expected Bool; received Int', []),
    'failures/conditional-operator.wes': (
        'CAL001: the ?: operator is not supported; use if/else and return the selected value', []),
    'failures/arrow-record.wes': ('CAL001: expected a statement, not a record field; braces after => start a block', []),
    'failures/return-function.wes': ('CAL004: functions cannot cross a value boundary', []),
    'failures/wrong-arity.wes': ("CAL012: function 'add' expects 2 argument(s); received 1", []),
    'failures/endless-loop.wes': (
        'CAL006: calculation work limit reached (1000000 work units). Reduce the input or split '
        'the calculation; work units count evaluated operations, not loop iterations.', []),
    'failures/too-deep.wes': ('CAL006: calculation call-frame limit reached', []),
    'failures/too-large.wes': ('CAL006: calculation retained allocation limit reached', []),
    'failures/zero-step.wes': ('CAL005: range step must be nonzero', []),
    'failures/shadowed-call.wes': ('CAL004: This value is not callable; expected Function.', []),
    'failures/reserved-iter.wes': (
        "CAL010: local name 'iter' conflicts with the language vocabulary; choose another name", []),
    'failures/sort-lists.wes': (
        'CAL004: sortBy keys requires matching Int, Decimal, Text, Instant or Duration', []),
    'failures/sort-impure.wes': (
        'CAL009: sortBy selector must be pure and cannot capture mutable outer bindings', []),
    'failures/concat-mixed.wes': ('CAL004: concat requires compatible element types', []),
}
# Explanations the CLI prints on standard error for successful programs.
NOTES = {'failure-output-success.wes': 'error output was not produced by $health in this run'}
PRINTED = {'main.wes': {5: '{"failures":2,"meanMs":374.8,"maxMs":1250}'}}


def value(line):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return 'TEXT:' + line


def run(binary, program):
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-03-') as home:
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
        assert [value(line) for line in lines] == expected, f'{program}: {result.stdout}'
        if program in NOTES:
            assert NOTES[program] in result.stderr, f'{program}: {result.stderr}'
        for index, text in PRINTED.get(program, {}).items():
            assert lines[index] == text, f'{program} value {index}: {lines[index]} != {text}'

    for program, (error, expected) in FAILS.items():
        result = run(binary, program)
        output = result.stdout + result.stderr
        assert result.returncode != 0, f'{program} unexpectedly succeeded: {output}'
        assert error in output, f'{program}: {output}'
        assert [value(line) for line in printed(result.stdout)] == expected, f'{program}: {output}'

    print(f'PASS tutorial 03: {len(SUCCEEDS)} programs and {len(FAILS)} documented failures')


if __name__ == '__main__':
    main()
