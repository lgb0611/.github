"""DeepL is optional. These tests use a fake DeepL response; no key or network is used."""
import http.client
import io
import json
import threading
import unittest
import urllib.error
from http.server import ThreadingHTTPServer
from unittest import mock

import deepl_service
import free_server

FREE_KEY = '11111111-2222-3333-4444-555555555555:fx'


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_deepl(calls, fail=None):
    def urlopen(req, timeout=0):
        calls.append({'url': req.full_url, 'auth': req.headers.get('Authorization'), 'body': json.loads(req.data) if req.data else None})
        if fail:
            raise urllib.error.HTTPError(req.full_url, fail, 'x', {}, None)
        if req.full_url.endswith('/v2/usage'):
            return FakeResponse(json.dumps({'character_count': 1200, 'character_limit': 500000}).encode())
        body = json.loads(req.data)
        return FakeResponse(json.dumps({'translations': [{'text': '번역: ' + t} for t in body['text']]}, ensure_ascii=False).encode())
    return urlopen


class DeepLServiceTests(unittest.TestCase):
    def setUp(self):
        self.saved = deepl_service.KEY['value']
        self.env = mock.patch.object(deepl_service, 'ENV_FILE', deepl_service.ROOT / 'tests' / '.env.test')
        self.env.start()

    def tearDown(self):
        deepl_service.KEY['value'] = self.saved
        if deepl_service.ENV_FILE.exists():
            deepl_service.ENV_FILE.unlink()
        self.env.stop()

    def test_free_key_uses_free_host_and_keeps_order(self):
        calls = []
        deepl_service.KEY['value'] = FREE_KEY
        with mock.patch('urllib.request.urlopen', fake_deepl(calls)):
            r = deepl_service.translate({'texts': ['First.', 'Second.'], 'context': 'Before.'})
        self.assertEqual(r['engine'], 'deepl')
        self.assertEqual([t['source_en'] for t in r['translations']], ['First.', 'Second.'])
        self.assertEqual(r['translations'][1]['korean_text'], '번역: Second.')
        self.assertEqual(calls[0]['url'], 'https://api-free.deepl.com/v2/translate')
        self.assertEqual(calls[0]['auth'], 'DeepL-Auth-Key ' + FREE_KEY)
        self.assertEqual(calls[0]['body'], {'text': ['First.', 'Second.'], 'source_lang': 'EN', 'target_lang': 'KO', 'context': 'Before.'})

    def test_pro_key_uses_pro_host(self):
        self.assertEqual(deepl_service.base_url('abcdefabcdefabcdefabcdef'), 'https://api.deepl.com')

    def test_key_is_checked_before_storing_and_can_be_remembered_and_cleared(self):
        calls = []
        deepl_service.KEY['value'] = ''
        with mock.patch('urllib.request.urlopen', fake_deepl(calls)):
            r = deepl_service.set_key({'key': FREE_KEY, 'remember': True})
        self.assertEqual(r['usage'], {'character_count': 1200, 'character_limit': 500000})
        self.assertEqual(deepl_service.status(), {'configured': True, 'plan': 'free'})
        self.assertIn('DEEPL_API_KEY=' + FREE_KEY, deepl_service.ENV_FILE.read_text())
        deepl_service.KEY['value'] = ''
        deepl_service.load_key()
        self.assertEqual(deepl_service.KEY['value'], FREE_KEY)
        deepl_service.set_key({'clear': True})
        self.assertNotIn('DEEPL_API_KEY', deepl_service.ENV_FILE.read_text())
        self.assertFalse(deepl_service.status()['configured'])

    def test_wrong_key_is_not_stored(self):
        deepl_service.KEY['value'] = ''
        with mock.patch('urllib.request.urlopen', fake_deepl([], fail=403)):
            with self.assertRaisesRegex(deepl_service.DeepLError, '올바르지 않습니다'):
                deepl_service.set_key({'key': FREE_KEY})
        self.assertFalse(deepl_service.status()['configured'])
        with self.assertRaisesRegex(deepl_service.DeepLError, '형식'):
            deepl_service.set_key({'key': 'not a key'})

    def test_quota_and_bad_input_errors(self):
        deepl_service.KEY['value'] = FREE_KEY
        with mock.patch('urllib.request.urlopen', fake_deepl([], fail=456)):
            with self.assertRaisesRegex(deepl_service.DeepLError, '한도'):
                deepl_service.translate({'texts': ['Hi.']})
        for bad in [{'texts': []}, {'texts': [''] }, {'texts': ['x' * 2001]}, {'texts': ['a'] * 51}, {'texts': ['a'], 'extra': 1}]:
            with self.assertRaises(deepl_service.DeepLError):
                deepl_service.translate(bad)

    def test_untranslated_reply_is_rejected(self):
        deepl_service.KEY['value'] = FREE_KEY
        def english(req, timeout=0):
            return FakeResponse(json.dumps({'translations': [{'text': 'still English'}]}).encode())
        with mock.patch('urllib.request.urlopen', english):
            with self.assertRaisesRegex(deepl_service.DeepLError, '한국어'):
                deepl_service.translate({'texts': ['Hi.']})


class DeepLEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), free_server.FreeHandler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, path, body, token=None):
        port = self.httpd.server_port
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        raw = json.dumps(body).encode()
        c.request('POST', path, raw, {'Host': f'127.0.0.1:{port}', 'Content-Type': 'application/json', 'Content-Length': str(len(raw)), 'X-Local-Token': free_server.YOUTUBE_TOKEN if token is None else token})
        r = c.getresponse()
        data = json.loads(r.read())
        c.close()
        return r.status, data

    def test_endpoint_translates_with_token_and_never_returns_the_key(self):
        saved = deepl_service.KEY['value']
        deepl_service.KEY['value'] = FREE_KEY
        try:
            with mock.patch('urllib.request.urlopen', fake_deepl([])):
                status, data = self.post('/deepl/translate', {'texts': ['Hello.']})
                self.assertEqual(status, 200)
                self.assertEqual(data['translations'][0]['korean_text'], '번역: Hello.')
                status, data = self.post('/deepl/usage', {})
                self.assertEqual(data['usage']['character_limit'], 500000)
                self.assertNotIn(FREE_KEY, json.dumps(data))
            status, _ = self.post('/deepl/translate', {'texts': ['Hello.']}, token='wrong')
            self.assertEqual(status, 403)
        finally:
            deepl_service.KEY['value'] = saved

    def test_config_reports_only_whether_deepl_is_connected(self):
        port = self.httpd.server_port
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        c.request('GET', '/api/config', headers={'Host': f'127.0.0.1:{port}'})
        data = json.loads(c.getresponse().read())
        c.close()
        self.assertEqual(set(data['deepl']), {'configured', 'plan'})


if __name__ == '__main__':
    unittest.main()
