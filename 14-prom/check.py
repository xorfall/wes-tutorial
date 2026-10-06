#!/usr/bin/env python3
"""Check real Prometheus inputs, reference following, Pin and live log windows."""
import argparse
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from client import Client
from dashboard import dashboard_definition

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LAB = HERE / 'lab'
sys.path.insert(0, str(REPO))
from wes_tutorial import WES_CHECKOUT, default_binary  # noqa: E402

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROM = 'http://127.0.0.1:19091'
API = 'http://127.0.0.1:18770'
COMPOSE = ['docker', 'compose', '-f', str(LAB / 'compose.yaml')]
FILES = ['describe.wes', 'config.wes', 'import.wes', 'helpers.wes',
         'discover.wes', 'load-view.wes', 'queries.wes', 'window.wes',
         'fetch.wes', 'draw.wes', 'create.wes']


def request(url, body=None):
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    data = json.dumps(body).encode() if body is not None else None
    with OPENER.open(urllib.request.Request(url, data, headers), timeout=5) as r:
        return json.load(r)


def query(expression):
    return request(PROM + '/api/v1/query?' +
                   urllib.parse.urlencode({'query': expression}))


def eventually(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError('The lab did not reach the expected condition')


def commands(text):
    """Split the checked top-level command forms, retaining calc body lines."""
    chunks, current = [], []
    for line in text.splitlines():
        if line.startswith('//'):
            continue
        if line and not line[0].isspace() and not line.startswith('}'):
            if current:
                chunks.append('\n'.join(current))
                current = []
        if line.strip():
            current.append(line)
    if current:
        chunks.append('\n'.join(current))
    return chunks


def program(client, name, socket):
    text = HERE.joinpath(name).read_text()
    if name == 'logs.wes':
        text = text.replace('"/var/run/docker.sock"', json.dumps(socket))
    for command in commands(text):
        before = client.serial
        client.submit(command)
        if command.startswith(':describe'):
            client.wait(lambda: any(e['event'] == 'ready' and
                        e['_serial'] > before for e in client.events))
        elif command.startswith(':import plan'):
            plan = command.rsplit('>', 1)[1].strip()
            details = client.value(plan)['data']
            assert details['contentsReadWhenPlanned'] is False
            assert details['origins']
        elif command.startswith(':import'):
            client.wait(lambda: any(e['event'] == 'environments' and
                        e['_serial'] > before for e in client.events))


def assert_snapshots(client):
    """Every plotted sample is the exact adapted value from its HTTP response."""
    latest = {}
    for raw_name, data_name in [('rateRaw', 'rateData'),
                                ('errorsRaw', 'errorsData'),
                                ('p95Raw', 'latencyData')]:
        raw = client.value(raw_name)['data']
        drawn = client.value(data_name)['data']
        assert raw['status'] == 200
        assert raw['validation']['state'] == 'validated'
        assert raw['body']['data']['resultType'] == 'matrix'
        pairs = raw['body']['data']['result'][0]['values']
        samples = drawn['series'][0]['samples']
        assert 1 <= len(samples) <= 60
        assert len(samples) == len(pairs) - 1, (raw_name, len(samples))
        assert len({p['id'] for p in samples}) == len(samples)
        for sample, pair in zip(samples, pairs):
            assert not sample['gap']
            difference = abs(Decimal(str(sample['value'])) - Decimal(pair[1]))
            assert difference < Decimal('0.000000001')
        latest[data_name] = samples[-1]['value']
    return latest


def assert_following(client):
    frame = client.frame('board')
    entries = {entry['id']: entry for entry in frame['instances']}
    for panel, data in [('ratePanel', 'rateData'),
                        ('errorsPanel', 'errorsData'),
                        ('latencyPanel', 'latencyData')]:
        shown = entries[client.names[panel]]
        assert shown['inputReference']['kind'] == 'current'
        assert shown['input']['data'] == client.value(data)['data']
        assert shown['inputDelivery'] == 'finite'
        assert not shown['inputProblem']
    group = entries[client.names['board']]
    assert group['inputReference']['kind'] == 'current'
    assert group['input']['data'] == client.value('groupData')['data']
    assert group['input']['data']['range'] == client.value('window')['data']
    return entries


def assert_read_only_reopen(client):
    names = ['clock', 'rateRaw', 'errorsRaw', 'p95Raw']
    before = {name: client.ready[client.names[name]]['_serial'] for name in names}
    client.frame('board')
    node = client.names['board']
    identity = client.value('board')['data']['instance']
    token = client.mounts.pop((node, identity))
    client.request(f'/view-mounts/{node}/{identity}',
                   {'action': 'close', 'token': token})
    assert_following(client)
    time.sleep(.4)
    assert before == {name: client.ready[client.names[name]]['_serial']
                      for name in names}, 'Opening a panel replayed an external read'


def assert_documented_programs():
    blocks = re.findall(r'```wes\n(.*?)\n```', (HERE / 'README.md').read_text(),
                        re.DOTALL)
    programs = {path.read_text().strip() for path in HERE.glob('*.wes')}
    assert blocks and all(block.strip() in programs for block in blocks), (
        'Every Wes code block must match a checked chapter program')


def read_board(client, name):
    client.submit(':inspect $board > ' + name)
    return client.value(name)['data']['view']


def refresh(client, socket):
    # Keep the same display lease alive during execution, as an open GUI does.
    # Reading only after completion misses observation failures during refresh.
    client.frame('board')

    def execute():
        after = client.serial
        program(client, 'refresh.wes', socket)
        client.value('clock', after=after)
        for name in ['rateData', 'errorsData', 'latencyData']:
            client.value(name, after=after)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(execute)
        while not pending.done():
            for shown in client.frame('board')['instances']:
                if shown['inputReference']['kind'] == 'current':
                    assert shown['observing'], shown['inputProblem']
                    assert shown['inputProblem'] in (
                        None, 'Waiting for the current source result')
            time.sleep(.05)
        pending.result()
    assert_following(client)
    return assert_snapshots(client)


def offline_cases(binary, work):
    load = '\n'.join(command for command in commands(
        (HERE / 'helpers.wes').read_text())
        if not command.startswith(':def PromRange')) + '\n'
    body = {'status': 'success', 'data': {'resultType': 'matrix', 'result': [
        {'metric': {}, 'values': [[1, 'NaN'], [2, '1.25'], [3, '9']]}]}}
    source = load + '\n:calc pure { return parseJson(' + json.dumps(
        json.dumps(body)) + '); } > body\n'
    source += ':calc pure { return interval(fromEpochSeconds(1), '
    source += 'fromEpochSeconds(3)); } > span\n'
    source += ':calc pure { return {id:"gaps",title:"Gap",unit:"ms"}; } > p\n'
    source += 'Draw input:$body span:$span p:$p > drawn\n'
    with tempfile.TemporaryDirectory(prefix='wes-prom-adapter-') as home:
        result = subprocess.run(
            [str(binary), '--home', home, '--sequential', '--command', source],
            cwd=work, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        values = [json.loads(l.partition(': ')[2]) for l in
                  result.stdout.splitlines() if l.startswith('id') and ': ' in l]
        samples = values[-1]['series'][0]['samples']
        assert len(samples) == 2 and samples[0]['gap']
        assert samples[1]['value'] == 1.25
    cases = [
        (source.replace('\\"NaN\\"', '\\"+Inf\\"'), 'CAL016'),
        (source.replace('\\"matrix\\"', '\\"vector\\"'), 'TYP005'),
        (load + '\n:calc pure { return {view:"timeline",id:"empty",'
         'title:"Empty",range:interval(fromEpochSeconds(1),fromEpochSeconds(2)),'
         'coverage:interval(fromEpochSeconds(1),fromEpochSeconds(2)),omitted:0,'
         'sourceError:"",series:[],events:[]}; } > noData\n'
         ':calc pure { return {title:"Empty",unit:"ms"}; } > plot\n'
         'Latest input:$noData plot:$plot', 'TYP005'),
    ]
    for bad, code in cases:
        with tempfile.TemporaryDirectory(prefix='wes-prom-refusal-') as home:
            result = subprocess.run(
                [str(binary), '--home', home, '--sequential', '--command', bad],
                cwd=work, capture_output=True, text=True, timeout=30)
            assert result.returncode != 0 and code in (
                result.stdout + result.stderr), result.stdout + result.stderr


def burst():
    def one(_):
        with OPENER.open(API + '/work', timeout=5) as response:
            assert response.status == 200
            response.read()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(one, range(600)))


def main():
    assert_documented_programs()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    parser.add_argument('--socket', default=os.environ.get('WES_DOCKER_SOCKET', '/var/run/docker.sock'))
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--site', type=Path, default=Path(os.environ.get(
        'WES_SITE', WES_CHECKOUT / 'gui/dist')))
    args = parser.parse_args()
    binary = args.binary.resolve()
    if shutil.which('docker') is None:
        print('SKIP tutorial 14: Docker is not installed')
        return
    daemon = subprocess.run(['docker', 'info'], capture_output=True, timeout=15)
    if daemon.returncode:
        print('SKIP tutorial 14: the Docker daemon is not available')
        return
    if not Path(args.socket).is_socket():
        print('SKIP tutorial 14: a local Unix Docker socket is required; '
              'select its path with --socket')
        return
    assert binary.is_file(), 'Build Wes or select it with --binary / WES'
    for key, expected in [('WES14_ORDERS_API_PORT', '18770'),
                          ('WES14_PROMETHEUS_PORT', '19091')]:
        assert os.environ.get(key, expected) == expected, (
            'The checked chapter uses the default lab ports')
    existing = subprocess.run(COMPOSE + ['ps', '-a', '-q'],
                              capture_output=True, text=True, timeout=15)
    assert existing.returncode == 0, existing.stderr
    started = not bool(existing.stdout.strip())
    original_mode = None
    client = None
    try:
        subprocess.run(['sh', str(LAB / 'setup.sh')], check=True,
                       capture_output=True, text=True, timeout=600)
        original_mode = request(API + '/profile')['mode']
        request(API + '/profile', {'mode': 'healthy'})
        eventually(lambda: query('sum(rate(wes_demo_requests_total{'
                    'status="503"}[10s]))')['data']['result'][0]['value'][1]
                   == '0')
        with tempfile.TemporaryDirectory(prefix='wes-tutorial-14-') as home, ExitStack() as cleanup:
            work = Path(home)
            shutil.copytree(HERE, work / '14-prom', ignore=shutil.ignore_patterns(
                '.state', '__pycache__', '*.gif'))
            (work / '14-prom/lab/.state').mkdir()
            offline_cases(binary, work)
            artifact = work / '14-prom/lab/.state/container-resources.wes-view.json'
            source = work / '14-prom/container-resources'
            validator = Path(os.environ.get('WES_VIEW_CONTRACT_TOOL',
                str(binary.with_name('wes-view-build'))))
            assert validator.is_file(), 'Select WES_VIEW_CONTRACT_TOOL'
            env = dict(os.environ, WES_VIEW_CONTRACT_TOOL=str(validator))
            built = subprocess.run(
                ['node', str(WES_CHECKOUT / 'tools/view-package/index.mjs'),
                 'build', str(source), str(artifact)],
                capture_output=True, text=True, timeout=90, env=env)
            assert built.returncode == 0, built.stdout + built.stderr
            client = Client(binary, work, site=(args.site.resolve()
                            if args.preview else None))
            cleanup.callback(client.close)
            for name in FILES:
                program(client, name, args.socket)
            healthy = assert_snapshots(client)
            initial = assert_following(client)
            assert_read_only_reopen(client)
            panel_handles = {name: client.ready[client.names[name]]['handle']
                          for name in ['ratePanel', 'errorsPanel',
                                       'latencyPanel']}
            assert 'Draw' in json.dumps(client.value('adapters')['data'])
            assert healthy['rateData'] > 0 and healthy['errorsData'] == 0
            assert healthy['latencyData'] > 0
            board = client.value('boardInfo')['data']['view']
            assert board['definition'] == 'TimelineGroup'
            assert board['revision'] == '3'
            assert len(board['members']['members']) == 3
            program(client, 'empty.wes', args.socket)
            assert client.value('empty')['data']['status'] == 200
            assert client.value('emptyData')['data']['series'] == []
            program(client, 'bad-query.wes', args.socket)
            bad = client.value('badQuery')['data']
            assert bad['status'] == 400 and bad['body']['errorType'] == 'bad_data'
            assert bad['body']['error'].endswith(
                '1:5: parse error: unclosed left parenthesis')
            client.submit(':help demo setProfile > mutationHelp')
            assert 'UNSAFE' in json.dumps(client.value('mutationHelp')['data'])
            program(client, 'logs.wes', args.socket)
            program(client, 'log-summary.wes', args.socket)
            rows = client.value('logs', lambda r: len(r) > 20)['data']
            exact_id = client.value('containerId')['data']
            assert len(exact_id) == 64
            assert all(r['container'] == exact_id for r in rows)
            program(client, 'stats.wes', args.socket)
            client.value('stats', lambda rows: len(rows) > 0)
            program(client, 'resource-data.wes', args.socket)
            resource = client.value('resources')['data']
            sample = resource['sample']['value']
            stats = client.value('stats', lambda rows: any(
                row['sequence'] == sample['sequence'] for row in rows))['data']
            measured = next(row for row in stats
                            if row['sequence'] == sample['sequence'])
            assert resource['container'] == exact_id == measured['container']
            fields = {
                'cpuPercent': 'cpu_percent',
                'cpuUnavailable': 'cpu_unavailable',
                'onlineCpus': 'online_cpus',
                'memoryWorkingSetBytes': 'memory_working_set_bytes',
                'memoryLimitBytes': 'memory_limit_bytes',
                'memoryPercent': 'memory_percent',
                'memoryUnavailable': 'memory_unavailable',
                'memoryCacheSource': 'memory_cache_source',
            }
            assert all(sample[dest] == measured[src]
                       for dest, src in fields.items())
            resource_frame = client.frame('resourcePanel')['instances'][0]
            assert resource_frame['inputReference']['kind'] == 'current'
            # The renderer gets one record; delivery still carries the bounded
            # stream provenance of its upstream Docker stats source.
            assert resource_frame['inputDelivery'] == 'window', resource_frame
            resource_handle = client.ready[client.names['resourcePanel']]['handle']
            client.value('resources', lambda value:
                         value['sample']['value']['sequence'] > sample['sequence'])
            assert (client.ready[client.names['resourcePanel']]['handle'] ==
                    resource_handle), 'A stats sample recreated the view'
            clock = client.value('clock')['data']
            program(client, 'degrade.wes', args.socket)
            assert client.value('degraded')['data']['body']['mode'] == 'degraded'
            client.value('logs', lambda rows: any(r['stream'] == 'stderr' and
                         'GET /work 503 ' in r['text'] for r in rows))
            def degraded_ready():
                q = '100 * sum(rate(wes_demo_requests_total{status="503"}'
                q += '[10s] offset 2s)) / sum(rate('
                q += 'wes_demo_requests_total[10s] offset 2s))'
                rows = query(q)['data']['result']
                return rows and float(rows[0]['value'][1]) >= 15
            eventually(degraded_ready)
            assert client.value('clock')['data'] == clock, (
                'A live log event unexpectedly refreshed the finite query')
            degraded = refresh(client, args.socket)
            assert degraded['errorsData'] > 0
            assert degraded['latencyData'] > healthy['latencyData']
            after = read_board(client, 'afterDegrade')
            assert after['id'] == board['id'] and after['revision'] == '3'
            assert after['members'] == board['members']
            program(client, 'recover.wes', args.socket)
            assert client.value('recovered')['data']['body']['mode'] == 'healthy'
            def recovered_ready():
                rows = query('sum(rate(wes_demo_requests_total{status="503"}'
                             '[10s] offset 2s))')['data']['result']
                return rows and rows[0]['value'][1] == '0'
            eventually(recovered_ready)
            recovered = refresh(client, args.socket)
            assert recovered['errorsData'] == 0
            assert recovered['latencyData'] < degraded['latencyData']
            old_errors = client.frame('board')['instances']
            old_errors = next(e['input']['data'] for e in old_errors
                              if e['id'] == client.names['errorsPanel'])
            program(client, 'pin.wes', args.socket)
            kept = client.value('incident')['data']
            assert kept == old_errors
            pinned = client.frame('board')
            pinned = next(e for e in pinned['instances']
                          if e['id'] == client.names['errorsPanel'])
            assert pinned['inputReference']['kind'] == 'retained'
            after_pin = client.serial
            program(client, 'refresh.wes', args.socket)
            client.value('latencyData', after=after_pin)
            client.value('errorsData', after=after_pin)
            rate = client.value('rateData', after=after_pin)['data']

            def pinned_refresh_delivered():
                # Provider completion and delivery to its mounted views are
                # separate events. Wait for the new input, not a fixed delay.
                shown = {e['id']: e for e in client.frame('board')['instances']}
                pinned = shown[client.names['errorsPanel']]
                assert pinned['inputReference']['kind'] == 'retained'
                assert pinned['input']['data'] == kept
                current = shown[client.names['ratePanel']]
                assert current['observing'], current['inputProblem']
                assert current['inputProblem'] in (
                    None, 'Waiting for the current source result')
                return shown if current.get('input', {}).get('data') == rate else None

            entries = eventually(pinned_refresh_delivered)
            assert entries[client.names['errorsPanel']]['input']['data'] == kept
            assert entries[client.names['ratePanel']]['input']['data'] == rate
            program(client, 'follow.wes', args.socket)
            assert_following(client)
            for name, handle in panel_handles.items():
                assert client.ready[client.names[name]]['handle'] == handle
            for name in ['ratePanel', 'errorsPanel', 'latencyPanel']:
                info = client.value(name)['data']
                assert initial[client.names[name]]['instance'] == info['instance']
            first_last = client.value('logs')['data'][-1]['sequence']
            burst()
            try:
                rows = client.value('logs', lambda r: len(r) == 500 and
                            r[-1]['sequence'] >= first_last + 600, timeout=30)['data']
            except AssertionError as error:
                last = client.value('logs')['data']
                raise AssertionError(f'Log window: {len(last)} rows, sequences '
                    f'{last[0]["sequence"]}..{last[-1]["sequence"]}; '
                    f'expected last >= {first_last + 600}') from error
            assert rows[0]['sequence'] > 1
            assert all(not (r['partial'] or r['lossy'] or r['line_truncated'])
                       for r in rows)
            summary = client.value('logSummary')['data']
            rows = client.value('logs', lambda r:
                     r[-1]['sequence'] >= summary['last'])['data']
            selected = [r for r in rows if summary['last'] - 20 <
                        r['sequence'] <= summary['last']]
            assert summary['analyzed'] == len(selected) == 20
            assert summary['errors'] == sum('GET /work 503 ' in r['text']
                                             for r in selected)
            program(client, 'cancel.wes', args.socket)
            for name in ['logs', 'logSummary', 'stats', 'resources']:
                client.wait(lambda: client.ready.get(client.names[name],
                                {}).get('event') == 'stopped')
            stopped = client.value('logs')['data']
            time.sleep(.5)
            assert client.value('logs')['data'] == stopped
            assert query('up{job="orders-api"}')['data']['result'][0]['value'][1] == '1'
            print('PASS tutorial 14: real Prometheus responses, exact adapters, '
                  'three coordinated Timeline members, exact live Docker resource '
                  'readings, Current following without rebind, '
                  'stable presentation constructors, Pin/follow, healthy/degraded/'
                  'recovered, live stdout/stderr, 500-event window and cancel',
                  flush=True)
            if args.preview:
                assert (args.site / 'index.html').is_file(), 'Build the GUI first'
                client.submit(':refresh $logs scope:downstream')
                client.value('logs', lambda r: len(r) > 0)
                serial = client.serial
                client.submit(':refresh $stats scope:downstream')
                client.value('resources', after=serial)
                definition = work / 'dashboard.json'
                definition.write_text(json.dumps(dashboard_definition(client),
                                                 indent=2) + '\n')
                print('Preview: ' + client.url, flush=True)
                print('Dashboard definition: ' + str(definition), flush=True)
                print('Enter /dashboard, Import definition, paste that file, '
                      'Load draft, Save, then /tabx $orders. '
                      'Ctrl+C stops this preview.', flush=True)
                try:
                    while client.process.poll() is None:
                        time.sleep(.5)
                except KeyboardInterrupt:
                    pass
    finally:
        if not started and original_mode is not None:
            request(API + '/profile', {'mode': original_mode})
        if started:
            subprocess.run(['sh', str(LAB / 'teardown.sh')], check=True,
                           capture_output=True, text=True, timeout=60)


if __name__ == '__main__':
    main()
