#!/usr/bin/env python3
"""Run the chapter 8 session against a temporary loopback server and verify the sandbox results.

Sandboxes answer through the client protocol, not the command line, so this check starts its
own `wes --serve` on a free loopback port with a temporary data home and submits each command
the way the client does. Workspace-side results are verified with the command line afterwards.
"""
import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

HERE = Path(__file__).resolve().parent
SEPARATOR = '// ---'
TIMEOUT_SECONDS = 30
BUSY_STATES = {'running', 'pending', 'accepted'}


@contextmanager
def server(binary, home):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([str(binary), '--home', home, '--serve', str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f'http://127.0.0.1:{port}'
        deadline = time.time() + TIMEOUT_SECONDS
        while True:
            try:
                urllib.request.urlopen(base + '/events', timeout=1).close()
                break
            except OSError:
                assert time.time() < deadline, 'server did not start'
                time.sleep(0.1)
        yield Client(base)
    finally:
        process.terminate()
        process.wait(TIMEOUT_SECONDS)


class Client:
    def __init__(self, base):
        self.base = base
        with urllib.request.urlopen(base + '/events', timeout=TIMEOUT_SECONDS) as stream:
            self.generation = json.loads(stream.readline().decode()[len('data: '):])['generation']

    def submit(self, text):
        body = json.dumps({'request': 'submit', 'cell': str(uuid.uuid4()), 'text': text,
                           'client': 'tutorial-check'}).encode()
        request = urllib.request.Request(self.base + '/submit', data=body, headers={
            'Content-Type': 'application/json', 'X-Wes-Session': self.generation})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    def observe(self, reference, inspect=False):
        """Poll a sandbox observation until no member is still running."""
        query = urllib.parse.urlencode({'reference': reference, 'inspect': str(inspect).lower()})
        request = urllib.request.Request(f'{self.base}/sandbox?{query}',
                                         headers={'X-Wes-Session': self.generation})
        deadline = time.time() + TIMEOUT_SECONDS
        while True:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = json.loads(response.read())['sandbox']['value']['data']
            members = data.get('members', []) if isinstance(data, dict) else []
            if not any(member['state'] in BUSY_STATES for member in members):
                return data
            assert time.time() < deadline, f'{reference} did not settle: {data}'
            time.sleep(0.2)


def cli(binary, home, source, *options):
    return subprocess.run([str(binary), '--home', home, *options, '--command', source],
                          text=True, capture_output=True, timeout=TIMEOUT_SECONDS)


def members(data):
    return {m['name']: (m['state'], m.get('value', m.get('error', {}).get('code'))) for m in data['members']}


def accepted(reply):
    status, body = reply
    return status == 200 and body['sandbox']['value']['data'] == {'kind': 'Sandbox', 'state': 'accepted'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    chunks = [c for c in HERE.joinpath('session.wes').read_text().split(SEPARATOR + '\n') if c.strip()]
    assert len(chunks) == 18, len(chunks)
    ready = lambda *values: dict(zip(['replicas', 'perReplicaRps', 'capacityRps', 'headroomRps'],
                                     [('ready', v) for v in values]))
    stopped = {name: ('stopped', None) for name in ['replicas', 'perReplicaRps', 'capacityRps', 'headroomRps']}
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-08-') as home:
        with server(binary, home) as client:
            assert client.submit(chunks[0])[0] == 202
            assert accepted(client.submit(chunks[1]))
            client.submit(chunks[2])
            assert members(client.observe('whatIf')) == ready(6, 300, 1800, 900)
            client.submit(chunks[3])
            assert client.observe('whatIf.headroomRps') == 900
            client.submit(chunks[4])
            inspected = client.observe('whatIf', inspect=True)
            assert inspected['persistence'] == 'definition only'
            assert all('value' not in m and m['state'] == 'ready' for m in inspected['members']), inspected
            assert accepted(client.submit(chunks[5]))
            client.submit(chunks[6])
            assert members(client.observe('whatIf')) == ready(4, 300, 1200, 300)
            status, message = client.submit(chunks[7])
            assert status == 400 and message.startswith('CAL010: Calculation analysis failed at this span.'), message
            assert 'Reference $capacityRps. Sandbox calculations can only reference their own' in message, message
            assert client.submit(chunks[8])[0] == 202
            assert accepted(client.submit(chunks[9]))
            client.submit(chunks[10])
            assert members(client.observe('faulty')) == {
                'perReplica': ('failed', 'CAL005'), 'capacityRps': ('ready', 1200)}
            client.submit(chunks[11])
            stopped_data = client.observe('whatIf')
            assert stopped_data['state'] == 'stopped' and members(stopped_data) == stopped
            client.submit(chunks[12])
            client.submit(chunks[13])
            assert members(client.observe('whatIf')) == ready(4, 300, 1200, 300)
        with server(binary, home) as client:
            client.submit(chunks[14])
            restarted = client.observe('whatIf')
            assert restarted['state'] == 'not run', restarted
            assert {m['state'] for m in restarted['members']} == {'not run'}, restarted
        assert cli(binary, home, ':list sandboxes').stdout.strip().endswith(': ["faulty","whatIf"]')
        with server(binary, home) as client:
            assert client.submit(chunks[15])[0] == 202
            status, body = client.submit(chunks[16])
            assert status == 200 and body['sandbox']['state'] == 'removed', body
            assert client.submit(chunks[17])[0] == 202
        assert cli(binary, home, ':list sandboxes').stdout.strip().endswith(': ["whatIf"]')
        shown = cli(binary, home, ':refresh $whatIf\n:read $whatIf.capacityRps', '--sequential')
        assert shown.stdout.splitlines()[-1] == 'whatIf: 1200', shown.stdout + shown.stderr
        with server(binary, home) as client:
            assert accepted(client.submit(HERE.joinpath('exercises.wes').read_text()))
            assert client.observe('whatIf.replicas') == 3
        # The workspace kept its own result, and cannot read the sandbox.
        read = subprocess.run([str(binary), '--home', home, '--command', ':read $capacityRps'],
                              text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        assert read.stdout.strip().endswith(': 750'), read.stdout + read.stderr
        copied = subprocess.run([str(binary), '--home', home, '--command', chunks[8]],
                                text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        assert "CAL010: unknown workspace output '$whatIf'" in copied.stdout + copied.stderr, copied.stderr
    print(f'PASS tutorial 08: {len(chunks)} submissions, restart, list and remove, exercise, '
          'command line and workspace isolation')


if __name__ == '__main__':
    main()
