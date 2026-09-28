"""
대형주만 + 손절 -10% + 25일선 이탈 50% / 60일선 이탈 50% 매도

largecap.py의 매수 신호 5개와 대형주 조건(한국 5조 원·미국 300억 달러 이상)을 그대로 쓰고,
매도만 아래 네 가지로 비교합니다.

실행: python largecap_ma.py && MARKET=us python largecap_ma.py && python largecap_ma.py summary
"""
import os
import sys

import pandas as pd

import largecap as L
import strategies as S

EXITS = {
    "손절 -10% + 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25", sl=-0.10)), (0.5, dict(ma="ma60", sl=-0.10))],
    "손절 없이 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))],
    "손절 -7% + 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))],
    "(참고) 40일 보유": [(1, dict(time=40))],
}
MAIN = list(EXITS)[0]


def summary():
    kr = pd.read_csv(os.path.join(S.BASE, "results", "largecap_ma.csv"))
    us = pd.read_csv(os.path.join(S.BASE, "results_us", "largecap_ma.csv"))
    d = kr.merge(us, on=["매수", "시총조건", "매도"], suffixes=("_kr", "_us"))
    pd.set_option("display.width", 340)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda x, a, fmt: (x[f"발견_{a}"].map(lambda v: f(v, fmt)) + " → " + x[f"확인_{a}"].map(lambda v: f(v, fmt))).values

    def show(x):
        return pd.DataFrame({
            "매수": x["매수"].values, "시총": x["시총조건"].values, "매도": x["매도"].values,
            "한국 거래수": arrow(x, "거래수_kr", "{:.0f}"), "승률": arrow(x, "승률_kr", "{:.0%}"),
            "거래평균": arrow(x, "거래평균_kr", "{:+.1%}"), "중간값": arrow(x, "중간값_kr", "{:+.1%}"),
            "수익비율": arrow(x, "수익비율_kr", "{:.0%}"), "-10%손실": arrow(x, "10%이상손실_kr", "{:.0%}"),
            "보유": arrow(x, "보유일_kr", "{:.0f}"),
            "한국 연평균": arrow(x, "연평균_kr", "{:+.1%}"), "한국 샤프": arrow(x, "샤프_kr", "{:.2f}"),
            "한국 낙폭": arrow(x, "최대낙폭_kr", "{:.0%}"),
            "미국 거래평균": arrow(x, "거래평균_us", "{:+.1%}"), "미국 연평균": arrow(x, "연평균_us", "{:+.1%}"),
            "미국 샤프": arrow(x, "샤프_us", "{:.2f}"), "미국 낙폭": arrow(x, "최대낙폭_us", "{:.0%}"),
        })

    print(f"[1] 대형주만 + {MAIN} (발견 2016~22 → 확인 2023~26)")
    print(show(d[(d["시총조건"] == "대형주만") & (d["매도"] == MAIN)]).to_string(index=False))
    print("\n[2] 매수 신호별 매도 비교 (대형주만)")
    print(show(d[d["시총조건"] == "대형주만"].sort_values(["매수", "매도"])).to_string(index=False))
    print(f"\n[3] 대형주 조건 유무 비교 ({MAIN})")
    print(show(d[d["매도"] == MAIN].sort_values(["매수", "시총조건"])).to_string(index=False))


if __name__ == "__main__":
    summary() if len(sys.argv) > 1 and sys.argv[1] == "summary" else L.run_market(EXITS, "largecap_ma.csv")
