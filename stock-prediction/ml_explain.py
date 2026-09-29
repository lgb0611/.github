"""
머신러닝 모델(ml_win.py)이 고른 종목은 어떤 종목인가 + 사람이 쓸 수 있는 간단한 규칙으로 흉내 내기

1) 매일 확률 상위 3종목(2023~2026)의 특징을 같은 날 전체 종목과 비교
2) 2016~2022 데이터로 깊이 3짜리 결정나무를 학습해 "만약 ~이면" 규칙을 만들고, 2023~2026에서 승률 확인

실행: python ml_explain.py   /   MARKET=us python ml_explain.py   (ml_win.py를 먼저 실행해야 함)
"""
import os

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text

import largecap as L
import midterm as M
import ml_win as W
import strategies as S

SHOW = {  # 특징 이름: (설명, 표시 형식)
    "range20": ("최근 20일 평균 하루 변동폭 (고가-저가)/종가", "{:.1%}"),
    "vol60": ("최근 60일 일간 수익률 표준편차", "{:.1%}"),
    "box60": ("직전 60일 최고가 / 최저가 - 1", "{:.0%}"),
    "ret20": ("최근 20일 수익률", "{:+.0%}"),
    "ret250": ("최근 1년 수익률", "{:+.0%}"),
    "gap_ll250": ("52주 최저가 대비 위치", "{:+.0%}"),
    "gap_hh250": ("52주 최고가 대비 위치", "{:+.0%}"),
    "gap_ma20": ("20일선 이격도", "{:+.0%}"),
    "ret1": ("당일 상승률", "{:+.1%}"),
    "vol_x20": ("거래량 / 20일 평균", "{:.1f}배"),
    "tv_rank": ("당일 거래대금 순위", "{:.0f}위"),
    "log_mcap": ("추정 시가총액", "mcap"),
    "mkt_ret20": ("시장 지수 20일 수익률", "{:+.1%}"),
    "breadth20": ("20일선 위 종목 비율", "{:.0%}"),
}


def fmt(name, v):
    f = SHOW[name][1]
    if f == "mcap":
        cap = np.exp(v)
        return f"{cap / 1e8:,.0f}억 원" if S.MARKET == "kr" else f"${cap / 1e9:,.1f}B"
    return f.format(v)


def main():
    p, P, out, ok, dates = M.prepare()
    p["mcap"] = p["close"] * p["code"].map(L.current_caps(p))
    X = W.build_features(p, P, ok)
    y = out["success"].to_numpy()
    year = p["date"].dt.year.to_numpy()
    valid = ok & ~np.isnan(y)

    picks = pd.read_csv(os.path.join(S.RESULT_DIR, "ml_win_picks.csv"), dtype={"code": str}, parse_dates=["date"])
    picks = picks[picks["rank_day"] <= 3]
    key = pd.MultiIndex.from_frame(p[["code", "date"]])
    pick_rows = key.get_indexer(pd.MultiIndex.from_frame(picks[["code", "date"]]))
    test = np.where(valid & (year >= 2023))[0]

    print(f"[{S.MARKET.upper()}] 1) 모델이 고른 종목(매일 상위 3종목, {len(pick_rows)}건) vs 같은 기간 전체 종목 — 중간값")
    pct = X.iloc[test].groupby(p["date"].iloc[test].to_numpy()).rank(pct=True)
    pct_of_pick = pct.reindex(p.index[pick_rows])
    rows = []
    for name, (desc, _) in SHOW.items():
        rows.append({"특징": desc, "모델이 고른 종목": fmt(name, np.nanmedian(X[name].iloc[pick_rows])),
                     "전체 종목": fmt(name, np.nanmedian(X[name].iloc[test])),
                     "그날 전체 중 상위 몇 %": f"{1 - np.nanmedian(pct_of_pick[name]):.0%}"})
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n2) 사람이 쓸 수 있는 규칙으로 흉내 내기: 2016~2022로 깊이 3 결정나무 학습 → 2023~2026 승률")
    feats = ["range20", "vol60", "box60", "mkt_ret20", "gap_ll250", "log_mcap", "breadth20", "ret20", "gap_hh250", "tv_rank"]
    tr = np.where(valid & (year <= 2022))[0]
    Xtr = X[feats].iloc[tr].fillna(-999)
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=3000, random_state=0).fit(Xtr, y[tr])
    print(export_text(tree, feature_names=feats, decimals=3, show_weights=False))
    leaf_tr = tree.apply(Xtr)
    leaf_te = tree.apply(X[feats].iloc[test].fillna(-999))
    res = []
    for leaf in np.unique(leaf_tr):
        a, b = y[tr][leaf_tr == leaf], y[test][leaf_te == leaf]
        res.append({"잎": leaf, "2016~22 거래수": len(a), "2016~22 승률": a.mean(),
                    "2023~26 거래수": len(b), "2023~26 승률": b.mean() if len(b) else np.nan})
    res = pd.DataFrame(res).sort_values("2016~22 승률", ascending=False)
    res["2016~22 승률"] = res["2016~22 승률"].map("{:.1%}".format)
    res["2023~26 승률"] = res["2023~26 승률"].map(lambda v: f"{v:.1%}" if pd.notna(v) else "-")
    print(res.to_string(index=False))
    print(f"   참고: 2023~26 전체 승률 {y[test].mean():.1%}, 모델 매일 상위 3종목 승률 {np.nanmean(y[pick_rows]):.1%}")


if __name__ == "__main__":
    main()
