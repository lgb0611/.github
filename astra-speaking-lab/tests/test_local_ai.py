"""Local extraction contracts; model outputs are fixtures, not real inference."""
import copy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
import local_ai as ai
import free_server

ID = 'M7lc1UVf-VE'
SOURCE = 'This song brings back so many good memories.'


def payload():
    return {'video_id': ID, 'count': 3, 'cues': [{'id': 'cue_0', 'text': SOURCE}]}


def item():
    return {'cue_id': 'cue_0', 'expression': SOURCE, 'meaning_ko': '이 노래를 들으면 좋은 추억이 아주 많이 떠올라요.',
            'use_case_ko': '사진이 옛 기억을 떠올리게 한다고 말하기', 'note_ko': '기억을 떠올리게 하는 문맥입니다.',
            'new_task_ko': '사진이 학창 시절을 떠올리게 한다고 말하기',
            'new_sample_en': 'This photo brings back memories of my school days.'}


def response(obj=None):
    return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(obj or {'items': [item()]})}}


class ExtractionTests(unittest.TestCase):
    def test_input_rejects_arbitrary_models_urls_and_bad_ids_before_network(self):
        for change in [{'model': 'cloud'}, {'url': 'https://example.com'}, {'video_id': '../etc'}, {'count': True}]:
            with patch.object(ai, 'request') as request:
                with self.assertRaises(ai.LocalAIError): ai.extract(payload() | change)
                request.assert_not_called()

    def test_source_size_and_duplicate_ids_are_bounded(self):
        for cues in [[{'id': 'cue_0', 'text': 'a' * 5000}], [{'id': 'cue_0', 'text': 'a'}] * 2,
                     [{'id': f'cue_{i}', 'text': 'a' * 1000} for i in range(17)]]:
            with self.assertRaises(ai.LocalAIError): ai.validate_input(payload() | {'cues': cues})

    def test_unknown_pattern_becomes_a_source_grounded_local_ai_lesson(self):
        with patch.object(ai, 'status', return_value={'ready': True}), patch.object(ai, 'request', side_effect=[{}, response()]) as request:
            got = ai.extract(payload())
            self.assertEqual(got['engine'], 'local_ai')
            self.assertEqual(got['items'][0]['source_text'], SOURCE)
            call = request.call_args_list[-1]
            self.assertEqual(call.args[0], '/api/chat')
            self.assertEqual(call.args[1]['model'], 'qwen3.5:4b')
            self.assertFalse(call.args[1]['think'])
            self.assertEqual(call.args[1]['format'], ai.SCHEMA)
            self.assertIn('untrusted', call.args[1]['messages'][0]['content'])

    def test_missing_model_does_not_trigger_download_or_generation(self):
        with patch.object(ai, 'status', return_value={'ready': False}), patch.object(ai, 'request') as request:
            with self.assertRaisesRegex(ai.LocalAIError, '준비'): ai.extract(payload())
            request.assert_not_called()

    def test_remote_model_metadata_is_rejected_before_chat(self):
        with patch.object(ai, 'status', return_value={'ready': True}), patch.object(ai, 'request', return_value={'remote_host': 'https://ollama.com'}) as request:
            with self.assertRaisesRegex(ai.LocalAIError, '클라우드'): ai.extract(payload())
            self.assertEqual(request.call_count, 1)

    def test_fabricated_quotes_duplicates_and_incomplete_lessons_are_filtered(self):
        bad = [item() | {'expression': 'brings back'}, item() | {'expression': 'makes me remember'}, item() | {'meaning_ko': 'English only'},
               item() | {'new_sample_en': 'Too short'}, item() | {'cue_id': 'cue_99'}]
        got = ai.checked_items({'items': bad + [item(), item()]}, payload()['cues'], 3)
        self.assertEqual(len(got), 1)
        with self.assertRaises(ai.LocalAIError): ai.checked_items({'items': bad}, payload()['cues'], 3)

    def test_full_sentence_can_transfer_structure_without_copying_the_original_event(self):
        got = ai.checked_items({'items': [item()]}, payload()['cues'], 1)[0]
        self.assertEqual(got['expression'], SOURCE)
        self.assertNotIn(SOURCE, got['new_sample_en'])
        self.assertIn('photo', got['new_sample_en'])

    def test_source_and_time_fields_come_from_input_not_the_model(self):
        made = item() | {'source_text': 'invented', 'start': 999, 'end': 1000}
        got = ai.checked_items({'items': [made]}, payload()['cues'], 3)[0]
        self.assertEqual(got['source_text'], SOURCE)
        self.assertNotIn('start', got)

    def test_one_local_repair_can_recover_invalid_json(self):
        malformed = {'done': True, 'message': {'content': '{bad'}}
        with patch.object(ai, 'status', return_value={'ready': True}), patch.object(ai, 'request', side_effect=[{}, malformed, response()]) as request:
            self.assertEqual(len(ai.extract(payload())['items']), 1)
            self.assertEqual(request.call_count, 3)

    def test_incomplete_output_is_never_saved_and_repair_is_bounded(self):
        unfinished = response() | {'done_reason': 'length'}
        with patch.object(ai, 'status', return_value={'ready': True}), patch.object(ai, 'request', side_effect=[{}, unfinished, unfinished]) as request:
            with self.assertRaises(ai.LocalAIError): ai.extract(payload())
            self.assertEqual(request.call_count, 3)
        self.assertFalse(ai.LOCK.locked())

    def test_connection_failure_is_not_retried(self):
        with patch.object(ai, 'status', return_value={'ready': True}), patch.object(ai, 'request', side_effect=[{}, ai.LocalAIError('offline')]) as request:
            with self.assertRaises(ai.LocalAIError): ai.extract(payload())
            self.assertEqual(request.call_count, 2)

    def test_duplicate_running_extraction_does_not_start_another_model(self):
        ai.LOCK.acquire()
        try:
            with patch.object(ai, 'status') as status:
                with self.assertRaisesRegex(ai.LocalAIError, '처리 중'): ai.extract(payload())
                status.assert_not_called()
        finally:
            ai.LOCK.release()

    def test_status_does_not_download_and_does_not_accept_cloud_tags(self):
        with patch.object(ai, 'request', return_value={'models': [{'name': ai.MODEL, 'remote_model': 'remote'}]}) as request:
            self.assertFalse(ai.status()['ready'])
            self.assertEqual(request.call_args.args, ('/api/tags',))

    def test_setup_requires_a_running_local_program(self):
        with patch.object(ai, 'status', return_value={'ready': False, 'running': False, 'setup': {}}), patch.object(ai.threading, 'Thread') as worker:
            with self.assertRaisesRegex(ai.LocalAIError, '설치'): ai.prepare()
            worker.assert_not_called()


