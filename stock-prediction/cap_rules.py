"""
대형주에서 규칙 기반 매수 × 매도 방식 계좌 시뮬레이션 (성공 기준·시총 하한은 환경변수)

- 성공(승률): TARGET, WINDOW (예: 60일 안 +30%)
- 대상: 추정 시가총액 CAP_MIN 이상 (한국 1조 원 = 1e12, 미국 100억 달러 = 1e10)
- 매수 규칙: 급등형 / 신고가 돌파형 / 트렌드 템플릿 등, 같은 종목은 WINDOW일 안 중복 매수 제외
- 매도: +TARGET 익절 / WINDOW일 청산, 손절 -10% + 25·60일선, 손절 -10% + 60일 보유,
        손절 -10% + 고점 -15%·-20% 추적, 50% +TARGET 익절 + 50% 고점 -20% 추적
- 계좌: 최대 10종목, 같은 날엔 거래대금 큰 종목부터

실행: TARGET=0.30 WINDOW=60 CAP_MIN=1e12 RESULT_DIR=results_t30w60_cap python cap_rules.py
"""
import os

import numpy as np
import pandas as pd

import best_strategies as B
import largecap as L
import midterm as M
import ml_win as W
import strategies as S
import vcp_test as V

SPLIT = np.datetime64(S.SPLIT_DATE)


def main():
    os.makedirs(S.RESULT_DIR, exist_ok=True)
    p, P, out, ok, dates = M.prepare()
    p["mcap"] = p["close"] * p["code"].map(L.current_caps(p))
    X = W.build_features(p, P, ok)
    y = out["success"].to_numpy()
    base = ok & (p["mcap"] >= W.CAP_MIN).to_numpy()
    rng, r20 = X["range20"].to_numpy(), X["ret20"].to_numpy()
    tvr, bull = X["tv_rank"].to_numpy(), X["bull"].to_numpy() > 0
    nh52, nhall = X["new_high_52w"].to_numpy() > 0, X["new_high_all"].to_numpy() > 0
    tt, gap20 = X["trend_template"].to_numpy() > 0, X["gap_ma20"].to_numpy()
    rules = {
        "하루 변동폭 10% 이상 + 20일 수익률 +50% 이상": (rng >= 0.10) & (r20 >= 0.5),
        "하루 변동폭 10% 이상 + 20일 수익률 +80% 이상": (rng >= 0.10) & (r20 >= 0.8),
        "20일 수익률 +50% 이상": r20 >= 0.5,
        "20일 수익률 +50% 이상 + 상승장": (r20 >= 0.5) & bull,
        "52주 신고가 + 거래대금 상위 30위 + 상승장": nh52 & (tvr <= 30) & bull,
        "역사적 신고가 + 거래대금 상위 10위 + 상승장": nhall & (tvr <= 10) & bull,
        "역사적 신고가 + 상승장": nhall & bull,
        "트렌드 템플릿 + 20일 수익률 +30% 이상 + 상승장": tt & (r20 >= 0.3) & bull,
    }
    T, Wn = S.TARGET, S.WINDOW
    exits = {
        f"+{T:.0%} 익절 / {Wn}일 청산": [(1, dict(tp=T, time=Wn))],
        f"+{T:.0%} 익절 / {Wn}일 청산 / 손절 -10%": [(1, dict(tp=T, time=Wn, sl=-0.10))],
        "손절 -10% + 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25", sl=-0.10)), (0.5, dict(ma="ma60", sl=-0.10))],
        "손절 -10% + 60일 보유": [(1, dict(time=60, sl=-0.10))],
        "손절 -10% + 고점 대비 -15% 추적": [(1, dict(trail=0.15, sl=-0.10))],
        "손절 -10% + 고점 대비 -20% 추적": [(1, dict(trail=0.20, sl=-0.10))],
        f"손절 -10% + 50% +{T:.0%} 익절 + 50% 고점 -20% 추적": [(0.5, dict(tp=T, sl=-0.10)), (0.5, dict(trail=0.20, sl=-0.10))],
    }
    rows = []
    for rname, cond in rules.items():
        sig = pd.Series(cond & base, index=p.index)
        recent = P.shift(P.roll(sig.astype(float), max(S.COOLDOWN, Wn), "sum"), 1).fillna(0)
        r = np.where((sig & (recent == 0)).to_numpy() & ~np.isnan(y))[0]
        if len(r) < 20:
            continue
        m = B.path_matrix(p, P, r)
        early = p["date"].to_numpy()[r] < SPLIT
        for xname, legs in exits.items():
            ret, hold, value = B.run_exit(m, legs)
            t = pd.DataFrame({"date": p["date"].to_numpy()[r], "ret": ret, "hold": hold,
                              "entry_idx": m["date_idx"][:, 0], "tv20": p["tv20"].to_numpy()[r], "row_key": np.arange(len(r))})
            curve = B.portfolio(t, dates, [value[k] for k in range(len(r))])
            row = {"매수": rname, "매도": xname}
            for label, pm, before in [("발견", early, True), ("확인", ~early, False)]:
                cs = V.seg_stats(curve, before)
                row.update({f"{label}_거래수": int(pm.sum()), f"{label}_승률": y[r][pm].mean(),
                            f"{label}_거래평균": ret[pm].mean(), f"{label}_연평균": cs["연평균수익률"],
                            f"{label}_샤프": cs["샤프지수"], f"{label}_최대낙폭": cs["최대낙폭"]})
            rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(S.RESULT_DIR, "cap_rules.csv"), index=False, encoding="utf-8-sig")
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    b = idx[S.BENCH].dropna()
    b = b[b.index >= pd.Timestamp("2017-01-01")]
    bs = [B.curve_stats(b[b.index < pd.Timestamp(S.SPLIT_DATE)]), B.curve_stats(b[b.index >= pd.Timestamp(S.SPLIT_DATE)])]
    print(f"[{S.MARKET.upper()}] 성공 기준 {Wn}일 안 +{T:.0%}, 시총 하한 {W.CAP_MIN:,.0f} / {S.BENCH} 연평균 "
          f"{bs[0]['연평균수익률']:+.1%} → {bs[1]['연평균수익률']:+.1%}, 샤프 {bs[0]['샤프지수']:.2f} → {bs[1]['샤프지수']:.2f}")
    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fm: fm.format(v) if pd.notna(v) else "-"
    ar = lambda a, fm: res[f"발견_{a}"].map(lambda v: f(v, fm)) + " → " + res[f"확인_{a}"].map(lambda v: f(v, fm))
    show = pd.DataFrame({"매수": res["매수"], "매도": res["매도"], "거래수": ar("거래수", "{:.0f}"),
                         "승률": ar("승률", "{:.0%}"), "거래평균": ar("거래평균", "{:+.1%}"),
                         "계좌 연평균": ar("연평균", "{:+.1%}"), "샤프": ar("샤프", "{:.2f}"), "최대낙폭": ar("최대낙폭", "{:.0%}")})
    order = res.sort_values("발견_샤프", ascending=False).index
    print("\n[발견 기간(2016~22) 샤프 순, 상위 15개] (발견 → 확인)")
    print(show.loc[order].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
