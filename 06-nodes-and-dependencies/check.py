#!/usr/bin/env python3
"""Submit the chapter 6 session one command at a time and verify the documented results."""
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
SEPARATOR = '// ---'
WORKSPACE = 'capacity'
PROCESS_3 = {'exitCode': 0, 'stdout': 'Mw==', 'stderr': ''}
PROCESS_5 = {'exitCode': 0, 'stdout': 'NQ==', 'stderr': ''}
STALE = ('RUN001: Result $headroomRps is stale: An upstream result was requested again; '
         'this result is no longer current. Use :refresh $capacityRps scope:downstream')
# One entry per submission: (values printed on standard output, text the output must contain).
EXPECTED = [
    ([], None),
    ([PROCESS_3, 250, 750, 150], None),
    (None, '"dependsOn":["id1002"]'),
    (None, '"name":"$headroomRps"'),
    ([PROCESS_3], 'refresh $replicas · default / sh · target local · rev 1cdd6a70 · 1 execution requested · 1 started · 2 marked stale'),
    (None, STALE),
    (None, 'Waiting for data output from $headroomRps'),
    ([PROCESS_3, 750, 150, True], None),
    ([], 'change $replicas · definition updated · 4 marked stale'),
    ([PROCESS_5, 1250, 650, True], None),
    ([650], None),
    ([], None),
    ([PROCESS_5, 1250, 650, True], None),
    ([], None),
    ([], None),
    (None, 'RUN002: The local operation was cancelled because its timeout expired.'),
    ([], None),
    ([], 'remove downstream $replicas · 4 removed · 3 names unbound'),
    (None, '[{"name":"$perReplicaRps","node":"id1001"'),
]
UNBIND = [([], None), ([PROCESS_3, 250, 750, 150, True], None), ([], None), ([True], None)]
PROCESS_3_RUN = [PROCESS_3, 250, 750, 150]
EXERCISES = [
    ([], None),
    (PROCESS_3_RUN, None),
    ([-150], None),
    (None, 'MET004: the target is not a provider call'),
    ([], None),
    ([PROCESS_3, 750], None),
    (None, ('"node":"id1002","state":"ready"', '"node":"id1003","state":"stale"',
            '"node":"id1004","state":"stale"')),
    ([PROCESS_3, 750, 150, -150], None),
]


def submissions(name):
    chunks = HERE.joinpath(name).read_text().split(SEPARATOR + '\n')
    return [chunk for chunk in chunks if chunk.strip()]


def values(stdout):
    found = []
    for line in stdout.splitlines():
        if line.startswith('id') and ': ' in line:
            try:
                found.append(json.loads(line.partition(': ')[2]))
            except json.JSONDecodeError:
                return None
    return found


def run_session(binary, name, expected):
    chunks = submissions(name)
    assert len(chunks) == len(expected), f'{name}: {len(chunks)} submissions, {len(expected)} expectations'
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-06-') as home:
        for number, (source, (printed, text)) in enumerate(zip(chunks, expected), start=1):
            result = subprocess.run(
                [str(binary), '--home', home, '--workspace', WORKSPACE, '--command', source],
                text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
            output = result.stdout + result.stderr
            if printed is not None:
                assert values(result.stdout) == printed, f'{name} submission {number}: {output}'
            for fragment in ((text,) if isinstance(text, str) else text or ()):
                assert fragment in output, f'{name} submission {number}: {output}'
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    count = run_session(binary, 'session.wes', EXPECTED)
    count += run_session(binary, 'unbind.wes', UNBIND)
    count += run_session(binary, 'exercises.wes', EXERCISES)
    print(f'PASS tutorial 06: {count} submissions')


if __name__ == '__main__':
    main()
