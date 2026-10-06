#!/usr/bin/env python3
"""Synthetic orders-api for tutorial chapter 14, instrumented for Prometheus.

GET /work is the only instrumented endpoint; the workload calls it. GET /health,
GET /metrics and GET/POST /profile are neither counted nor timed.

Every completed GET /work request writes one log line: the UTC completion time,
the request, its HTTP status, its measured duration and the mode it ran in.
200 lines go to stdout, 503 lines to stderr. Profile changes log one line on
stderr.

Usage: python3 orders_api.py [--host 127.0.0.1] [--port 8080] [--mode healthy]
"""
import argparse
import json
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SERVICE = 'orders-api'
MODES = ('healthy', 'degraded')
# Work simulated per request. The histogram records the measured duration,
# not these values.
DELAY_SECONDS = {'healthy': 0.01, 'degraded': 0.12}
# In degraded mode every FAILURE_EVERY-th request answers 503.
FAILURE_EVERY = 4
BUCKETS = ('0.005', '0.01', '0.025', '0.05', '0.1', '0.125', '0.15', '0.2',
           '0.25', '0.5', '1')
MAX_BODY = 1024
ROUTES = {
    '/health': ('GET',),
    '/metrics': ('GET',),
    '/work': ('GET',),
    '/profile': ('GET', 'POST'),
}
# One lock for both streams, so lines from concurrent requests never interleave.
LOG_LOCK = threading.Lock()


def log(stream, message):
    """Writes one line prefixed with the current UTC time, then flushes."""
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    line = f'{now.replace("+00:00", "Z")} {message}\n'
    with LOG_LOCK:
        stream.write(line)
        stream.flush()


class State:
    """Mode and metrics, shared by all request threads."""

    def __init__(self, mode):
        self.lock = threading.Lock()
        self.mode = mode
        self.degraded_requests = 0
        # Both series exist from the start, so an error ratio is 0, not empty.
        self.requests = {'200': 0, '503': 0}
        self.buckets = [0] * len(BUCKETS)
        self.duration_sum = 0.0
        self.duration_count = 0

    def get_mode(self):
        with self.lock:
            return self.mode

    def set_mode(self, mode):
        """Returns the previous and the new mode."""
        with self.lock:
            previous, self.mode = self.mode, mode
            return previous, self.mode

    def begin(self):
        """Returns the mode, delay and status of one /work request."""
        with self.lock:
            mode = self.mode
            if mode == 'healthy':
                return mode, DELAY_SECONDS[mode], 200
            self.degraded_requests += 1
            failed = self.degraded_requests % FAILURE_EVERY == 0
            return mode, DELAY_SECONDS[mode], 503 if failed else 200

    def observe(self, status, seconds):
        with self.lock:
            self.requests[str(status)] += 1
            for i, bound in enumerate(BUCKETS):
                if seconds <= float(bound):
                    self.buckets[i] += 1
            self.duration_sum += seconds
            self.duration_count += 1

    def exposition(self):
        """Prometheus text format 0.0.4."""
        labels = f'service="{SERVICE}"'
        counter = 'wes_demo_requests_total'
        histogram = 'wes_demo_request_duration_seconds'
        with self.lock:
            lines = [
                f'# HELP {counter} GET /work requests whose response was'
                ' sent, by HTTP status. Other endpoints are not counted.',
                f'# TYPE {counter} counter',
            ]
            for status in sorted(self.requests):
                lines.append(f'{counter}{{{labels},status="{status}"}}'
                             f' {self.requests[status]}')
            lines += [
                f'# HELP {histogram} Time orders-api spent on GET /work'
                ' requests whose response was sent, from routing to the'
                ' flushed response, in seconds.',
                f'# TYPE {histogram} histogram',
            ]
            for bound, count in zip(BUCKETS, self.buckets):
                lines.append(
                    f'{histogram}_bucket{{{labels},le="{bound}"}} {count}')
            lines.append(f'{histogram}_bucket{{{labels},le="+Inf"}}'
                         f' {self.duration_count}')
            lines.append(f'{histogram}_sum{{{labels}}} {self.duration_sum!r}')
            lines.append(
                f'{histogram}_count{{{labels}}} {self.duration_count}')
        return '\n'.join(lines) + '\n'


class Handler(BaseHTTPRequestHandler):
    server_version = 'orders-api/1.0'
    sys_version = ''
    # Seconds a client may take to send its request; a slow client is
    # disconnected.
    timeout = 5

    def log_message(self, *_):
        pass

    def send(self, status, content_type, data, headers=()):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def reply(self, status, body, headers=()):
        data = json.dumps(body).encode()
        self.send(status, 'application/json', data, headers)

    def dispatch(self, method):
        path = urlsplit(self.path).path
        allowed = ROUTES.get(path)
        if allowed is None:
            return self.reply(404, {'error': f'no route {path}'})
        if method not in allowed:
            return self.reply(405,
                              {'error': f'{method} is not allowed on {path}'},
                              [('Allow', ', '.join(allowed))])
        state = self.server.state
        if path == '/health':
            return self.reply(200, {'status': 'ok', 'mode': state.get_mode()})
        if path == '/metrics':
            return self.send(200, 'text/plain; version=0.0.4; charset=utf-8',
                             state.exposition().encode())
        if path == '/work':
            return self.work(state)
        if method == 'GET':
            return self.reply(200, {'mode': state.get_mode()})
        return self.set_profile(state)

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def do_PUT(self):
        self.dispatch('PUT')

    def do_DELETE(self):
        self.dispatch('DELETE')

    def work(self, state):
        start = time.perf_counter()
        mode, delay, status = state.begin()
        time.sleep(delay)
        if status == 200:
            body = {'ok': True}
        else:
            body = {'error': 'orders-api is degraded'}
        try:
            self.reply(status, body)
            self.wfile.flush()
        except OSError:
            return  # The client left; the request did not complete.
        seconds = time.perf_counter() - start
        state.observe(status, seconds)
        stream = sys.stdout if status == 200 else sys.stderr
        log(stream,
            f'GET /work {status} {seconds * 1000:.1f}ms mode={mode}')

    def set_profile(self, state):
        content_type = self.headers.get('Content-Type', '')
        if content_type.split(';')[0].strip().lower() != 'application/json':
            return self.reply(
                415, {'error': 'Content-Type must be application/json'})
        length = self.headers.get('Content-Length', '')
        if not (length.isascii() and length.isdigit()):
            return self.reply(411, {'error': 'Content-Length is required'})
        if len(length) > len(str(MAX_BODY)) or int(length) > MAX_BODY:
            return self.reply(413, {'error': f'body exceeds {MAX_BODY} bytes'})
        try:
            body = json.loads(self.rfile.read(int(length)))
        except ValueError:
            return self.reply(400, {'error': 'body is not valid JSON'})
        if (not isinstance(body, dict) or set(body) != {'mode'}
                or body['mode'] not in MODES):
            return self.reply(400, {'error': 'body must be {"mode": "healthy"}'
                                             ' or {"mode": "degraded"}'})
        previous, mode = state.set_mode(body['mode'])
        log(sys.stderr, f'POST /profile mode {previous} -> {mode}')
        return self.reply(200, {'mode': mode})


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--mode', choices=MODES, default='healthy')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = State(args.mode)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log(sys.stderr, f'{SERVICE} listening on {args.host}:{server.server_port}'
                    f' in {args.mode} mode')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
