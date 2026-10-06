#!/usr/bin/env python3
"""Synthetic workload for tutorial chapter 14: calls GET /work on orders-api in a loop.

One request at a time, --interval seconds apart. Every request is real; orders-api
measures and exports its duration. The workload prints the durations it observed
itself every --report seconds and touches --heartbeat after every HTTP answer.

Usage: python3 workload.py [--url http://127.0.0.1:8080/work] [--interval 0.1]
"""
import argparse
import signal
import sys
import threading
import time
import urllib.error
import urllib.request

# No proxy: container environments may carry proxy settings for outside traffic.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(url, timeout):
    """Returns the HTTP status (None without an answer) and the elapsed seconds."""
    start = time.perf_counter()
    try:
        with OPENER.open(url, timeout=timeout) as response:
            response.read(4096)
            status = response.status
    except urllib.error.HTTPError as error:
        error.close()
        status = error.code
    except OSError:
        status = None
    return status, time.perf_counter() - start


def touch(path):
    with open(path, 'w'):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default='http://127.0.0.1:8080/work')
    parser.add_argument('--interval', type=float, default=0.1)
    parser.add_argument('--timeout', type=float, default=2.0)
    parser.add_argument('--report', type=float, default=10.0)
    parser.add_argument('--heartbeat', default='/tmp/workload-heartbeat')
    args = parser.parse_args()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    print(f'workload calling {args.url} every {args.interval} s', file=sys.stderr, flush=True)
    counts, elapsed = {}, []
    next_report = time.monotonic() + args.report
    while not stop.is_set():
        status, seconds = call(args.url, args.timeout)
        counts[status] = counts.get(status, 0) + 1
        if status is not None:
            elapsed.append(seconds)
            touch(args.heartbeat)
        if time.monotonic() >= next_report:
            summary = ' '.join(f'{key or "no-answer"}={value}' for key, value in sorted(counts.items(), key=str))
            if elapsed:
                summary += f' mean={sum(elapsed) / len(elapsed):.3f}s max={max(elapsed):.3f}s'
            print(f'workload {summary}', flush=True)
            counts, elapsed = {}, []
            next_report = time.monotonic() + args.report
        stop.wait(args.interval if status is not None else 1.0)


if __name__ == '__main__':
    main()
