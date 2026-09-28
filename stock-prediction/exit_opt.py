"""
매수 고정(역사적 신고가 + 신호일 거래대금 상위 10위 + 상승장)에서 최적의 매도 방식 찾기

- 매도 후보 약 60개: 익절 / 손절 / 기간 청산 / 추적 손절 / 이평선 이탈 / 분할 매도 조합
- 평가: 거래당 평균·중간값·수익 난 비율·보유일, 계좌(최대 10종목) 연평균·최대낙폭
- 고르기는 한국 발견 기간(2016~22)만 사용, 한국 확인 기간과 미국 두 기간으로 검증

실행: python exit_opt.py && MARKET=us python exit_opt.py && python exit_opt.py summary
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
import vcp_test as V
from ath_low_gap import SG_STOCKS

B.H = 250
SPLIT = V.SPLIT
TOP_RANK = 10


def name_of(legs):
    parts = []
    for w, r in legs:
        bits = []
        if "tp" in r:
            bits.append(f"+{r['tp']:.0%} 익절")
        if "trail" in r:
            bits.append(f"고점 -{r['trail']:.0%} 추적")
        if "ma" in r:
            bits.append(f"{r['ma'][2:]}일선 이탈")
        if "time" in r:
            bits.append(f"{r['time']}일 청산")
        if "sl" in r:
            bits.append(f"손절 {r['sl']:.0%}")
        parts.append(("" if w == 1 else f"{w:.0%}: ") + " / ".join(bits))
    return " + ".join(parts)


def exit_candidates():
    c = []
    for tp, t in itertools.product([0.10, 0.15, 0.20, 0.30], [10, 20, 40]):
        c.append([(1, dict(tp=tp, time=t))])
    for tp, sl, t in itertools.product([0.15, 0.20, 0.30], [-0.05, -0.07, -0.10], [20, 40]):
        c.append([(1, dict(tp=tp, sl=sl, time=t))])
    for tr in [0.10, 0.15, 0.20]:
        c.append([(1, dict(trail=tr))])
        c.append([(1, dict(trail=tr, sl=-0.07))])
    for ma in ["ma5", "ma10", "ma20", "ma25"]:
        c.append([(1, dict(ma=ma))])
        c.append([(1, dict(ma=ma, sl=-0.07))])
    c.append([(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))])
    c.append([(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))])
    for tp, other in [(0.15, dict(trail=0.15)), (0.15, dict(ma="ma20")), (0.20, dict(trail=0.20)),
                      (0.15, dict(ma="ma25"))]:
        c.append([(0.5, dict(tp=tp)), (0.5, other)])
        c.append([(0.5, dict(tp=tp, sl=-0.07)), (0.5, {**other, "sl": -0.07})])
    for t in [5, 10, 20, 40, 60]:
        c.append([(1, dict(time=t))])
    return c


def run_market():
    p, P, out, universe, dates = B.load_all()
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    not_sg = ~p["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"])).to_numpy()
    c = p["close"]
    rank = (c * p["volume"]).groupby(p["date"]).rank(ascending=False, method="first").to_numpy()
    sig = ((c > p["hh_all"]) & (P.pos >= 500)).fillna(False)
    recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
    rows_ = np.where((sig & (recent == 0)).to_numpy() & universe & not_sg & p["bull"].to_numpy() & (rank <= TOP_RANK))[0]
    print(f"[{S.MARKET.upper()}] 매수 신호 {len(rows_)}건")
    m = B.path_matrix(p, P, rows_)
    early = p["date"].to_numpy()[rows_] < np.datetime64(SPLIT)
    success = out["success"].to_numpy()[rows_]
    out_rows = []
    for legs in exit_candidates():
        ret, hold, value = B.run_exit(m, legs)
        t = pd.DataFrame({"date": p["date"].to_numpy()[rows_], "ret": ret, "hold": hold,
                          "entry_idx": m["date_idx"][:, 0], "tv20": -rank[rows_], "row_key": np.arange(len(rows_))})
        curve = B.portfolio(t, dates, [value[k] for k in range(len(rows_))])
        row = {"매도": name_of(legs)}
        for label, pm, before in [("발견", early, True), ("확인", ~early, False)]:
            r = ret[pm]
            cs = V.seg_stats(curve, before)
            row.update({f"{label}_거래수": int(pm.sum()), f"{label}_승률": success[pm].mean(),
                        f"{label}_평균": r.mean(), f"{label}_중간값": np.median(r),
                        f"{label}_수익비율": (r > 0).mean(), f"{label}_보유일": hold[pm].mean(),
                        f"{label}_연평균": cs["연평균수익률"], f"{label}_최대낙폭": cs["최대낙폭"],
                        f"{label}_샤프": cs["샤프지수"]})
        out_rows.append(row)
    res = pd.DataFrame(out_rows)
    res.to_csv(os.path.join(S.RESULT_DIR, "exit_opt.csv"), index=False, encoding="utf-8-sig")
    print(f"   매도 후보 {len(res)}개 계산 완료 → {S.RESULT_DIR}/exit_opt.csv")


def summary():
    kr = pd.read_csv(os.path.join(S.BASE, "results", "exit_opt.csv"))
    us = pd.read_csv(os.path.join(S.BASE, "results_us", "exit_opt.csv"))
    d = kr.merge(us, on="매도", suffixes=("_kr", "_us"))
    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"

    def show(x):
        out = pd.DataFrame({"매도": x["매도"]})
        for mk, lab in [("kr", "한국"), ("us", "미국")]:
            out[f"{lab} 거래평균"] = (x[f"발견_평균_{mk}"].map(lambda v: f(v, "{:+.1%}")) + " → "
                                   + x[f"확인_평균_{mk}"].map(lambda v: f(v, "{:+.1%}")))
            out[f"{lab} 계좌 연평균"] = (x[f"발견_연평균_{mk}"].map(lambda v: f(v, "{:+.1%}")) + " → "
                                     + x[f"확인_연평균_{mk}"].map(lambda v: f(v, "{:+.1%}")))
            out[f"{lab} 최대낙폭"] = (x[f"발견_최대낙폭_{mk}"].map(lambda v: f(v, "{:.0%}")) + " → "
                                   + x[f"확인_최대낙폭_{mk}"].map(lambda v: f(v, "{:.0%}")))
        out["한국 수익비율"] = (x["발견_수익비율_kr"].map(lambda v: f(v, "{:.0%}")) + " → "
                           + x["확인_수익비율_kr"].map(lambda v: f(v, "{:.0%}")))
        out["한국 보유일"] = x["발견_보유일_kr"].map(lambda v: f(v, "{:.0f}"))
        return out

    d["발견순위"] = d["발견_평균_kr"].rank(ascending=False)
    print("[1] 한국 발견 기간(2016~22) 거래당 평균으로 고른 상위 10개 → 나머지 세 곳에서 검증 (발견 → 확인)")
    top = d.sort_values("발견_평균_kr", ascending=False).head(10)
    print(show(top).to_string(index=False))
    cols = ["발견_평균_kr", "확인_평균_kr", "발견_평균_us", "확인_평균_us"]
    d["네 곳 최소"] = d[cols].min(axis=1)
    d["네 곳 모두 플러스"] = (d[cols] > 0).all(axis=1)
    print(f"\n[2] 네 곳(한국·미국 × 두 기간) 모두 거래당 평균이 플러스인 매도: {int(d['네 곳 모두 플러스'].sum())}개 / {len(d)}개")
    print(show(d[d["네 곳 모두 플러스"]].sort_values("네 곳 최소", ascending=False)).to_string(index=False))
    for key in ["+15% 익절 / 20일 청산", "50%: 25일선 이탈 + 50%: 60일선 이탈", "20일 청산"]:
        if key in set(d["매도"]):
            print(f"\n참고 [{key}] 한국 발견 기간 순위 {int(d.loc[d['매도'] == key, '발견순위'].iloc[0])}위")
    d.to_csv(os.path.join(S.BASE, "results", "exit_opt_summary.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    summary() if len(sys.argv) > 1 and sys.argv[1] == "summary" else run_market()
