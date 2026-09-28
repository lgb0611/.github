"""Boundary and failure tests for the optional caption service; no live YouTube calls."""
import http.client
import json
import threading
import types
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import free_server
import transcript_service as service

ID = 'M7lc1UVf-VE'

class CaptionEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), free_server.FreeHandler)
        cls.worker = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.worker.join(2)
    def post(self, payload, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        h = {'Content-Type': 'application/json', 'X-Local-Token': free_server.YOUTUBE_TOKEN}
        h.update(headers or {})
        c.request('POST', '/youtube/transcript', json.dumps(payload), h)
        r = c.getresponse(); status, data = r.status, json.loads(r.read()); c.close()
        return status, data
    def test_success_passes_only_video_id_to_service(self):
        fixture = {'video_id': ID, 'cues': [{'start': .1, 'duration': .3, 'text': 'Fixture.'}]}
        with patch.object(service, 'fetch_public', return_value=fixture) as mock:
            self.assertEqual(self.post({'video_id': ID}), (200, fixture))
            mock.assert_called_once_with(ID)
    def test_foreign_site_and_bad_token_never_call_service(self):
        for header in [{'Origin': 'https://foreign.example'}, {'Host': 'foreign.example'}, {'X-Local-Token': 'wrong'}]:
            with patch.object(service, 'fetch_public') as mock:
                self.assertEqual(self.post({'video_id': ID}, header)[0], 403)
                mock.assert_not_called()
    def test_excess_fields_and_large_body_rejected(self):
        self.assertEqual(self.post({'url': 'https://example.com'})[0], 400)
        self.assertEqual(self.post({'video_id': 'x'*2000})[0], 413)
    def test_busy_rejects_duplicate_network_work(self):
        free_server.YOUTUBE_BUSY.acquire()
        try:
            with patch.object(service, 'fetch_public') as mock:
                self.assertEqual(self.post({'video_id': ID})[0], 409)
                mock.assert_not_called()
        finally:
            free_server.YOUTUBE_BUSY.release()
    def test_caption_failure_is_actionable_and_unlocks_next_request(self):
        with patch.object(service, 'fetch_public', side_effect=service.TranscriptError('자막 붙여넣기로 계속하세요.')):
            status, data = self.post({'video_id': ID})
            self.assertEqual(status, 422); self.assertIn('붙여넣기', data['detail'])
        self.assertFalse(free_server.YOUTUBE_BUSY.locked())

class PublicCaptionTests(unittest.TestCase):
    def test_invalid_id_rejected_before_import_or_network(self):
        with patch.object(service, 'available') as available:
            with self.assertRaises(service.TranscriptError): service.fetch_public('http://127.0.0.1/')
            available.assert_not_called()
    def test_missing_optional_package_has_manual_fallback(self):
        with patch.object(service, 'available', return_value=False):
            with self.assertRaisesRegex(service.TranscriptError, '붙여 넣'): service.fetch_public(ID)
    def fake_modules(self, tracks=None, error=None):
        class Session:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class API:
            calls = 0
            def __init__(self, http_client=None): pass
            def list(self, video_id):
                API.calls += 1
                if error: raise error
                return tracks
        return {'requests': types.SimpleNamespace(Session=Session), 'youtube_transcript_api': types.SimpleNamespace(YouTubeTranscriptApi=API)}, API
    def test_english_track_prefers_manual_and_preserves_real_times(self):
        auto = types.SimpleNamespace(language_code='en', is_generated=True, fetch=lambda: [])
        manual = types.SimpleNamespace(language_code='en-US', is_generated=False, fetch=lambda: [types.SimpleNamespace(text='Fixture.',start=.125,duration=.375)])
        modules, api = self.fake_modules([auto, manual])
        with patch.object(service, 'available', return_value=True), patch.dict('sys.modules', modules):
            got = service.fetch_public(ID)
            self.assertFalse(got['is_generated']); self.assertEqual(got['cues'][0]['start'], .125)
            self.assertEqual(api.calls, 1)
    def test_access_block_is_not_retried(self):
        modules, api = self.fake_modules(error=type('RequestBlocked', (Exception,), {})())
        with patch.object(service, 'available', return_value=True), patch.dict('sys.modules', modules):
            with self.assertRaisesRegex(service.TranscriptError, '접근을 제한'): service.fetch_public(ID)
            self.assertEqual(api.calls, 1)

if __name__ == '__main__': unittest.main()
