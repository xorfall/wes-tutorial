#!/usr/bin/env python3
"""Verify chapter 9 against the Docker lab: three targets, results as data and target failures.

Requires Docker with Compose and an OpenSSH client. The check starts the lab with lab/setup.sh,
runs every command on the command line with --env-file, and stops the lab again if it started
it. Without Docker it reports SKIP.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
LAB = HERE / 'lab'
TIMEOUT_SECONDS = 120


def compose(*args):
    return subprocess.run(['docker', 'compose', '-f', str(LAB / 'compose.yaml'), *args],
                          text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


def lab_running():
    result = compose('ps', '--status', 'running', '--services')
    return result.returncode == 0 and {'orders-api', 'edge-host'} <= set(result.stdout.split())


def run(binary, source, package=None):
    """Run one command in a fresh data home with the lab package applied."""
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-09-') as scratch:
        home = Path(scratch, 'home')
        if package is None:
            package = Path(scratch, 'environments.yaml')
            package.write_text(absolute((LAB / 'environments.yaml').read_text()))
        result = subprocess.run(
            [str(binary), '--home', str(home), '--env-file', str(package),
             '--env', 'lab', '--command', source],
            text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
    return result.stdout + result.stderr


def absolute(package_text, **replace):
    """Copy the lab package for another directory: anchor its relative key paths to the lab."""
    lines = []
    for line in package_text.splitlines():
        key = line.strip().partition(':')[0]
        if key in ('identity_file', 'known_hosts'):
            value = replace.get(key, LAB / line.strip().partition(': ')[2])
            line = f'    {key}: "{value}"'
        elif key == 'socket' and os.environ.get('WES_DOCKER_SOCKET'):
            line = f'    socket: {json.dumps(os.environ["WES_DOCKER_SOCKET"])}'
        lines.append(line)
    return '\n'.join(lines) + '\n'


def output(text):
    for line in text.splitlines():
        if line.startswith('id') and ': {' in line:
            value = json.loads(line.partition(': ')[2])
            return {key: base64.b64decode(value[key]).decode() if key in ('stdout', 'stderr') else value[key]
                    for key in value}
    raise AssertionError(text)


def session():
    chunks = HERE.joinpath('session.wes').read_text().split('// ---\n')
    return ['\n'.join(line for line in chunk.splitlines() if not line.startswith('//')) for chunk in chunks]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    if shutil.which('docker') is None or subprocess.run(['docker', 'info'], capture_output=True).returncode:
        print('SKIP tutorial 09: Docker is not available')
        return
    started = not lab_running()
    subprocess.run(['sh', str(LAB / 'setup.sh')], check=True, capture_output=True, timeout=600)
    try:
        commands = session()
        assert output(run(binary, commands[4])) == {
            'exitCode': 0, 'stdout': 'running on the local machine\n', 'stderr': ''}
        assert output(run(binary, commands[5])) == {
            'exitCode': 0, 'stdout': 'orders-api\norders-api 2.4.1\n2.4.1\n', 'stderr': ''}
        assert output(run(binary, commands[6])) == {
            'exitCode': 0, 'stdout': 'edge-host\nops\nedge-host\nregion=eu-west-1\n', 'stderr': ''}
        missing = output(run(binary, commands[8]))
        assert missing['exitCode'] == 1 and 'missing.txt' in missing['stderr'], missing
        assert 'ENV036: SSH execution exceeded its time budget' in run(binary, commands[9])
        # The comparison of step 6, with both outputs in one program.
        both = run(binary, '\n'.join([commands[5], commands[6], commands[7]]))
        hosts = json.loads([l for l in both.splitlines() if l.startswith('id1002: ')][0].partition(': ')[2])
        assert hosts == {'app': ['orders-api', 'orders-api 2.4.1', '2.4.1'],
                         'edge': ['edge-host', 'ops', 'edge-host', 'region=eu-west-1']}, hosts
        # Target failures of step 7.
        compose('stop', 'orders-api')
        try:
            assert 'ENV038: Compose target wes-tutorial-09/orders-api has no running service container' \
                in run(binary, 'app run cmd:"hostname"')
        finally:
            compose('start', 'orders-api')
        with tempfile.TemporaryDirectory() as scratch:
            empty = Path(scratch, 'known_hosts')
            empty.write_text('')
            package = Path(scratch, 'environments.yaml')
            package.write_text(absolute((LAB / 'environments.yaml').read_text(), known_hosts=empty))
            unknown = run(binary, 'edge run cmd:"hostname"', package)
            assert 'ENV036: SSH client did not report a trustworthy remote exit' in unknown, unknown
            assert 'Host key verification failed' in unknown, unknown
            # Home expansion and PATH search are refused while planning.
            for field, value, message in [
                    ('identity_file', '~/.ssh/id_ed25519', "SSH paths do not expand '~'"),
                    ('client', 'ssh', 'SSH client does not search PATH')]:
                changed = package.read_text().replace(
                    next(l for l in package.read_text().splitlines() if l.strip().startswith(field + ':')),
                    f'    {field}: {value}')
                package.write_text(changed)
                assert f'ENV010: {message}' in run(binary, 'local run cmd:"true"', package)
                package.write_text(absolute((LAB / 'environments.yaml').read_text(), known_hosts=empty))
            # Missing key files are refused before anything runs; their contents are never read.
            for field, message in [('identity_file', 'SSH identity file was not found'),
                                   ('known_hosts', 'SSH known-hosts file was not found')]:
                package.write_text(absolute((LAB / 'environments.yaml').read_text(),
                                            **{field: Path(scratch, 'missing')}))
                assert f'ENV010: {message}' in run(binary, 'edge run cmd:"hostname"', package)
                package.write_text(absolute((LAB / 'environments.yaml').read_text(), known_hosts=empty))
        # Reopening a data home closes environment execution until it is activated.
        with tempfile.TemporaryDirectory(prefix='wes-tutorial-09-') as scratch:
            home = str(Path(scratch, 'home'))
            package = Path(scratch, 'environments.yaml')
            package.write_text(absolute((LAB / 'environments.yaml').read_text()))
            base = [str(binary), '--home', home, '--env-file', str(package), '--env', 'lab']
            first = subprocess.run(base + ['--command', 'app run cmd:"hostname"'], text=True, capture_output=True)
            second = subprocess.run(base + ['--command', 'app run cmd:"hostname"'], text=True, capture_output=True)
            third = subprocess.run(base + ['--activate-env', '--command', 'app run cmd:"hostname"'],
                                   text=True, capture_output=True)
            assert output(first.stdout)['stdout'] == 'orders-api\n'
            assert ('ENV020: Environment execution is closed after reopening; explicitly select it '
                    'again or use --env NAME --env-revision REVISION --activate-env.') in second.stdout + second.stderr
            assert output(third.stdout)['stdout'] == 'orders-api\n'
            # An applied environment is selected by revision, without the package.
            revision = json.loads(subprocess.run(
                [str(binary), '--home', home, '--command', ':inspect env:"lab"'],
                text=True, capture_output=True).stdout.partition(': ')[2])['revision']
            by_revision = subprocess.run(
                [str(binary), '--home', home, '--env', 'lab', '--env-revision', revision, '--activate-env',
                 '--command', 'edge run cmd:"hostname"'], text=True, capture_output=True)
            assert output(by_revision.stdout)['stdout'] == 'edge-host\n', by_revision.stdout + by_revision.stderr
            exported = subprocess.run(
                [str(binary), '--home', home, '--env', 'lab', '--env-revision', revision, '--activate-env',
                 '--command', f':env export file:"{Path(home, "lab.lock")}"'], text=True, capture_output=True)
            assert 'Local paths and target metadata are included; review them before sharing.' in exported.stdout
        # Plan and apply belong to one session; the command line cannot apply a plan later.
        with tempfile.TemporaryDirectory(prefix='wes-tutorial-09-') as home:
            plan = subprocess.run([str(binary), '--home', home, '--command', commands[0]],
                                  text=True, capture_output=True)
            apply = subprocess.run([str(binary), '--home', home, '--command', commands[1]],
                                   text=True, capture_output=True)
        assert "plan 'proposed': 1 environment change; apply uses these captured inputs" in plan.stdout
        assert 'imports added: app, edge, local' in plan.stdout, plan.stdout
        assert 'ENV001: No live environment plan with this name belongs to this client.' in apply.stdout + apply.stderr
        # Exercises: an extra import, and a file that exists only in the container.
        exercises = [chunk for chunk in HERE.joinpath('exercises.wes').read_text().split('// ---\n')]
        exercises = ['\n'.join(l for l in c.splitlines() if not l.startswith('//')) for c in exercises]
        with tempfile.TemporaryDirectory() as scratch:
            package = Path(scratch, 'environments.yaml')
            package.write_text(absolute((LAB / 'environments.yaml').read_text())
                               + HERE.joinpath('exercises.yaml').read_text())
            assert output(run(binary, exercises[0], package))['stdout'] == \
                '2026-09-30T10:01:30Z deploy 2.4.1 finished\n'
        wrong_host = output(run(binary, exercises[1]))
        assert wrong_host['exitCode'] == 1 and 'VERSION' in wrong_host['stderr'], wrong_host
        # Facts quoted in the text.
        assert 'Safety  UNSAFE' in run(binary, ':help app run')
        assert '["default","lab"]' in run(binary, ':list environments')
    finally:
        if started:
            subprocess.run(['sh', str(LAB / 'teardown.sh')], capture_output=True, timeout=600)
    print('PASS tutorial 09: three targets, outputs, failures, activation and plan authority')


if __name__ == '__main__':
    main()
