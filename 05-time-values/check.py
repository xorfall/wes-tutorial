#!/usr/bin/env python3
"""Run every program of tutorial chapter 5 in an isolated home and verify its documented results."""
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
CHECKOUT_LOG = (
    '2026-09-28T14:26:10Z GET /checkout 200 180\n'
    '2026-09-28T14:28:45Z GET /checkout 200 210\n'
    '2026-09-28T14:31:05Z POST /checkout 503 1250\n'
    '2026-09-28T14:29:30Z GET /checkout 200 190\n'
    '2026-09-28T14:33:40Z POST /checkout 500 990\n'
    '2026-09-28T14:36:15Z GET /checkout 200 240\n'
    '2026-09-28T14:41:50Z GET /checkout 200 205\n'
)
REQUESTS = [
    {'at': '2026-09-28T14:26:10Z', 'status': 200, 'durationMs': 180},
    {'at': '2026-09-28T14:28:45Z', 'status': 200, 'durationMs': 210},
    {'at': '2026-09-28T14:29:30Z', 'status': 200, 'durationMs': 190},
    {'at': '2026-09-28T14:31:05Z', 'status': 503, 'durationMs': 1250},
    {'at': '2026-09-28T14:33:40Z', 'status': 500, 'durationMs': 990},
    {'at': '2026-09-28T14:36:15Z', 'status': 200, 'durationMs': 240},
    {'at': '2026-09-28T14:41:50Z', 'status': 200, 'durationMs': 205},
]
SPAN = '2026-09-28T14:25:00Z/2026-09-28T14:45:00Z'
TIMELINE = {
    'view': 'timeline', 'id': 'checkout', 'title': 'Checkout latency',
    'range': SPAN, 'coverage': SPAN, 'omitted': 0, 'sourceError': '',
    'series': [{'id': 'latency', 'label': 'latency', 'unit': 'ms', 'samples': [
        {'id': r['at'], 'at': r['at'], 'value': r['durationMs'], 'gap': False} for r in REQUESTS]}],
    'events': [{'id': 'deploy', 'at': '2026-09-28T14:30:00Z', 'label': 'deploy v2.4.1',
                'detail': 'orders-api rollout'}],
}
SUCCEEDS = {
    'main.wes': [
        CHECKOUT_LOG, '2026-09-28T14:30:00Z', 'PT10M',
        '2026-09-28T14:40:00Z', 'PT1M5S', True, 'PT2M30S',
        '2026-09-28T14:30:00Z/2026-09-28T14:40:00Z', '2026-09-28T14:25:00Z/2026-09-28T14:35:00Z',
        'PT10M',
        {'seconds': 1790605800, 'fromMillis': '2026-09-28T14:31:05Z',
         'errorAfterS': 65, 'deployHour': 14},
        REQUESTS, ['PT1M5S', 'PT3M40S'],
        TIMELINE,
    ],
    'edge-cases.wes': [
        '2026-09-29T00:00:00Z', '2026-09-28T14:30:00.123456789Z', True,
        ['PT24H', '-PT5M', 'PT1M30S'], '2026-09-28T14:30:00Z/2026-09-28T14:30:00Z',
        1790605800, 1790605800123456789, 90, 'PT15M', 4, 0.108, 'PT3.333333333S',
        '-PT1M5S', True,
    ],
    'exercises.wes': [CHECKOUT_LOG, '2026-09-28T14:30:00Z', REQUESTS,
                      'PT15M40S', 5, 1790605865000, 'PT5M35S'],
}
# The number of decimal places of epoch conversions is documented.
PRINTED = {'edge-cases.wes': {5: '1790605800.000000000', 7: '90.000000000'}}
INVALID = 'CAL005: invalid timestamp or duration: '
PARSE = 'CAL016: invalid timestamp or duration: '
TIMESTAMP_FORMAT = ('expected ISO date and time with T and an explicit Z or UTC offset, '
                    'for example 2026-01-02T03:04:05Z; at most 9 fractional digits')
DURATION_FORMAT = ('expected ISO duration such as PT5M or -PT1.5S (days/hours/minutes/seconds, '
                   'at most 9 fractional digits); calendar months, years and shorthand such as '
                   '5m are unsupported')
# Program -> (text the error must contain, values produced despite the failure).
FAILS = {
    'failures/space-separated.wes': (PARSE + TIMESTAMP_FORMAT, []),
    'failures/impossible-date.wes': (
        PARSE + 'invalid calendar date, time, UTC offset or supported year range; '
        'check month/day (including leap years), time and offset', []),
    'failures/month-duration.wes': (PARSE + DURATION_FORMAT, []),
    'failures/unit-shorthand.wes': (PARSE + DURATION_FORMAT, []),
    'failures/reversed-interval.wes': (INVALID + 'interval start must not exceed end', []),
    'failures/negative-radius.wes': (INVALID + 'interval radius must be positive', []),
    'failures/uneven-division.wes': (
        'CAL005: duration division requires exact nanoseconds; for explicit rounding use '
        'durationNanos(roundDiv(toNanos(total), count, 0))', []),
    'failures/add-number.wes': ('CAL004: invalid temporal operation: Instant add Int', []),
    'failures/calendar-field.wes': (
        "CAL004: field 'hour' is absent on Instant; use utcParts(instant) for UTC calendar "
        'fields', []),
}


def run(binary, program, structured=False):
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-05-') as home:
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

    print(f'PASS tutorial 05: {len(SUCCEEDS)} programs and {len(FAILS)} documented failures')


if __name__ == '__main__':
    main()
