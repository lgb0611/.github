"""
신고가 돌파 전략 다듬기

고정
- 매수: 52주 신고가 돌파 (종가가 어제까지 250일 최고가 위) + 상승장(지수 60일선 위), 다음날 시가 매수
- 성공: 매수 후 20거래일 안에 고가 +15% 이상
- 매도: +15% 익절 / 20일째 종가 청산 / 손절 없음 (3부에서 가장 좋았던 규칙)

다듬는 것
1) 어떤 특징의 돌파가 더 잘 되나? (거래량, 당일 상승률, 이격도, 역사적 신고가 여부, 돌파 전 조정 폭 등)
2) 매수 필터: 좋은 돌파만 고르기
3) 우선순위: 같은 날 신호가 많을 때 무엇부터 살지
4) 동시 보유 종목 수: 5 / 10 / 20

모든 선택은 2016~2022(발견 기간) 결과로만 하고, 2023~2026(확인 기간)으로 검증합니다.

실행: python refine_breakout.py   (collect_data.py를 먼저 실행해야 함)
"""
import itertools
import os

import matplotlib
import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULT_DIR = S.RESULT_DIR
SPLIT_DATE = S.SPLIT_DATE
EXIT_RULE = "익절 +15% / 20일 청산 (손절 없음)"


def build_trades():
    p, P, out, universe, dates = B.load_all()
    c = p["close"]

    # ---- 신호 당일에 알 수 있는 특징들 ----
    p["f_vol_x"] = p["volume"] / p["vma20"]                       # 거래량 배수 (평소 대비)
    p["f_ret1"] = p["ret1"]                                       # 당일 상승률
    p["f_breakout_gap"] = c / p["hh250"] - 1                      # 신고가를 얼마나 넘었나
    p["f_ma20_gap"] = c / p["ma20"] - 1                           # 20일선 이격도
    p["f_ma60_gap"] = c / p["ma60"] - 1                           # 60일선 이격도
    p["f_ret120"] = c / P.shift(c, 120) - 1                       # 6개월 수익률
    p["f_base_depth"] = P.shift(P.roll(p["low"], 60, "min"), 1) / p["hh250"] - 1  # 돌파 전 60일 최저가가 고점 대비 얼마나 낮았나
    p["f_vol20"] = P.roll(p["ret1"], 20, "std")                   # 최근 변동성
    p["f_ath"] = ((c > p["hh_all"]) & (P.pos >= 500)).astype(float)  # 역사적 신고가(10년 내) 여부
    p["f_tv20"] = p["tv20"]                                       # 20일 평균 거래대금
    p["f_upper_wick"] = (p["high"] - c) / (p["high"] - p["low"] + 1e-9)  # 윗꼬리 비율 (0 = 고가 마감)
    # 시장 지수 20일 수익률 (시장 모멘텀)
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet"))
    idx["mkt_ret20"] = idx.groupby("index")["close"].pct_change(20)
    p["f_mkt_ret20"] = B.lookup_index(idx, "mkt_ret20", p)

    sig = (c > p["hh250"]).fillna(False)
    recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
    sig = (sig & (recent == 0) & p["bull"]).to_numpy() & universe

    rows = np.where(sig)[0]
    m = B.path_matrix(p, P, rows)
    ret, hold, value = B.run_exit(m, B.EXITS[EXIT_RULE])
    feats = [col for col in p.columns if col.startswith("f_")]
    t = p.loc[rows, ["date", "code", "market"] + feats].reset_index(drop=True)
    t["ret"] = ret
    t["hold"] = hold
    t["success"] = out["success"].to_numpy()[rows]
    t["entry_idx"] = m["date_idx"][:, 0]
    t["row_key"] = np.arange(len(t))
    t["early"] = t["date"] < SPLIT_DATE
    return t, [value[i] for i in range(len(t))], dates, feats


FEATURE_NAMES = {
    "f_vol_x": "거래량 배수", "f_ret1": "당일 상승률", "f_breakout_gap": "신고가 돌파 폭",
    "f_ma20_gap": "20일선 이격도", "f_ma60_gap": "60일선 이격도", "f_ret120": "6개월 수익률",
    "f_base_depth": "돌파 전 조정 폭", "f_vol20": "변동성", "f_ath": "역사적 신고가",
    "f_tv20": "거래대금", "f_upper_wick": "윗꼬리 비율", "f_mkt_ret20": "시장 20일 수익률",
}


