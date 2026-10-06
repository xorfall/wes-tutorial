"""Disposable loopback Wes client used by the Prometheus chapter check."""
from collections import deque
import json
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid


class Client:
    def __init__(self, binary, root, site=None, environment="default"):
        self.environment = environment
        self.changed = threading.Condition()
        self.events = deque(maxlen=2000)
        self.names, self.ready = {}, {}
        self.generation = None
        self.context = None
        self.problem = None
        self.closed = False
        self.serial = 0
        self.root = root
        self.mounts = {}
        self.errors = open(root / 'engine.stderr', 'w+')
        args = [str(binary), '--home', str(root / 'home'), '--serve', '0', '--no-auto-keep']
        if site:
            args += ['--site', str(site)]
        self.process = subprocess.Popen(args, cwd=root, text=True, stdout=subprocess.PIPE, stderr=self.errors)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                if not selector.select(30):
                    raise RuntimeError('Engine startup timed out')
            line = self.process.stdout.readline().strip()
            if not line.startswith('Listening at http://'):
                self.errors.seek(0)
                raise RuntimeError(line + self.errors.read())
            self.url = line.removeprefix('Listening at ')
            self.stream = urllib.request.urlopen(self.url + '/events', timeout=30)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self.wait(lambda: self.generation)
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for raw in self.stream:
                if not raw.startswith(b'data:'):
                    continue
                event = json.loads(raw[5:])
                with self.changed:
                    self.serial += 1
                    event['_serial'] = self.serial
                    self.events.append(event)
                    kind = event['event']
                    if kind == 'session':
                        self.generation = event['generation']
                        self.names.clear()
                        self.ready.clear()
                    elif kind == 'environments':
                        self.context = ({'selected': self.environment, 'revisions': event['revisions']}
                                        if self.environment in event['revisions'] else None)
                    elif kind == 'created' and event.get('name'):
                        self.names[event['name']] = event['node']
                    elif kind in ('ready', 'stopped'):
                        self.ready[event['node']] = event
                    elif kind == 'reported' and any(d.get('severity') == 'error' for d in event.get('diagnostics', [])):
                        self.problem = str(event)
                    elif kind == 'failed':
                        self.problem = str(event)
                    self.changed.notify_all()
        except Exception as error:
            with self.changed:
                if not self.closed:
                    self.problem = repr(error)
                self.changed.notify_all()

    def wait(self, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        with self.changed:
            while True:
                if self.problem:
                    raise AssertionError(self.problem)
                value = predicate()
                if value:
                    return value
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f'Timed out; recent events: {list(self.events)[-12:]}')
                self.changed.wait(min(remaining, .1))

    def submit(self, text, switch=False):
        cell = str(uuid.uuid4())
        before = self.generation
        self.post({
            'request': 'submit', 'cell': cell, 'text': text,
            'client': 'prometheus-tutorial-check', 'environments': self.context,
        })
        result = self.wait(lambda: next((e for e in self.events if e['event'] == 'planned' and e['cell'] == cell), None)
                           or ({'generation': self.generation} if switch and self.generation != before else None))
        assert not result.get('failure'), result
        return result

    def request(self, path, payload=None, headers=None):
        fields = {'X-Wes-Session': self.generation, **(headers or {})}
        data = None
        if payload is not None:
            fields['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode()
        request = urllib.request.Request(self.url + path, data, fields)
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            return json.loads(body) if body else None

    def post(self, payload):
        return self.request('/submit', payload)

    def frame(self, name):
        handle = self.value(name)['data']
        node, identity = self.names[name], handle['instance']
        path = f'/view-mounts/{node}/{identity}'
        token = self.mounts.get((node, identity))
        if token is None:
            token = self.request(path, {'action': 'open'})['token']
            self.mounts[node, identity] = token
        else:
            try:
                self.request(path, {'action': 'touch', 'token': token})
            except urllib.error.HTTPError as error:
                if error.code != 409:
                    raise
                token = self.request(path, {'action': 'open'})['token']
                self.mounts[node, identity] = token
        return self.request(f'/view-instances/{node}/{identity}',
                            headers={'X-Wes-View-Mount': token})

    def keep(self, name):
        frame = self.wait(lambda: self.ready.get(self.names.get(name)))
        self.post({'request': 'keep', 'handle': frame['handle']})
        self.wait(lambda: self.ready.get(frame['node'], {}).get('kept'))

    def file(self, name):
        return self.submit((self.root / name).read_text())

    def value(self, name, predicate=lambda _: True, after=0, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            def fresh():
                event = self.ready.get(self.names.get(name))
                return event if event and event['_serial'] > after else None
            event = self.wait(fresh, timeout=max(.1, deadline-time.monotonic()))
            try:
                with urllib.request.urlopen(self.url + '/values/' + event['handle'], timeout=10) as response:
                    value = json.load(response)
                if predicate(value['data']):
                    return value
                after = event['_serial']
                continue
            except urllib.error.HTTPError as error:
                if error.code not in (404, 409, 410, 429, 503):
                    raise
            with self.changed:
                self.changed.wait(.03)
        raise AssertionError(f'Timed out reading {name}; last frame: {event}')

    def close(self):
        self.closed = True
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if hasattr(self, 'stream'):
            self.stream.close()
            self.reader.join(timeout=5)
        self.process.stdout.close()
        self.errors.close()
