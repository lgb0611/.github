"""Exercise the free server over real loopback HTTP, without optional dependencies."""
import http.client
import json
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from free_server import FreeHandler


class FreeServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), FreeHandler)
        cls.worker = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.worker.join(2)

    def request(self, path, method='GET', headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        c.request(method, path, headers=headers or {})
        r = c.getresponse()
        status, body = r.status, r.read()
        c.close()
        return status, body

    def test_free_page_and_config(self):
        status, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('말한 답변 자가 점검'.encode(), body)
        status, body = self.request('/api/config')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data['server'])
        self.assertTrue(data['free_only'])
        self.assertFalse(data['connected'])
        self.assertIn('youtube_available', data)
        self.assertIn('youtube_token', data)

    def test_paid_endpoints_rejected(self):
        for path in ['/api/grade', '/api/transcribe', '/api/generate', '/api/settings']:
            self.assertEqual(self.request(path, 'POST')[0], 403)

    def test_only_learning_assets_are_served(self):
        self.assertEqual(self.request('/sources/gabriel_01_1.png')[0], 200)
        for path in ['/server.py', '/.env', '/sources/../server.py', '/sources/%2e%2e/.env', '/sources/']:
            self.assertNotEqual(self.request(path)[0], 200)

    def test_bundled_interview_pdfs_are_served_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        materials = json.loads((root / 'data/materials.json').read_text())
        for material in materials:
            path = '/sources/' + material['source_file']
            status, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(body, (root / path.lstrip('/')).read_bytes())

    def test_foreign_host_is_rejected(self):
        self.assertEqual(self.request('/', headers={'Host': 'foreign.example'})[0], 403)

    def test_head_has_no_body(self):
        self.assertEqual(self.request('/', 'HEAD'), (200, b''))


if __name__ == '__main__':
    unittest.main()
