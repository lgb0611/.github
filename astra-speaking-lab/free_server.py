"""Free local launcher. Optional public captions; no OpenAI client or key loading."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import mimetypes
import os
import threading
import webbrowser
import secrets
import transcript_service
import local_ai
import deepl_service

ROOT = Path(__file__).resolve().parent
YOUTUBE_TOKEN = secrets.token_urlsafe(32)
YOUTUBE_BUSY = threading.Lock()


class FreeHandler(BaseHTTPRequestHandler):
    def send_content(self, status, body, content_type='text/plain; charset=utf-8', head=False):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        port = self.server.server_port
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            return self.send_content(403, b'Local access only.', head=head)
        try:
            path = unquote(urlsplit(self.path).path)
            if path == '/api/config':
                return self.send_content(200, json.dumps({'server': False, 'free_only': True, 'connected': False, 'youtube_available': transcript_service.available(), 'youtube_token': YOUTUBE_TOKEN, 'local_ai': True, 'deepl': deepl_service.status()}).encode(), 'application/json', head)
            if path == '/local-ai/status':
                return self.send_content(200, json.dumps(local_ai.status()).encode(), 'application/json', head)
            if path in {'/', '/OPEN_ME.html'}:
                target = ROOT / 'OPEN_ME.html'
            elif path.startswith('/sources/'):
                target = (ROOT / path.lstrip('/')).resolve()
                if not target.is_relative_to((ROOT / 'sources').resolve()):
                    return self.send_content(403, b'Forbidden.', head=head)
            else:
                return self.send_content(404, b'Not found. Free mode has no paid API endpoints.', head=head)
            if not target.is_file():
                return self.send_content(404, b'Not found.', head=head)
            kind = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            self.send_content(200, target.read_bytes(), kind, head)
        except (ValueError, OSError):
            self.send_content(400, b'Invalid path.', head=head)

    def do_POST(self):
        if self.path not in {'/youtube/transcript', '/youtube/extract', '/local-ai/setup', '/local-ai/translate', '/local-ai/paragraph', '/deepl/key', '/deepl/translate', '/deepl/usage'}:
            return self.send_content(403, b'Free mode: paid API requests are disabled.')
        def reply(code, data):
            self.send_content(code, json.dumps(data, ensure_ascii=False).encode(), 'application/json; charset=utf-8')
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts or self.headers.get('Origin', '') not in {'', *(f'http://{h}' for h in hosts)} or not secrets.compare_digest(self.headers.get('X-Local-Token', ''), YOUTUBE_TOKEN):
            return reply(403, {'detail': '이 앱에서만 요청할 수 있습니다. 페이지를 새로고침하세요.'})
        try:
            if self.headers.get('Transfer-Encoding'):
                return reply(400, {'detail': '요청 크기를 확인하지 못했습니다.'})
            length = int(self.headers.get('Content-Length', '-1'))
            limit = 128000 if self.path in {'/youtube/extract', '/local-ai/translate', '/local-ai/paragraph', '/deepl/translate'} else 1024
            if not 1 <= length <= limit:
                return reply(413, {'detail': '자막 요청 크기가 올바르지 않습니다.'})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                return reply(400, {'detail': '요청 형식을 확인하세요.'})
            if self.path == '/youtube/transcript' and set(payload) != {'video_id'}:
                return reply(400, {'detail': '영상 ID 하나만 요청할 수 있습니다.'})
        except (ValueError, UnicodeError):
            return reply(400, {'detail': '자막 요청 형식을 확인하세요.'})
        if self.path.startswith('/deepl/'):
            try:
                if self.path == '/deepl/key':
                    return reply(200, deepl_service.set_key(payload))
                if self.path == '/deepl/usage':
                    return reply(200, {**deepl_service.status(), 'usage': deepl_service.usage()})
                return reply(200, deepl_service.translate(payload))
            except deepl_service.DeepLError as exc:
                return reply(422, {'detail': str(exc)})
        if self.path != '/youtube/transcript':
            try:
                if self.path == '/local-ai/setup':
                    if payload:
                        return reply(400, {'detail': '준비 요청에는 추가 설정이 필요하지 않습니다.'})
                    return reply(200, local_ai.prepare())
                if self.path == '/local-ai/translate':
                    return reply(200, local_ai.translate(payload))
                if self.path == '/local-ai/paragraph':
                    return reply(200, local_ai.paragraph(payload))
                return reply(200, local_ai.extract(payload))
            except local_ai.LocalAIError as exc:
                return reply(422, {'detail': str(exc)})
        if not YOUTUBE_BUSY.acquire(blocking=False):
            return reply(409, {'detail': '이전 자막 요청을 처리 중입니다. 잠시 후 다시 시도하세요.'})
        try:
            reply(200, transcript_service.fetch_public(payload['video_id']))
        except transcript_service.TranscriptError as exc:
            reply(422, {'detail': str(exc)})
        finally:
            YOUTUBE_BUSY.release()

    def log_message(self, format, *args):
        pass


def main():
    port = int(os.environ.get('ASTRA_FREE_PORT', '8765'))
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', port), FreeHandler)
    except OSError:
        print(f'Port {port} is in use. Close the previous Speaking Lab server and try again.')
        return 1
    url = f'http://127.0.0.1:{httpd.server_port}/'
    print(f'Astra Speaking Lab - FREE MODE\nOpen {url}\nNo API key. No paid API calls. Ctrl+C to stop.', flush=True)
    if os.environ.get('ASTRA_NO_BROWSER') != '1':
        opener = threading.Timer(0.5, lambda: webbrowser.open(url))
        opener.daemon = True
        opener.start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
