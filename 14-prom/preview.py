#!/usr/bin/env python3
"""Open the Prometheus dashboard and live logs in a disposable Wes workspace."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from check import (API, COMPOSE, FILES, HERE, LAB, WES_CHECKOUT,
                   default_binary, program, request)
from client import Client
from dashboard import dashboard_definition


def build_panel(binary, work):
    source = work / '14-prom/container-resources'
    artifact = work / '14-prom/lab/.state/container-resources.wes-view.json'
    validator = Path(os.environ.get('WES_VIEW_CONTRACT_TOOL',
                                   str(binary.with_name('wes-view-build'))))
    assert validator.is_file(), 'Build wes-view-build or select WES_VIEW_CONTRACT_TOOL'
    result = subprocess.run(
        ['node', str(WES_CHECKOUT / 'tools/view-package/index.mjs'),
         'build', str(source), str(artifact)],
        env={**os.environ, 'WES_VIEW_CONTRACT_TOOL': str(validator)},
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=default_binary())
    parser.add_argument('--site', type=Path, default=Path(os.environ.get(
        'WES_SITE', WES_CHECKOUT / 'gui/dist')))
    parser.add_argument('--socket', default=os.environ.get('WES_DOCKER_SOCKET', '/var/run/docker.sock'))
    args = parser.parse_args()
    binary, site = args.binary.resolve(), args.site.resolve()
    assert binary.is_file(), 'Build Wes or select --binary / WES'
    assert (site / 'index.html').is_file(), 'Build the GUI or select --site / WES_SITE'
    assert shutil.which('docker'), 'Docker and Compose are required'
    assert Path(args.socket).is_socket(), 'Select a local Docker Unix socket'
    existing = subprocess.run(COMPOSE + ['ps', '-a', '-q'],
                              capture_output=True, text=True, timeout=15)
    assert existing.returncode == 0, existing.stderr
    started = not bool(existing.stdout.strip())
    client, original_mode = None, None
    try:
        subprocess.run(['sh', str(LAB / 'setup.sh')], check=True)
        original_mode = request(API + '/profile')['mode']
        request(API + '/profile', {'mode': 'healthy'})
        with tempfile.TemporaryDirectory(prefix='wes-prometheus-preview-') as root, ExitStack() as cleanup:
            work = Path(root)
            shutil.copytree(HERE, work / '14-prom', ignore=shutil.ignore_patterns(
                '.state', '__pycache__', '*.gif', '*.png'))
            (work / '14-prom/lab/.state').mkdir()
            build_panel(binary, work)
            client = Client(binary, work, site=site)
            cleanup.callback(client.close)
            for name in FILES:
                program(client, name, args.socket)
            client.value('boardInfo')
            program(client, 'logs.wes', args.socket)
            program(client, 'log-summary.wes', args.socket)
            program(client, 'stats.wes', args.socket)
            client.value('stats', lambda rows: len(rows) > 0)
            program(client, 'resource-data.wes', args.socket)
            client.value('resources')
            client.value('logs', lambda rows: len(rows) > 0)
            definition = work / 'dashboard.json'
            definition.write_text(json.dumps(dashboard_definition(client),
                                              indent=2) + '\n')
            print('Preview: ' + client.url, flush=True)
            print('Dashboard definition: ' + str(definition), flush=True)
            print('Enter /dashboard. Click Import definition, paste that file, '
                  'Load draft, then Save. Enter /tabx $orders to focus the '
                  'saved layout.', flush=True)
            print('Keep the default session tab for commands; optionally '
                  'open /split right to keep it beside the dashboard.', flush=True)
            print('To change the service: demo setProfile body:{mode:"degraded"}. '
                  'After a few scrapes: :refresh $clock scope:downstream.', flush=True)
            print('Ctrl+C stops this workspace and removes its temporary data. '
                  'Only a lab started by this command is stopped.', flush=True)
            while client.process.poll() is None:
                time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        if not started and original_mode is not None:
            request(API + '/profile', {'mode': original_mode})
        if started:
            subprocess.run(['sh', str(LAB / 'teardown.sh')], check=True)


if __name__ == '__main__':
    main()
