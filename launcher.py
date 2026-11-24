"""A small, local-first Vizio launcher. Run --help for setup and usage."""
import argparse
import json
import logging
import socket
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
SELECTION = ROOT / 'selection.json'
DEFAULT_APPS = {'youtube': [5, '1'], 'netflix': [3, '1'], 'prime': [3, '3']}
TLS = ssl._create_unverified_context()  # Device-local Vizio certificate is not publicly trusted.


def request_tv(host, path, token='', body=None):
    payload = None if body is None else json.dumps(body).encode()
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['AUTH'] = token
    request = Request('https://' + host + ':7345' + path, data=payload, headers=headers,
                      method='GET' if payload is None else 'PUT')
    with urlopen(request, context=TLS, timeout=5) as response:
        result = json.load(response)
    if result.get('STATUS', {}).get('RESULT', '').upper() != 'SUCCESS':
        raise RuntimeError('TV rejected request: ' + str(result.get('STATUS', {}).get('DETAIL', 'unknown error')))
    return result


def pair(host):
    device_id = 'simple-vizio-' + uuid.uuid4().hex[:16]
    start = request_tv(host, '/pairing/start', body={'DEVICE_NAME': 'Simple Vizio Launcher', 'DEVICE_ID': device_id})
    pin = input('Enter the four-digit code shown on the TV: ').strip()
    if len(pin) != 4 or not pin.isdigit():
        raise ValueError('Expected a four-digit PIN')
    item = start['ITEM']
    result = request_tv(host, '/pairing/pair', body={'DEVICE_ID': device_id, 'CHALLENGE_TYPE': item['CHALLENGE_TYPE'],
                        'PAIRING_REQ_TOKEN': item['PAIRING_REQ_TOKEN'], 'RESPONSE_VALUE': pin})
    config = {'tv_host': host, 'auth_token': result['ITEM']['AUTH_TOKEN'], 'port': 8765,
              'redirect_watchfree': False, 'apps': DEFAULT_APPS}
    CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Paired. Configuration saved locally in config.json. Keep that file private.')


def route_address(host):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((host, 7345))
        return s.getsockname()[0]


class Launcher:
    def __init__(self, config):
        self.config = config
        self.host = config['tv_host']
        self.port = int(config.get('port', 8765))
        self.apps = config.get('apps', DEFAULT_APPS)
        self.lock = threading.Lock()
        self.stock_mode = False
        self.seen_stock = False
        self.pause_until = 0.0

    def call(self, path, body=None):
        return request_tv(self.host, path, self.config['auth_token'], body)

    def launch(self, namespace, app_id, message=None):
        return self.call('/app/launch', {'VALUE': {'NAME_SPACE': namespace, 'APP_ID': str(app_id), 'MESSAGE': message}})

    def tv_is_on(self):
        response = self.call('/state/device/power_mode')
        return any(item.get('CNAME') == 'power_mode' and item.get('VALUE') == 1
                   for item in response.get('ITEMS', []))

    def watcher(self):
        last_home = last_watchfree = 0.0
        while True:
            try:
                if not self.tv_is_on():
                    time.sleep(2)
                    continue
                value = self.call('/app/current').get('ITEM', {}).get('VALUE', {})
                home = value.get('NAME_SPACE') == 4 and value.get('APP_ID') == '1'
                watchfree = value.get('NAME_SPACE') == 4 and value.get('APP_ID') == '3014'
                with self.lock:
                    if self.stock_mode:
                        if home:
                            self.seen_stock = True
                        elif self.seen_stock or time.monotonic() > self.pause_until:
                            self.stock_mode = False
                    redirect = home and not self.stock_mode and time.monotonic() - last_home > 7
                if watchfree and self.config.get('redirect_watchfree', False) and time.monotonic() - last_watchfree > 7:
                    last_watchfree = time.monotonic()
                    self.launch(*self.apps['youtube'])
                    logging.info('WatchFree redirected to YouTube')
                elif redirect:
                    last_home = time.monotonic()
                    self.launch(4, '3001', 'http://%s:%d/' % (route_address(self.host), self.port))
                    logging.info('Opened simple home')
            except (OSError, ValueError, KeyError, RuntimeError, URLError) as exc:
                logging.debug('TV unavailable: %s', type(exc).__name__)
            time.sleep(2)

    def open_stock(self):
        with self.lock:
            self.stock_mode, self.seen_stock = True, False
            self.pause_until = time.monotonic() + 30
        try:
            self.call('/key_command/', {'KEYLIST': [{'CODESET': 4, 'CODE': 15, 'ACTION': 'KEYPRESS'}]})
        except Exception:
            with self.lock:
                self.stock_mode = False
            raise


def serve(config):
    launcher = Launcher(config)
    bind_address = route_address(launcher.host)

    class Handler(BaseHTTPRequestHandler):
        def allowed(self):
            # IP is a basic restriction, not strong authentication. Use only a trusted LAN.
            return self.client_address[0] == launcher.host

        def reply(self, status, data=b'', kind='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

        def do_GET(self):
            if not self.allowed() or self.path not in ('/', '/selection'):
                self.send_error(404); return
            if self.path == '/':
                self.reply(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8'); return
            try:
                app = json.loads(SELECTION.read_text(encoding='utf-8')).get('app', 'youtube')
            except (OSError, ValueError):
                app = 'youtube'
            self.reply(200, json.dumps({'app': app if app in launcher.apps else 'youtube'}).encode())

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.allowed() or self.path not in ('/launch', '/selection') or origin != 'http://%s:%d' % (bind_address, launcher.port):
                self.send_error(403); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512:
                    raise ValueError('Invalid request')
                app = json.loads(self.rfile.read(length))['app']
                if self.path == '/selection':
                    if app not in launcher.apps: raise ValueError('Unknown app')
                    SELECTION.write_text(json.dumps({'app': app}), encoding='utf-8')
                elif app == 'stock':
                    launcher.open_stock()
                else:
                    launcher.launch(*launcher.apps[app])
                self.reply(204)
            except (OSError, KeyError, ValueError, RuntimeError, URLError):
                self.send_error(400)

        def log_message(self, fmt, *args):
            logging.debug(fmt, *args)

    server = ThreadingHTTPServer((bind_address, launcher.port), Handler)
    threading.Thread(target=launcher.watcher, daemon=True).start()
    logging.info('Serving the launcher on %s:%s', bind_address, launcher.port)
    print('Launcher running. Press Ctrl+C to stop.', flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('pair', help='pair with a TV and save private configuration')
    p.add_argument('tv_ip', help='TV local IPv4 address')
    commands.add_parser('run', help='run the launcher until stopped')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    if args.command == 'pair':
        if CONFIG.exists():
            parser.error('config.json already exists; back it up or move it before pairing again')
        socket.inet_aton(args.tv_ip)
        pair(args.tv_ip)
    else:
        if not CONFIG.exists():
            parser.error('Pair first: python launcher.py pair TV_IP')
        serve(json.loads(CONFIG.read_text(encoding='utf-8')))

if __name__ == '__main__':
    main()
