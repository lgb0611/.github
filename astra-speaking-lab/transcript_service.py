"""Optional public English captions. No keys, login cookies, proxies, or paid provider."""
import importlib.util
import math
import re


class TranscriptError(Exception):
    pass


def available():
    return importlib.util.find_spec('youtube_transcript_api') is not None


def fetch_public(video_id):
    if not isinstance(video_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise TranscriptError('YouTube 동영상 ID가 올바르지 않습니다.')
    if not available():
        raise TranscriptError('자동 자막 구성 요소가 없습니다. start_youtube_windows.bat으로 실행하거나 자막을 붙여 넣으세요.')
    from requests import Session
    from youtube_transcript_api import YouTubeTranscriptApi

    class TimeoutSession(Session):
        def request(self, method, url, **kwargs):
            kwargs.setdefault('timeout', (5, 12))
            return super().request(method, url, **kwargs)

    try:
        with TimeoutSession() as http:
            tracks = list(YouTubeTranscriptApi(http_client=http).list(video_id))
            english = [t for t in tracks if t.language_code.lower().split('-')[0] == 'en']
            if not english:
                raise TranscriptError('사용 가능한 영어 자막이 없습니다. 영상의 영어 스크립트를 직접 붙여 넣으세요.')
            track = sorted(english, key=lambda t: t.is_generated)[0]
            transcript = track.fetch()
            cues, length = [], 0
            for row in transcript:
                if not isinstance(row.text, str) or not all(math.isfinite(v) for v in [row.start, row.duration]):
                    raise TranscriptError('자막 응답을 읽지 못했습니다.')
                if row.start < 0 or row.duration <= 0 or row.start + row.duration > 86400:
                    raise TranscriptError('자막의 재생 시간을 확인하지 못했습니다.')
                if not row.text.strip():
                    continue
                length += len(row.text)
                if length > 200000 or len(cues) >= 3000:
                    raise TranscriptError('영상 자막이 너무 깁니다. 필요한 구간의 스크립트를 직접 붙여 넣으세요.')
                cues.append({'start': row.start, 'duration': max(row.duration, .01), 'text': row.text})
            if not cues:
                raise TranscriptError('영어 자막이 비어 있습니다.')
            return {'video_id': video_id, 'language': track.language_code, 'is_generated': track.is_generated, 'cues': cues}
    except TranscriptError:
        raise
    except Exception as exc:
        kind = type(exc).__name__
        if kind in {'RequestBlocked', 'IpBlocked', 'AgeRestricted', 'PoTokenRequired', 'YouTubeRequestFailed'}:
            message = 'YouTube가 자막 접근을 제한했습니다. 자동 재시도 없이 중단합니다.'
        elif kind in {'TranscriptsDisabled', 'NoTranscriptFound', 'VideoUnavailable', 'VideoUnplayable'}:
            message = '이 영상에서 영어 자막을 가져올 수 없습니다.'
        else:
            message = 'YouTube 자막 요청에 실패했습니다. 네트워크 또는 자막 서비스 상태를 확인하세요.'
        raise TranscriptError(message + ' YouTube의 스크립트 표시에서 자막을 복사해 붙여 넣으세요.') from None
