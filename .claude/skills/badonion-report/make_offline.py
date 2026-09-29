"""보고서 HTML을 인터넷 없이 열리는 단일 파일로 만듦.

사용법:
    python make_offline.py 보고서.html
결과:
    보고서_offline.html  (차트 라이브러리 Plotly가 파일 안에 들어감, 약 5MB 증가)

처음 실행할 때 Plotly를 한 번 내려받아 이 폴더에 plotly-3.3.1.min.js 로 저장하고,
다음부터는 저장된 파일을 다시 씀.
"""
import sys
import urllib.request
from pathlib import Path

PLOTLY_URL = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@3.3.1/plotly.min.js"
CACHE = Path(__file__).with_name("plotly-3.3.1.min.js")
TAG = f'<script src="{PLOTLY_URL}"></script>'


def load_plotly() -> str:
    if not CACHE.exists():
        print("Plotly 내려받는 중…")
        with urllib.request.urlopen(PLOTLY_URL) as res:
            CACHE.write_bytes(res.read())
    return CACHE.read_text(encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: python make_offline.py 보고서.html")
    src = Path(sys.argv[1])
    html = src.read_text(encoding="utf-8")
    if TAG not in html:
        sys.exit("Plotly CDN 태그를 찾지 못함 — template.html의 <script src=...> 줄을 지우거나 바꾸지 않았는지 확인")
    # 라이브러리 안의 '</script>' 문자열이 태그를 일찍 닫지 않도록 이스케이프
    lib = load_plotly().replace("</script", "<\\/script")
    out = src.with_name(src.stem + "_offline.html")
    out.write_text(html.replace(TAG, "<script>\n" + lib + "\n</script>", 1), encoding="utf-8")
    print(f"완료: {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
