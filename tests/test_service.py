import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from server import LabServer


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.marker = Path(self.temp.name) / 'not-ready'
        self.server = LabServer(('127.0.0.1', 0), self.marker, 'test-version', 'A "quoted" message')
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_health(self):
        self.assertEqual(self.get('/healthz')[0], 200)

    def test_ready_default(self):
        self.assertTrue(json.loads(self.get('/readyz')[2])['ready'])

    def test_readiness_marker_and_recovery(self):
        self.marker.touch()
        self.assertEqual(self.get('/readyz')[0], 503)
        self.marker.unlink()
        self.assertEqual(self.get('/readyz')[0], 200)

    def test_readiness_does_not_change_liveness(self):
        self.marker.touch()
        self.assertEqual(self.get('/healthz')[0], 200)

    def test_draining_unready(self):
        self.server.draining = True
        self.assertEqual(self.get('/readyz')[0], 503)

    def test_status_config(self):
        value = json.loads(self.get('/api/status')[2])
        self.assertEqual(value['version'], 'test-version')
        self.assertEqual(value['message'], 'A "quoted" message')
        self.assertGreaterEqual(value['uptime_seconds'], 0)

    def test_root_status(self):
        self.assertEqual(json.loads(self.get('/')[2])['service'], 'operations-lab')

    def test_query_string(self):
        self.assertEqual(self.get('/healthz?probe=1')[0], 200)

    def test_unknown_path(self):
        status, _, body = self.get('/missing')
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)['error'], 'not_found')

    def test_metrics_counter(self):
        self.get('/healthz')
        status, headers, body = self.get('/metrics')
        self.assertEqual(status, 200)
        self.assertIn(b'lab_http_requests_total 2\n', body)
        self.assertIn('text/plain', headers['Content-Type'])

    def test_json_response_headers(self):
        _, headers, body = self.get('/api/status')
        self.assertEqual(int(headers['Content-Length']), len(body))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_no_remote_failure_switch(self):
        self.assertEqual(self.get('/fail')[0], 404)
        self.assertEqual(self.get('/readyz')[0], 200)


if __name__ == '__main__':
    unittest.main()
