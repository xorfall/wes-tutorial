#!/usr/bin/env python3
"""Submit the chapter 7 session one command at a time and verify the documented results."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 60
SEPARATOR = '// ---'
# The chapter lowers the automatic retention limit so that one result is not kept.
KEEP_UNDER = '200'
REQUEST_IDS = ['request-' + str(i) for i in range(100)]


def names_and_states(stdout):
    for line in stdout.splitlines():
        if line.startswith('id') and ': [' in line:
            return {row['name']: row['state'] for row in json.loads(line.partition(': ')[2])}
    return None


def values(stdout):
    found = []
    for line in stdout.splitlines():
        if line.startswith('id') and ': ' in line:
            try:
                found.append(json.loads(line.partition(': ')[2]))
            except json.JSONDecodeError:
                return None
    return found


# One entry per submission: a function that receives (stdout, output) and returns True.
EXPECTED = [
    lambda out, all_: values(out) == [['default']],
    lambda out, all_: values(out) == [750],
    lambda out, all_: values(out) == [REQUEST_IDS],
    lambda out, all_: "saved workspace 'capacity-0930'" in out,
    lambda out, all_: values(out) == [['capacity-0930', 'default']],
    lambda out, all_: values(out) == [1250],
    lambda out, all_: set(names_and_states(out)) == {'$capacityRps', '$requestIds', '$afterScaleOut'},
    lambda out, all_: names_and_states(out) == {'$capacityRps': 'READY', '$requestIds': 'STALE'}
                      and '"element":{"kind":"primitive","name":"TEXT"}' in out,
    lambda out, all_: values(out) == [750],
    lambda out, all_: ('RUN001: Result $requestIds is stale: No retained result was available '
                       'when the workspace reopened.') in all_
                      and 'Use :refresh $requestIds' in all_,
    lambda out, all_: values(out) == [REQUEST_IDS],
    lambda out, all_: '"workspace": "capacity-0930"' in out and '"expiresInSeconds": 120' in out,
    lambda out, all_: 'Expected a live WorkspaceDeletePlan' in all_,
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    chunks = [c for c in HERE.joinpath('session.wes').read_text().split(SEPARATOR + '\n') if c.strip()]
    assert len(chunks) == len(EXPECTED), f'{len(chunks)} submissions, {len(EXPECTED)} expectations'
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-07-') as home:
        for number, (source, expected) in enumerate(zip(chunks, EXPECTED), start=1):
            workspace = re.search(r'^// workspace: (\S+)', source, re.M)
            command = [str(binary), '--home', home, '--keep-under', KEEP_UNDER]
            if workspace:
                command += ['--workspace', workspace.group(1)]
            result = subprocess.run(command + ['--command', source],
                                    text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
            assert expected(result.stdout, result.stdout + result.stderr), \
                f'submission {number}: {result.stdout}{result.stderr}'
    # One --sequential invocation is one session, so a plan can be applied in it.
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-07-') as home:
        deleted = sequential(binary, home, 'delete.wes')
        assert deleted.returncode == 0, deleted.stdout + deleted.stderr
        assert deleted.stdout.strip().endswith('["default"]'), deleted.stdout
        assert 'Workspace deletion completed.' in deleted.stdout, deleted.stdout
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-07-') as home:
        refused = sequential(binary, home, 'refused.wes')
        output = refused.stdout + refused.stderr
        assert refused.returncode != 0, output
        assert 'STO003: The deletion preview expired' in output, output
        assert ':list workspaces' not in output and '["default"]' not in output, output
    print(f'PASS tutorial 07: {len(chunks)} submissions and 2 sequential programs')


def sequential(binary, home, program):
    return subprocess.run([str(binary), '--home', home, '--sequential', '--file', str(HERE / program)],
                          text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


if __name__ == '__main__':
    main()
