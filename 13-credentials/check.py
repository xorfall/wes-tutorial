#!/usr/bin/env python3
"""Verify chapter 13 against the synthetic orders-api of chapter 12 on a free loopback port.

Describes the chapter 12 contract into a temporary copy, then checks both authentication
methods, every documented failure, a 401 response, trace redaction, that no data home keeps
the token, and that a token written into a command is stored.
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
CONTRACTS = HERE.parent / '12-api-contracts'
DOCUMENTED_ENDPOINT = 'http://127.0.0.1:8770'
TIMEOUT_SECONDS = 60
TOKEN = 'tutorial-ops-token'
TOKEN_CREDENTIALS = {'tutorial/orders/ops-token': TOKEN}
BASIC_CREDENTIALS = {'tutorial/orders/ops-user': 'ops', 'tutorial/orders/ops-password': 'tutorial-pass'}
REFUNDS = [{'orderId': 3, 'amountCents': 7500}]
NOT_GRANTED = ("HTTP002: credential access has not been granted for provider 'orders'; grant provider "
               "access in /env or use --grant-provider orders in the CLI")
SEC001 = 'SEC001: Possible credential literal in command source.'
sys.path.insert(0, str(CONTRACTS / 'service'))
from orders_api import make_server  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wes_tutorial import default_binary  # noqa: E402


def values(stdout):
    found = []
    for line in stdout.splitlines():
        if line.startswith('id1') and ': ' in line:
            try:
                found.append(json.loads(line.partition(': ')[2]))
            except json.JSONDecodeError:
                found.append(line.partition(': ')[2])
    return found


def stores(home, secret):
    """Files of a data home that contain the secret."""
    return [path for path in Path(home).rglob('*') if path.is_file() and secret.encode() in path.read_bytes()]


class Lab:
    """A service on a free port, and copies of chapters 12 and 13 that point at it."""

    def __init__(self, binary, scratch):
        self.binary = binary
        self.scratch = Path(scratch)
        self.homes = []
        self.server = make_server(0)
        Thread(target=self.server.serve_forever, daemon=True).start()
        endpoint = f'http://127.0.0.1:{self.server.server_port}'
        tutorial = self.scratch / 'tutorial'
        for chapter in (CONTRACTS, HERE):
            shutil.copytree(chapter, tutorial / chapter.name,
                            ignore=shutil.ignore_patterns('orders.json', '__pycache__'))
            for path in (tutorial / chapter.name).rglob('*'):
                if path.suffix in ('.yaml', '.wes'):
                    path.write_text(path.read_text().replace(DOCUMENTED_ENDPOINT, endpoint))
        self.chapter = tutorial / HERE.name
        contract = tutorial / CONTRACTS.name
        described = self.run(None, f':describe file:"{contract}/orders-api.openapi.yaml" provider:orders '
                                   f'out:"{contract}/orders.json" > draft', env=None)
        assert (contract / 'orders.json').is_file(), described.stdout + described.stderr

    def run(self, credentials, source, *options, env='ops', package='environments.yaml'):
        home = self.scratch / f'home-{len(self.homes)}'
        self.homes.append(home)
        command = [str(self.binary), '--home', str(home)]
        if env:
            command += ['--env-file', str(self.chapter / package), '--env', env]
        if credentials is not None:
            command += ['--credentials-stdin']
        result = subprocess.run(command + list(options) + ['--command', source],
                                input=json.dumps(credentials) if credentials is not None else None,
                                text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        return result

    def refunds(self, credentials, *options, env='ops'):
        return self.run(credentials, (self.chapter / 'refunds.wes').read_text(), *options, env=env)

    def requests(self):
        taken = [(request['path'], request['authorized']) for request in self.server.requests]
        self.server.requests.clear()
        return taken


def check_methods(lab):
    for env, credentials in (('ops', TOKEN_CREDENTIALS), ('ops-basic', BASIC_CREDENTIALS)):
        result = lab.refunds(credentials, '--grant-provider', 'orders', env=env)
        response, total = values(result.stdout)
        assert response['status'] == 200 and response['body'] == REFUNDS, result.stdout + result.stderr
        assert total == 7500, total
        assert lab.requests() == [('/refunds?limit=5', True)], env


def check_refusals(lab):
    no_grant = lab.refunds(TOKEN_CREDENTIALS)
    assert NOT_GRANTED in no_grant.stdout + no_grant.stderr
    nothing = lab.refunds(None)
    assert NOT_GRANTED in nothing.stdout + nothing.stderr
    no_value = lab.refunds(None, '--grant-provider', 'orders')
    assert "HTTP002: HTTP requires the missing credential 'opsToken'" in no_value.stdout + no_value.stderr
    no_method = lab.run(None, 'orders listRefunds limit:5 > refunds', package='failures/no-method.yaml')
    assert ("HTTP001: authentication choice is missing; select the endpoint's schemes in environment "
            "bind.auth") in no_method.stdout + no_method.stderr
    # Credentials bound without a method choice are refused while planning.
    unchosen = lab.chapter / 'unchosen.yaml'
    unchosen.write_text('\n'.join(line for line in (lab.chapter / 'environments.yaml').read_text().splitlines()
                                  if 'auth: {listRefunds: [opsToken]}' not in line) + '\n')
    planned = lab.run(None, 'orders health > health', package='unchosen.yaml')
    assert ("ENV010: Provider 'orders' on target 'local': Authentication choice is missing for "
            "'listRefunds'; select its schemes in environment bind.auth before binding credentials"
            ) in planned.stderr, planned.stdout + planned.stderr
    malformed = subprocess.run(
        [str(lab.binary), '--home', str(lab.scratch / 'malformed'), '--env-file',
         str(lab.chapter / 'environments.yaml'), '--env', 'ops', '--credentials-stdin',
         '--command', 'orders health > health'], input='not json', text=True, capture_output=True,
        timeout=TIMEOUT_SECONDS)
    assert 'invalid credential JSON map' in malformed.stderr, malformed.stderr
    empty = lab.refunds({'tutorial/orders/ops-token': ''}, '--grant-provider', 'orders')
    assert ('credential value must not be empty; supply a nonempty value or explicitly forget the '
            'credential') in empty.stderr, empty.stdout + empty.stderr
    unknown = lab.refunds(TOKEN_CREDENTIALS, '--grant-provider', 'nope')
    assert ('ENV005: Credential grant target is unavailable in the requested environment revision'
            in unknown.stderr), unknown.stdout + unknown.stderr
    assert lab.requests() == [], 'a refused call reached the service'


def check_wrong_value_and_trace(lab):
    wrong = lab.refunds({'tutorial/orders/ops-token': 'wrong'}, '--grant-provider', 'orders')
    response = values(wrong.stdout)[0]
    assert response['status'] == 401, wrong.stdout + wrong.stderr
    assert response['body'] == {'error': 'missing or invalid credentials'}
    assert lab.requests() == [('/refunds?limit=5', False)]
    traced = lab.run(TOKEN_CREDENTIALS, '@trace(http) orders listRefunds limit:5 > traced\n'
                                        ':read trace:$traced', '--grant-provider', 'orders', '--sequential')
    assert '{"name":"authorization","value":"[REDACTED]"}' in traced.stdout, traced.stdout + traced.stderr
    assert TOKEN not in traced.stdout + traced.stderr
    lab.requests()


def check_nothing_stored(lab):
    for home in lab.homes:
        if home.exists():
            assert stores(home, TOKEN) == [], f'{home} stores the token'


def check_token_in_source(lab):
    """The documented anti-pattern really stores the token, in its own data home."""
    home = lab.scratch / 'leaked-home'
    source = '\n'.join(line for line in (lab.chapter / 'failures/token-in-source.wes').read_text().splitlines()
                       if not line.startswith('//'))
    result = subprocess.run([str(lab.binary), '--home', str(home), '--sequential', '--command', source],
                            text=True, capture_output=True, timeout=TIMEOUT_SECONDS)
    assert values(result.stdout)[-1]['status'] == 200, result.stdout + result.stderr
    assert SEC001 in result.stdout + result.stderr, result.stdout + result.stderr
    assert result.stderr.count('SEC001') + result.stdout.count('SEC001') == 1
    assert TOKEN not in result.stderr.split('SEC001', 1)[1].split('\n\n')[0]
    places = {path.name for path in stores(home, TOKEN)}
    assert 'journal.jsonl' in places and len(places) >= 2, places
    lab.requests()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    binary = parser.parse_args().binary.resolve()
    with tempfile.TemporaryDirectory(prefix='wes-tutorial-13-') as scratch:
        lab = Lab(binary, scratch)
        try:
            check_methods(lab)
            check_refusals(lab)
            check_wrong_value_and_trace(lab)
            check_nothing_stored(lab)
            check_token_in_source(lab)
        finally:
            lab.server.shutdown()
            lab.server.server_close()
    print('PASS tutorial 13: token and basic methods, refusals before sending, 401 as data, '
          'trace redaction, no stored token, and the stored token of the anti-pattern')


if __name__ == '__main__':
    main()
