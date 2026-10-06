#!/usr/bin/env python3
"""Verify chapter 12 against its own synthetic orders-api on a free loopback port.

Runs the session, the environment package, the exercises and every documented failure in
temporary data homes and checks the results and the requests the service received.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import Thread

HERE = Path(__file__).resolve().parent
CHAPTER = '12-api-contracts'
DOCUMENTED_ENDPOINT = 'http://127.0.0.1:8770'
TIMEOUT_SECONDS = 60
sys.path.insert(0, str(HERE / 'service'))
from orders_api import make_server  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402

ORDERS = [
    {'id': 4, 'status': 'open', 'totalCents': 1250},
    {'id': 3, 'status': 'failed', 'totalCents': 7500},
    {'id': 2, 'status': 'shipped', 'totalCents': 1999},
    {'id': 1, 'status': 'open', 'totalCents': 4200},
]
# Program -> (text the output must contain, requests the service may receive).
FAILS = {
    'limit-out-of-range.wes': (
        'HTTP001: /arguments/limit: query parameter "limit": number is outside the permitted bounds; '
        'number: 1..50 (inclusive)', []),
    'unknown-status.wes': (
        'HTTP001: /arguments/status: query parameter "status": value is not allowed; allowed values: '
        '"open", "shipped", "failed"', []),
    'missing-argument.wes': ("CHK002: 'listOrders' needs 'limit:'", []),
    'unknown-operation.wes': ("RES005: 'orders' offers nothing called 'deleteOrder'", []),
    'missing-endpoint.wes': (
        "IMP001: Required import argument 'endpoint:' is missing. Read this importer's help.", []),
    'authentication-choice.wes': (
        "HTTP001: authentication choice is missing; select the endpoint's schemes in environment bind.auth",
        []),
    'not-openapi.wes': ('DSC002: API source contains unsupported or invalid declarations', []),
    'missing-file.wes': ('DSC003: No such file or directory', []),
    'call-out-of-range.wes': (
        'CAL008: calculation provider call failed: HTTP001: /arguments/limit: query parameter "limit": '
        'number is outside the permitted bounds; number: 1..50 (inclusive)', []),
    'pure-call.wes': ('CAL009: pure calculation contains a possible external provider call', []),
}


def responses(stdout):
    """Values printed on standard output, in order."""
    found = []
    for line in stdout.splitlines():
        if line.startswith('id1') and ': ' in line:
            text = line.partition(': ')[2]
            try:
                found.append(json.loads(text))
            except json.JSONDecodeError:
                found.append(text)
    return found


class Lab:
    """A service on a free port and a copy of the chapter whose endpoint points at it."""

    def __init__(self, binary, scratch):
        self.binary = binary
        self.server = make_server(0)
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}'
        # Paths in the programs are relative to the repository root; run them from a copy.
        self.root = Path(scratch, 'root')
        shutil.copytree(HERE, self.root / CHAPTER, ignore=shutil.ignore_patterns('orders.json', '__pycache__'))

    def text(self, relative):
        return (self.root / CHAPTER / relative).read_text().replace(DOCUMENTED_ENDPOINT, self.endpoint)

    def run(self, home, source, *options):
        return subprocess.run([str(self.binary), '--home', str(home), *options, '--sequential',
                               '--command', source], cwd=self.root, text=True, capture_output=True,
                              timeout=TIMEOUT_SECONDS)

    def requests(self):
        taken = [request['path'] for request in self.server.requests]
        self.server.requests.clear()
        return taken


def check_session(lab, scratch):
    result = lab.run(Path(scratch, 'session'), lab.text('session.wes'))
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "IMP007: Authentication choice required for listRefunds" in output, output
    assert (lab.root / CHAPTER / 'orders.json').is_file(), 'draft file not written'
    values = responses(result.stdout)
    # Help is printed as text after its identifier, not as a JSON value.
    info, health, recent, open_orders, failed, unknown, checks, totals, value = values
    assert 'orders listRefunds  List refunds issued today' in result.stdout, result.stdout
    assert 'limit:  Int (required)\n    Constraints  number: 1..50 (inclusive)' in result.stdout, result.stdout
    assert 'allowed values: "open", "shipped", "failed"' in result.stdout and 'Safety  SAFE' in result.stdout
    draft = json.loads((lab.root / CHAPTER / 'orders.json').read_text())
    assert draft['source']['location'] == 'orders-api.openapi.yaml', draft['source']['location']
    states = {tuple(entry['operation']): entry['state'] for entry in info['information']['authentication']}
    assert states == {('health',): 'selected', ('listOrders',): 'selected', ('getOrder',): 'selected',
                      ('listRefunds',): 'selection-required'}, states
    assert health['status'] == 200 and health['body'] == {'status': 'ok', 'version': '1.4.0'}
    assert recent['body'] == ORDERS[:3] and recent['validation'] == {'state': 'validated', 'issues': []}
    assert open_orders['body'] == [ORDERS[0], ORDERS[3]]
    assert failed['body'] == ORDERS[1]
    assert unknown['status'] == 404 and unknown['body'] == {'error': 'unknown order'}
    assert unknown['validation']['state'] == 'validated', unknown['validation']
    assert checks == {'status': 200, 'healthy': True, 'version': '1.4.0', 'found': False,
                      'problem': 'unknown order'}, checks
    assert totals == [1250, 4200], totals
    assert value == {'orders': 4, 'failedCents': 7500}, value
    assert lab.requests() == ['/health', '/orders?limit=3', '/orders?limit=10&status=open', '/orders/3',
                              '/orders/99', '/orders?limit=10', '/orders/3']
    # Describing never overwrites the draft file.
    before = (lab.root / CHAPTER / 'orders.json').read_bytes()
    again = lab.run(Path(scratch, 'again'), lab.text('session.wes').splitlines()[1])
    assert ('DSC006: Draft saved; export failed because the output already exists. Choose a new '
            'filename; the existing file was not changed.') in again.stdout + again.stderr, again.stdout
    assert (lab.root / CHAPTER / 'orders.json').read_bytes() == before
    return len(values)


def check_reimport(lab, scratch):
    importing = lab.text('failures/limit-out-of-range.wes').splitlines()[0]
    home = Path(scratch, 'reimport')
    lab.run(home, importing)
    refused = lab.run(home, importing)
    assert ('IMP004: Provider already exists; choose another alias or explicitly use replace:true.'
            in refused.stdout + refused.stderr), refused.stdout + refused.stderr
    replaced = lab.run(home, importing + ' replace:true')
    assert "IMP006: provider 'orders' was replaced" in replaced.stdout + replaced.stderr
    lab.requests()
    # A result keeps its captured connection; after a replacement it is refused, not redirected.
    moved = importing.replace('127.0.0.1', 'localhost') + ' replace:true'
    result = lab.run(Path(scratch, 'binding'), '\n'.join(
        [importing, 'orders health > before', moved, 'orders health > after', ':refresh $before']))
    output = result.stdout + result.stderr
    assert ("ENV039: Captured binding for provider 'orders' in environment 'default' changed or was "
            "removed") in output, output
    assert lab.requests() == ['/health', '/health'], 'the refused refresh reached the service'
    inspected = lab.run(Path(scratch, 'binding'), ':inspect $before')
    assert 'binding changed or removed; new command required' in inspected.stdout, inspected.stdout


def check_safety(lab, scratch):
    """An explicit safety in the local draft overrides the method; other values are refused."""
    document = Path(scratch, 'search.yaml')
    document.write_text('openapi: 3.1.0\ninfo: {title: search, version: "1"}\npaths:\n'
                        '  /orders/search:\n    post:\n      operationId: searchOrders\n'
                        '      security: []\n      responses: {"200": {description: Orders}}\n')
    draft = Path(scratch, 'search.json')
    lab.run(Path(scratch, 'describe-search'), f':describe file:"{document}" provider:search out:"{draft}" > d')
    contract = json.loads(draft.read_text())
    importing = f':import spec file:"{draft}" endpoint:"{lab.endpoint}" as:search\n:help search searchOrders'
    default = lab.run(Path(scratch, 'safety-default'), importing)
    assert 'Safety  UNSAFE' in default.stdout, default.stdout + default.stderr
    contract['operations'][0]['safety'] = 'safe'
    draft.write_text(json.dumps(contract))
    explicit = lab.run(Path(scratch, 'safety-safe'), importing + '\n:info search > info')
    assert 'Safety  SAFE' in explicit.stdout, explicit.stdout + explicit.stderr
    assert '"basis":"explicit local contract"' in explicit.stdout, explicit.stdout
    contract['operations'][0]['safety'] = 'maybe'
    draft.write_text(json.dumps(contract))
    invalid = lab.run(Path(scratch, 'safety-invalid'), importing)
    assert 'IMP001: operation safety must be safe or unsafe' in invalid.stdout + invalid.stderr
    assert lab.requests() == []


def check_environment(lab, scratch):
    package = lab.root / CHAPTER / 'environments.yaml'
    package.write_text(lab.text('environments.yaml'))
    result = lab.run(Path(scratch, 'environment'), 'orders health > health', '--env-file', str(package),
                     '--env', 'shop')
    assert responses(result.stdout)[-1]['body']['status'] == 'ok', result.stdout + result.stderr
    assert lab.requests() == ['/health']


def check_exercises(lab, scratch):
    source = lab.text('failures/limit-out-of-range.wes').splitlines()[0] + '\n' + lab.text('exercises.wes')
    result = lab.run(Path(scratch, 'exercises'), source)
    output = result.stdout + result.stderr
    assert responses(result.stdout)[1] == 1999, output
    assert ('HTTP001: /arguments/id: path parameter "id": number is outside the permitted bounds; '
            'number: at least 1 (inclusive)') in output, output
    assert lab.requests() == ['/orders?limit=10&status=shipped']


def check_failures(lab, scratch):
    for number, (program, (message, sent)) in enumerate(FAILS.items()):
        result = lab.run(Path(scratch, f'failure-{number}'), lab.text(f'failures/{program}'))
        output = result.stdout + result.stderr
        assert message in output, f'{program}: {output}'
        assert lab.requests() == sent, f'{program} sent a request'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-12-') as scratch:
        lab = Lab(binary, scratch)
        try:
            values = check_session(lab, scratch)
            check_reimport(lab, scratch)
            check_safety(lab, scratch)
            check_environment(lab, scratch)
            check_exercises(lab, scratch)
            check_failures(lab, scratch)
        finally:
            lab.server.shutdown()
            lab.server.server_close()
    print(f'PASS tutorial 12: session with {values} results, environment package, exercises and '
          f'{len(FAILS)} documented failures; refused calls sent no request')


if __name__ == '__main__':
    main()
