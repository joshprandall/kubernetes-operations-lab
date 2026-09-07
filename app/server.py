"""Small, dependency-free HTTP service for a local Kubernetes teaching lab."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import threading
import time
from urllib.parse import urlsplit


class LabServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, marker, version='v1', message='Operations lab'):
        super().__init__(address, Handler)
        self.marker = Path(marker)
        self.version = version
        self.message = message
        self.started = time.monotonic()
        self.requests_total = 0
        self.lock = threading.Lock()
        self.draining = False


class Handler(BaseHTTPRequestHandler):
    server_version = 'OperationsLab/1'
    sys_version = ''

    def do_GET(self):
        with self.server.lock:
            self.server.requests_total += 1
            total = self.server.requests_total
        path = urlsplit(self.path).path
        status = 200
        content_type = 'application/json; charset=utf-8'
        if path == '/healthz':
            payload = {'alive': True}
        elif path == '/readyz':
            ready = not self.server.draining and not self.server.marker.exists()
            status = 200 if ready else 503
            payload = {'ready': ready}
        elif path in ('/', '/api/status'):
            payload = {'service': 'operations-lab', 'version': self.server.version,
                       'message': self.server.message, 'pod': socket.gethostname(),
                       'uptime_seconds': round(time.monotonic() - self.server.started, 3)}
        elif path == '/metrics':
            content_type = 'text/plain; version=0.0.4; charset=utf-8'
            payload = '# HELP lab_http_requests_total GET requests including probes and scrapes.\n# TYPE lab_http_requests_total counter\nlab_http_requests_total ' + str(total) + '\n'
        else:
            status = 404
            payload = {'error': 'not_found'}
        body = (payload if isinstance(payload, str) else json.dumps(payload)).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)
        print(json.dumps({'event': 'request', 'path': path, 'status': status}), flush=True)

    def log_message(self, *_):
        pass


def main():
    server = LabServer(('0.0.0.0', int(os.getenv('PORT', '8080'))),
                       os.getenv('READINESS_MARKER', '/tmp/not-ready'),
                       os.getenv('APP_VERSION', 'v1'), os.getenv('APP_MESSAGE', 'Operations lab'))
    def stop(*_):
        server.draining = True
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json.dumps({'event': 'started', 'port': server.server_port, 'version': server.version}), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