def feature_analysis(t, feats):
    """특징마다 5구간으로 나눠 구간별 평균수익·승률을 발견/확인 기간 따로 계산."""
    rows = []
    for f in feats:
        if f == "f_ath":
            bucket = t[f].map({0.0: "아님", 1.0: "역사적 신고가"})
        else:
            edges = t.loc[t["early"], f].quantile([0, .2, .4, .6, .8, 1]).to_numpy()  # 구간 경계는 발견 기간 기준
            edges[0], edges[-1] = -np.inf, np.inf
            bucket = pd.cut(t[f], np.unique(edges), labels=False) + 1
        for b, g in t.groupby(bucket):
            e, l = g[g["early"]], g[~g["early"]]
            rows.append({"특징": FEATURE_NAMES[f], "구간": b,
                         "범위": f"{g[f].min():.3g} ~ {g[f].max():.3g}",
                         "발견_승률": e["success"].mean(), "발견_평균": e["ret"].mean(),
                         "확인_승률": l["success"].mean(), "확인_평균": l["ret"].mean(),
                         "신호수": len(g)})
    return pd.DataFrame(rows)


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 52주 신고가 돌파 [상승장만] 거래 모으는 중...")
    t, paths, dates, feats = build_trades()
    print(f"   거래 {len(t):,}건 (발견 {t['early'].sum():,} / 확인 {(~t['early']).sum():,})")

    print("\n2) 특징별 5구간 분석 (1 = 낮음, 5 = 높음)")
    fa = feature_analysis(t, feats)
    fa.to_csv(os.path.join(RESULT_DIR, "breakout_features.csv"), index=False, encoding="utf-8-sig")
    show = fa.copy()
    for col in ["발견_승률", "확인_승률"]:
        show[col] = show[col].map("{:.1%}".format)
    for col in ["발견_평균", "확인_평균"]:
        show[col] = show[col].map("{:+.2%}".format)
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    print(show.to_string(index=False))

    # ---- 3) 필터 × 우선순위 × 보유 종목 수 계좌 시뮬레이션 ----
    early = t[t["early"]]
    q = lambda f: early[f].quantile(0.4)   # 기준값은 발견 기간 하위 40% 경계 (확인 기간은 안 봄)
    filters = {
        "필터 없음": pd.Series(True, index=t.index),
        f"거래량 {q('f_vol_x'):.1f}배 이상": t["f_vol_x"] >= q("f_vol_x"),
        f"당일 {q('f_ret1'):.1%} 이상 상승": t["f_ret1"] >= q("f_ret1"),
        f"변동성 {q('f_vol20'):.1%} 이상": t["f_vol20"] >= q("f_vol20"),
        f"20일선 이격도 {q('f_ma20_gap'):.0%} 이상": t["f_ma20_gap"] >= q("f_ma20_gap"),
        "역사적 신고가만": t["f_ath"] == 1,
        "변동성 + 거래량 둘 다": (t["f_vol20"] >= q("f_vol20")) & (t["f_vol_x"] >= q("f_vol_x")),
    }
    rng = np.random.default_rng(0)
    t["p_random"] = rng.random(len(t))
    t["p_tv"] = t["f_tv20"]
    t["p_vol_x"] = t["f_vol_x"]
    t["p_ret1"] = t["f_ret1"]
    t["p_small_ret1"] = -t["f_ret1"]
    t["p_vol20"] = t["f_vol20"]
    t["p_ath_tv"] = t["f_ath"] * 1e15 + t["f_tv20"]
    priorities = {
        "무작위": "p_random", "거래대금 큰 순": "p_tv", "거래량 배수 큰 순": "p_vol_x",
        "당일 상승률 큰 순": "p_ret1", "당일 상승률 작은 순": "p_small_ret1",
        "변동성 큰 순": "p_vol20", "역사적 신고가 먼저 → 거래대금 순": "p_ath_tv",
    }
    slot_options = [5, 10, 20]

    split = pd.Timestamp(SPLIT_DATE)
    print(f"\n3) 계좌 시뮬레이션: 필터 {len(filters)} × 우선순위 {len(priorities)} × 보유 종목 수 {len(slot_options)}"
          f" = {len(filters) * len(priorities) * len(slot_options)}개")
    sims, curves = [], {}
    for (fname, fmask), (pname, pkey), slots in itertools.product(
            filters.items(), priorities.items(), slot_options):
        sub = t[fmask]
        c = B.portfolio(sub, dates, paths, key=pkey, slots=slots)
        e_st, l_st = B.curve_stats(c[c.index < split]), B.curve_stats(c[c.index >= split])
        sims.append({
            "필터": fname, "우선순위": pname, "보유수": slots,
            "발견_승률": sub.loc[sub["early"], "success"].mean(), "확인_승률": sub.loc[~sub["early"], "success"].mean(),
            "발견_거래평균": sub.loc[sub["early"], "ret"].mean(), "확인_거래평균": sub.loc[~sub["early"], "ret"].mean(),
            **{f"발견_{k}": v for k, v in e_st.items()}, **{f"확인_{k}": v for k, v in l_st.items()},
        })
        curves[(fname, pname, slots)] = c
    sim = pd.DataFrame(sims)
    sim.to_csv(os.path.join(RESULT_DIR, "breakout_grid.csv"), index=False, encoding="utf-8-sig")

    def fmt(df):
        out = df[["필터", "우선순위", "보유수"]].copy()
        for a, b in [("발견_승률", "확인_승률"), ("발견_거래평균", "확인_거래평균"),
                     ("발견_연평균수익률", "확인_연평균수익률"), ("발견_최대낙폭", "확인_최대낙폭")]:
            f = "{:.1%}" if "승률" in a else "{:+.1%}" if "평균" in a and "거래" not in a or "낙폭" in a else "{:+.2%}"
            out[a.replace("발견_", "")] = df[a].map(f.format) + " → " + df[b].map(f.format)
        out["샤프"] = df["발견_샤프지수"].map("{:.2f}".format) + " → " + df["확인_샤프지수"].map("{:.2f}".format)
        return out

    print("\n[각 필터별 최선 조합] 발견 기간 샤프지수로 선정, 표기는 '발견 → 확인'")
    best_per_filter = sim.loc[sim.groupby("필터")["발견_샤프지수"].idxmax()].sort_values("발견_샤프지수", ascending=False)
    print(fmt(best_per_filter).to_string(index=False))

    print("\n[우선순위별 평균] (모든 필터·보유수 평균, 발견 → 확인 샤프지수)")
    pr = sim.groupby("우선순위")[["발견_샤프지수", "확인_샤프지수", "발견_연평균수익률", "확인_연평균수익률"]].mean()
    print(pr.sort_values("발견_샤프지수", ascending=False).round(3).to_string())

    print("\n[보유 종목 수별 평균]")
    sl = sim.groupby("보유수")[["발견_샤프지수", "확인_샤프지수", "발견_최대낙폭", "확인_최대낙폭"]].mean()
    print(sl.round(3).to_string())

    # 최종 선택: 발견 기간 샤프지수 1위
    final = sim.loc[sim["발견_샤프지수"].idxmax()]
    base = sim[(sim["필터"] == "필터 없음") & (sim["우선순위"] == "거래대금 큰 순") & (sim["보유수"] == 10)].iloc[0]
    print("\n[최종 선택 vs 3부 전략(필터 없음, 거래대금 순, 10종목)]")
    print(fmt(pd.DataFrame([final, base])).to_string(index=False))

    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    fig, ax = plt.subplots(figsize=(12, 5.5))
    for row, label in [(final, "Refined"), (base, "Part 3 (no filter, trading value, 10 slots)")]:
        c = curves[(row["필터"], row["우선순위"], row["보유수"])]
        ax.plot(c / c.iloc[0], label=label)
    ref = curves[(final["필터"], final["우선순위"], final["보유수"])]
    for name, color in [("KOSPI", "black"), ("KOSDAQ", "gray")]:
        s = idx[name].reindex(ref.index).ffill()
        ax.plot(s / s.iloc[0], label=name, color=color, linestyle="--")
    ax.axvline(split, color="k", alpha=0.3)
    ax.set_yscale("log")
    ax.set_title("52-week high breakout: refined vs before (log scale)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "breakout_refined.png"), dpi=110)


if __name__ == "__main__":
    main()