class LocalHTTPTests(unittest.TestCase):
    def test_model_download_processes_progress_success_and_failure_over_local_http(self):
        for failed in [False, True]:
            recorded = []
            class Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    recorded.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                    rows = [{'status': 'pulling digest', 'completed': 50, 'total': 100},
                            {'error': 'fixture failure'} if failed else {'status': 'success'}]
                    body = ''.join(json.dumps(row)+'\n' for row in rows).encode()
                    self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
                def log_message(self, *args): pass
            httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
            try:
                with patch.object(ai, 'PORT', httpd.server_port), patch.dict(ai.SETUP, {'running': True, 'error': ''}):
                    ai._download()
                    self.assertFalse(ai.SETUP['running'])
                    self.assertEqual(bool(ai.SETUP['error']), failed)
                    self.assertEqual(recorded, [('/api/pull', {'model': ai.MODEL, 'stream': True})])
            finally:
                httpd.shutdown(); httpd.server_close(); thread.join(2)

    def test_repeated_setup_does_not_start_multiple_downloads(self):
        with patch.object(ai, 'status', return_value={'ready': False, 'running': True, 'setup': {}}), patch.object(ai.threading, 'Thread') as worker, patch.dict(ai.SETUP, {'running': False}):
            ai.prepare(); ai.prepare()
            self.assertTrue(ai.SETUP['running'])
            self.assertEqual(worker.call_count, 1)

    def test_http_client_sends_only_to_loopback_and_rejects_redirects(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302); self.send_header('Location', 'https://example.com'); self.end_headers()
            def log_message(self, *args): pass
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
        try:
            with patch.object(ai, 'PORT', httpd.server_port):
                with self.assertRaises(ai.LocalAIError): ai.request('/api/tags')
                with self.assertRaises(ai.LocalAIError): ai.request('https://example.com')
        finally:
            httpd.shutdown(); httpd.server_close(); thread.join(2)


class AppEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), free_server.FreeHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.thread.join(2)
    def post(self, path, data, extra=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        headers = {'Content-Type': 'application/json', 'X-Local-Token': free_server.YOUTUBE_TOKEN} | (extra or {})
        connection.request('POST', path, json.dumps(data), headers)
        response = connection.getresponse(); result = response.status, json.loads(response.read()); connection.close()
        return result
    def test_extraction_requires_the_local_app_token_and_origin(self):
        for headers in [{'X-Local-Token': 'invalid'}, {'Origin': 'https://foreign.example'}, {'Host': 'foreign.example'}]:
            with patch.object(ai, 'extract') as extract:
                self.assertEqual(self.post('/youtube/extract', payload(), headers)[0], 403)
                extract.assert_not_called()
    def test_valid_extraction_route_returns_local_result(self):
        expected = {'video_id': ID, 'engine': 'local_ai', 'items': [item()]}
        with patch.object(ai, 'extract', return_value=expected) as extract:
            self.assertEqual(self.post('/youtube/extract', payload()), (200, expected))
            extract.assert_called_once_with(payload())
    def test_setup_is_an_explicit_post_with_no_model_override(self):
        with patch.object(ai, 'prepare', return_value={'ready': False, 'setup': {'running': True}}) as prepare:
            self.assertEqual(self.post('/local-ai/setup', {'model': 'cloud'})[0], 400)
            prepare.assert_not_called()
            self.assertEqual(self.post('/local-ai/setup', {})[0], 200)
            prepare.assert_called_once()
    def test_errors_do_not_erase_the_client_input_or_return_fake_lessons(self):
        with patch.object(ai, 'extract', side_effect=ai.LocalAIError('AI 준비 필요')):
            status, data = self.post('/youtube/extract', payload())
            self.assertEqual(status, 422); self.assertEqual(data, {'detail': 'AI 준비 필요'})
    def test_oversized_caption_body_is_rejected_before_model_work(self):
        with patch.object(ai, 'extract') as extract:
            self.assertEqual(self.post('/youtube/extract', {'text': 'a' * 128001})[0], 413)
            extract.assert_not_called()


if __name__ == '__main__': unittest.main()
