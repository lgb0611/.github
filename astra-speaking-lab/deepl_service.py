"""Optional DeepL translation for Korean meanings, called only from the local free server.

The key stays on this computer: in memory, or in .env when the learner asks to remember it.
The browser never receives the key. Only English sentences are sent to DeepL.
"""
from pathlib import Path
import json
import os
import re
import threading
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / '.env'
MAX_TEXTS = 50
MAX_TEXT = 2000
MAX_TOTAL = 30000
MAX_CONTEXT = 2000
LOCK = threading.Lock()
KEY = {'value': ''}


class DeepLError(Exception):
    pass


def valid_key(key):
    return isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9-]{20,60}(?::fx)?', key.strip()) is not None


def load_key():
    """Environment first, then the DEEPL_API_KEY line of .env."""
    key = os.environ.get('DEEPL_API_KEY', '').strip()
    if not key and ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.strip().startswith('DEEPL_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"\'')
    KEY['value'] = key if valid_key(key) else ''


def base_url(key):
    # DeepL API Free keys end with ":fx" and use a separate host.
    return 'https://api-free.deepl.com' if key.endswith(':fx') else 'https://api.deepl.com'


def call(path, body=None, key=None, timeout=30):
    key = key or KEY['value']
    if not key:
        raise DeepLError('DeepL API 키가 연결되지 않았습니다. 설정에서 키를 넣어 주세요.')
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(base_url(key) + path, data=data, method='POST' if data else 'GET',
                                 headers={'Authorization': 'DeepL-Auth-Key ' + key, 'Content-Type': 'application/json',
                                          'User-Agent': 'AstraSpeakingLab/2.11'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        messages = {403: 'DeepL API 키가 올바르지 않습니다. 키를 다시 확인해 주세요.',
                    456: '이번 달 DeepL 무료 번역 한도를 다 썼습니다. 다음 달에 다시 쓰거나 기존 번역을 사용하세요.',
                    429: 'DeepL 요청이 너무 많습니다. 잠시 후 다시 시도하세요.'}
        raise DeepLError(messages.get(exc.code, f'DeepL 번역에 실패했습니다 (HTTP {exc.code}).')) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise DeepLError('DeepL에 연결하지 못했습니다. 인터넷 연결을 확인하세요.') from None
    except ValueError:
        raise DeepLError('DeepL 응답을 읽지 못했습니다.') from None


def usage(key=None):
    data = call('/v2/usage', key=key)
    count, limit = data.get('character_count'), data.get('character_limit')
    return {'character_count': count if isinstance(count, int) else None, 'character_limit': limit if isinstance(limit, int) else None}


def status():
    return {'configured': bool(KEY['value']), 'plan': ('free' if KEY['value'].endswith(':fx') else 'pro') if KEY['value'] else ''}


def remember(key):
    lines = ENV_FILE.read_text(encoding='utf-8').splitlines() if ENV_FILE.is_file() else []
    lines = [line for line in lines if not line.strip().startswith('DEEPL_API_KEY=')]
    if key:
        lines.append('DEEPL_API_KEY=' + key)
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def set_key(payload):
    if not isinstance(payload, dict) or set(payload) - {'key', 'remember', 'clear'}:
        raise DeepLError('키 설정 형식을 확인하세요.')
    with LOCK:
        if payload.get('clear') is True:
            KEY['value'] = ''
            remember('')
            return {**status(), 'usage': None}
        key = payload.get('key')
        key = key.strip() if isinstance(key, str) else ''
        if not valid_key(key):
            raise DeepLError('DeepL API 키 형식이 아닙니다. DeepL 계정의 API Keys 화면에서 복사해 주세요.')
        found = usage(key)  # checks the key before storing it
        KEY['value'] = key
        if payload.get('remember') is True:
            remember(key)
        return {**status(), 'usage': found}


def translate(payload):
    texts = payload.get('texts') if isinstance(payload, dict) else None
    context = payload.get('context', '') if isinstance(payload, dict) else ''
    if (not isinstance(texts, list) or not 1 <= len(texts) <= MAX_TEXTS
            or any(not isinstance(t, str) or not t.strip() or len(t) > MAX_TEXT for t in texts)
            or sum(len(t) for t in texts) > MAX_TOTAL or not isinstance(context, str) or set(payload) - {'texts', 'context'}):
        raise DeepLError('번역할 문장 형식을 확인하세요.')
    body = {'text': texts, 'source_lang': 'EN', 'target_lang': 'KO'}
    if context.strip():
        body['context'] = context[:MAX_CONTEXT]  # surrounding sentences guide the meaning and are not billed
    data = call('/v2/translate', body)
    rows = data.get('translations') if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != len(texts) or any(not isinstance(r, dict) or not isinstance(r.get('text'), str) or not re.search('[가-힣]', r['text']) for r in rows):
        raise DeepLError('DeepL이 모든 문장의 한국어를 돌려주지 않았습니다.')
    return {'engine': 'deepl', 'translations': [{'source_en': t, 'korean_text': r['text'].strip()} for t, r in zip(texts, rows)]}


load_key()
