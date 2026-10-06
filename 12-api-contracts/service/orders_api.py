#!/usr/bin/env python3
"""Synthetic orders-api for tutorial chapters 12 and 13; listens on loopback only.

Usage: python3 orders_api.py [--port 8770]
The credentials it accepts are public tutorial values, not secrets.
"""
import argparse
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

DEFAULT_PORT = 8770
OPS_TOKEN = 'tutorial-ops-token'
OPS_USER = 'ops'
OPS_PASSWORD = 'tutorial-pass'
ORDERS = [
    {'id': 4, 'status': 'open', 'totalCents': 1250},
    {'id': 3, 'status': 'failed', 'totalCents': 7500},
    {'id': 2, 'status': 'shipped', 'totalCents': 1999},
    {'id': 1, 'status': 'open', 'totalCents': 4200},
]
REFUNDS = [{'orderId': 3, 'amountCents': 7500}]


def authorized(header):
    basic = base64.b64encode(f'{OPS_USER}:{OPS_PASSWORD}'.encode()).decode()
    return header in (f'Bearer {OPS_TOKEN}', f'Basic {basic}')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = urlsplit(self.path)
        query = parse_qs(route.query)
        # Record the request without credential values, for the chapter checks.
        self.server.requests.append({'path': self.path,
                                     'authorized': authorized(self.headers.get('Authorization'))})
        if route.path == '/health':
            return self.reply(200, {'status': 'ok', 'version': '1.4.0'})
        if route.path == '/orders':
            status = query.get('status', [None])[0]
            limit = int(query.get('limit', ['50'])[0])
            return self.reply(200, [o for o in ORDERS if status in (None, o['status'])][:limit])
        if route.path.startswith('/orders/'):
            found = [o for o in ORDERS if str(o['id']) == route.path.rsplit('/', 1)[1]]
            return self.reply(200, found[0]) if found else self.reply(404, {'error': 'unknown order'})
        if route.path == '/refunds':
            if not authorized(self.headers.get('Authorization')):
                return self.reply(401, {'error': 'missing or invalid credentials'})
            return self.reply(200, REFUNDS[:int(query.get('limit', ['50'])[0])])
        return self.reply(404, {'error': 'no route'})


def make_server(port):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.requests = []
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    with make_server(parser.parse_args().port) as server:
        print(f'orders-api listening on http://127.0.0.1:{server.server_port}', file=sys.stderr, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
