"""
매수 고정(52주 신고가 + 거래대금 상위 30위 + 상승장 + 대형주)에서 더 나은 매도 조건 찾기

- 매도 후보: 기존 79개(13부 단기 59개 + 14부 중기 20개) + 손절 -10% 기반 중기 변형
- 한국 발견 기간(2016~22) 계좌 샤프지수로 고르고, 한국 확인 기간과 미국 두 기간으로 검증
- 16부 매도(손절 -10% + 25일선 50% / 60일선 50%)와 비교

실행: python largecap_exit_search.py && MARKET=us python largecap_exit_search.py && python largecap_exit_search.py summary
"""
import itertools
import os
import sys

import pandas as pd

import largecap as L
import strategies as S

ENTRY = "52주 신고가 + 거래대금 상위 30위 + 상승장"
BASE_EXIT = "손절 -10% + 25일선 50% / 60일선 50%"


def candidates():
    ex = dict(L.all_exits())
    ex[BASE_EXIT] = [(0.5, dict(ma="ma25", sl=-0.10)), (0.5, dict(ma="ma60", sl=-0.10))]
    sl = -0.10
    # 이평선 두 개로 절반씩 (손절 -10%)
    for a, b in itertools.combinations(["ma20", "ma25", "ma50", "ma60"], 2):
        ex[f"손절 -10% + {a[2:]}일선 50% / {b[2:]}일선 50%"] = [(0.5, dict(ma=a, sl=sl)), (0.5, dict(ma=b, sl=sl))]
    # 한 이평선으로 전량 (손절 -10%)
    for a in ["ma20", "ma25", "ma50", "ma60"]:
        ex[f"손절 -10% + {a[2:]}일선 이탈 전량"] = [(1, dict(ma=a, sl=sl))]
    # 최소 보유 후 이평선
    for h, (a, b) in itertools.product([10, 20], [("ma25", "ma60"), ("ma20", "ma60"), ("ma20", "ma50")]):
        ex[f"손절 -10% + {h}일 보유 후 {a[2:]}일선 50% / {b[2:]}일선 50%"] = [
            (0.5, dict(ma=a, sl=sl, min_hold=h)), (0.5, dict(ma=b, sl=sl, min_hold=h))]
    # 추적 손절
    for tr in [0.10, 0.15, 0.20]:
        ex[f"손절 -10% + 고점 대비 -{tr:.0%} 추적"] = [(1, dict(trail=tr, sl=sl))]
        ex[f"손절 -10% + 20일 보유 후 고점 대비 -{tr:.0%} 추적"] = [(1, dict(trail=tr, sl=sl, min_hold=20))]
    # 일부 익절 + 나머지 추세
    for tp in [0.15, 0.20, 0.30]:
        ex[f"손절 -10% + 50% +{tp:.0%} 익절 + 50% 60일선 이탈"] = [(0.5, dict(tp=tp, sl=sl)), (0.5, dict(ma="ma60", sl=sl))]
        ex[f"손절 -10% + 50% +{tp:.0%} 익절 + 50% 고점 대비 -15% 추적"] = [(0.5, dict(tp=tp, sl=sl)), (0.5, dict(trail=0.15, sl=sl))]
    # 기간 청산
    for t in [40, 60, 90]:
        ex[f"손절 -10% + {t}일 보유"] = [(1, dict(time=t, sl=sl))]
        ex[f"손절 -10% + 25일선 50% / {t}일 보유 50%"] = [(0.5, dict(ma="ma25", sl=sl)), (0.5, dict(time=t, sl=sl))]
    return ex


def summary():
    kr = pd.read_csv(os.path.join(S.BASE, "results", "largecap_exit_search.csv"))
    us = pd.read_csv(os.path.join(S.BASE, "results_us", "largecap_exit_search.csv"))
    d = kr.merge(us, on=["매수", "시총조건", "매도"], suffixes=("_kr", "_us"))
    pd.set_option("display.width", 340)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda x, a, fmt: (x[f"발견_{a}"].map(lambda v: f(v, fmt)) + " → " + x[f"확인_{a}"].map(lambda v: f(v, fmt))).values

    def show(x):
        return pd.DataFrame({
            "매도": x["매도"].values, "보유": x["발견_보유일_kr"].map(lambda v: f(v, "{:.0f}")).values,
            "한국 거래평균": arrow(x, "거래평균_kr", "{:+.1%}"), "수익비율": arrow(x, "수익비율_kr", "{:.0%}"),
            "한국 연평균": arrow(x, "연평균_kr", "{:+.1%}"), "한국 샤프": arrow(x, "샤프_kr", "{:.2f}"),
            "한국 낙폭": arrow(x, "최대낙폭_kr", "{:.0%}"),
            "미국 거래평균": arrow(x, "거래평균_us", "{:+.1%}"), "미국 연평균": arrow(x, "연평균_us", "{:+.1%}"),
            "미국 샤프": arrow(x, "샤프_us", "{:.2f}"), "미국 낙폭": arrow(x, "최대낙폭_us", "{:.0%}"),
        })

    d["발견순위"] = d["발견_샤프_kr"].rank(ascending=False).astype(int)
    print(f"매수 고정: {ENTRY} + 대형주 / 매도 후보 {len(d)}개 (발견 2016~22 → 확인 2023~26)")
    print("\n[1] 한국 발견 기간 샤프 상위 10개 (전체)")
    print(show(d.sort_values("발견_샤프_kr", ascending=False).head(10)).to_string(index=False))
    mid = d[d["발견_보유일_kr"] >= 20]
    print("\n[2] 평균 보유 20일 이상 중 한국 발견 기간 샤프 상위 10개")
    print(show(mid.sort_values("발견_샤프_kr", ascending=False).head(10)).to_string(index=False))
    base = d[d["매도"] == BASE_EXIT]
    print(f"\n[3] 16부 매도 ({BASE_EXIT}) — 한국 발견 기간 순위 {int(base['발견순위'].iloc[0])}위 / {len(d)}개")
    print(show(base).to_string(index=False))
    cols = ["발견_샤프_kr", "확인_샤프_kr", "발견_샤프_us", "확인_샤프_us"]
    d["네 곳 최소 샤프"] = d[cols].min(axis=1)
    print("\n[4] 참고: 네 곳 중 가장 나쁜 샤프가 높은 순 (네 곳을 다 보고 고른 것이라 검증 아님)")
    print(show(d.sort_values("네 곳 최소 샤프", ascending=False).head(8)).to_string(index=False))
    d.to_csv(os.path.join(S.BASE, "results", "largecap_exit_search_summary.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        summary()
    else:
        L.run_market(candidates(), "largecap_exit_search.csv", only=[ENTRY], caps=(True,))
