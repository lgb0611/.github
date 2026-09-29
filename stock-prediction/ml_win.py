"""
"20일 안에 고가 +15% 이상"을 가장 자주 맞히는 전략 — 머신러닝(LightGBM)으로 모든 정보 결합

- 특징 약 40개: 수익률, 변동성, 이평선 거리, 신고가 거리, 거래량·거래대금·거래대금 순위,
  추정 시가총액, RS, 트렌드 템플릿, 캔들 모양, 시장 흐름(지수 수익률, 상승장, 20일선 위 종목 비율)
- 정답: 다음날 시가 매수 후 20거래일 안에 고가 +15% 이상 (성공)
- 워크포워드: 2023·2024·2025·2026년을 예측할 때마다 그 전 해까지의 데이터로만 새로 학습
  (직전 1년은 조기 종료용 검증, 학습·검증·예측 사이 20거래일 간격)
- 평가: 매일 확률 상위 K종목의 승률, 확률 기준별 승률, 매도 방식별 손익·계좌(최대 10종목)

실행: python ml_win.py   /   MARKET=us python ml_win.py
성공 기준 바꾸기: TARGET=0.30 WINDOW=40 RESULT_DIR=results_t30w40 python ml_win.py  (40일 안 +30%)
대형주만: CAP_MIN=1e12 (한국 1조 원) / CAP_MIN=1e10 (미국 100억 달러) — 학습·예측 모두 이 종목들로만
"""
import os

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import best_strategies as B
import largecap as L
import midterm as M
import strategies as S
import vcp_test as V

TEST_YEARS = [2023, 2024, 2025, 2026]
EMBARGO = 20
CAP_MIN = float(os.environ.get("CAP_MIN", 0))          # 추정 시가총액 하한 (0이면 조건 없음)
EXITS = {
    f"+{S.TARGET:.0%} 익절 / {S.WINDOW}일 청산": [(1, dict(tp=S.TARGET, time=S.WINDOW))],
    "손절 -10% + 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25", sl=-0.10)), (0.5, dict(ma="ma60", sl=-0.10))],
    "손절 -10% + 60일 보유": [(1, dict(time=60, sl=-0.10))],
    "손절 -10% + 고점 대비 -15% 추적": [(1, dict(trail=0.15, sl=-0.10))],
}
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_child_samples=1000,
              feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1, seed=0)


def build_features(p, P, ok):
    c, h, l, v = p["close"], p["high"], p["low"], p["volume"]
    F = {}
    for n in [1, 5, 20, 60, 120, 250]:
        F[f"ret{n}"] = c / P.shift(c, n) - 1
    F["vol20"] = P.roll(p["ret1"], 20, "std")
    F["vol60"] = P.roll(p["ret1"], 60, "std")
    F["range20"] = P.roll((h - l) / c, 20)
    for n in [5, 20, 60, 120, 200]:
        F[f"gap_ma{n}"] = c / p[f"ma{n}"] - 1
    F["gap_hh20"] = c / p["hh20"] - 1
    F["gap_hh250"] = c / p["hh250"] - 1
    F["gap_hh_all"] = c / p["hh_all"] - 1
    F["gap_ll250"] = c / p["ll250"] - 1
    F["vol_x20"] = v / p["vma20"]
    F["vol_x50"] = v / p["vma50"]
    F["log_tv20"] = np.log1p(p["tv20"])
    tv = c * v
    F["tv_rank"] = tv.groupby(p["date"]).rank(ascending=False, method="first")
    F["tv_rank_pct"] = tv.groupby(p["date"]).rank(pct=True)
    F["log_mcap"] = np.log(p["mcap"])
    F["rs"] = p["rs"]
    F["trend_template"] = p["trend_template"].astype(float)
    F["close_pos"] = (c - l) / (h - l + 1e-9)                   # 종가가 하루 범위 중 어디쯤 (1 = 고가 마감)
    F["upper_wick"] = (h - np.maximum(c, p["open"])) / (h - l + 1e-9)
    F["gap_open"] = p["open"] / p["prev_close"] - 1
    F["up_days3"] = p["up_days3"]
    F["rsi"] = p["rsi"]
    F["bb_width"] = p["bb_width"]
    F["box60"] = p["box60"]
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet"))
    idx["r20"] = idx.groupby("index")["close"].pct_change(20)
    idx["r5"] = idx.groupby("index")["close"].pct_change(5)
    F["mkt_ret20"] = B.lookup_index(idx, "r20", p)
    F["mkt_ret5"] = B.lookup_index(idx, "r5", p)
    F["bull"] = p["bull"].astype(float)
    above = pd.Series(np.where(ok, (c > p["ma20"]).astype(float), np.nan), index=p.index)
    F["breadth20"] = p["date"].map(above.groupby(p["date"]).mean())    # 그날 20일선 위 종목 비율
    F["new_high_52w"] = (c > p["hh250"]).astype(float)
    F["new_high_all"] = ((c > p["hh_all"]) & (P.pos >= 500)).astype(float)
    X = pd.DataFrame(F).astype("float32")
    return X.replace([np.inf, -np.inf], np.nan)


def main():
    os.makedirs(S.RESULT_DIR, exist_ok=True)
    print(f"[{S.MARKET.upper()}] 1) 데이터·특징 준비 중...")
    p, P, out, ok, dates = M.prepare()
    p["mcap"] = p["close"] * p["code"].map(L.current_caps(p))
    X = build_features(p, P, ok)
    y = out["success"].to_numpy()
    year = p["date"].dt.year.to_numpy()
    didx = p["date_idx"].to_numpy()
    big = (p["mcap"] >= CAP_MIN).to_numpy() if CAP_MIN else np.ones(len(p), bool)
    rows = np.where(ok & ~np.isnan(y) & big)[0]
    print(f"   시가총액 하한 {CAP_MIN:,.0f}, 학습 가능한 행 {len(rows):,}개, 특징 {X.shape[1]}개, 전체 승률 {np.nanmean(y[rows]):.1%}")

    preds = pd.Series(np.nan, index=p.index)
    importances = []
    for ty in TEST_YEARS:
        first_test = didx[rows][year[rows] == ty].min()
        tr = rows[(year[rows] < ty - 1) & (didx[rows] < first_test - 250 - EMBARGO)]
        va = rows[(year[rows] == ty - 1) & (didx[rows] < first_test - EMBARGO)]
        te = rows[year[rows] == ty]
        model = lgb.train(PARAMS, lgb.Dataset(X.iloc[tr], y[tr]), num_boost_round=2000,
                          valid_sets=[lgb.Dataset(X.iloc[va], y[va])],
                          callbacks=[lgb.early_stopping(100, verbose=False)])
        preds.iloc[te] = model.predict(X.iloc[te], num_iteration=model.best_iteration)
        importances.append(pd.Series(model.feature_importance("gain"), index=X.columns))
        print(f"   {ty}년 예측: 학습 {len(tr):,} / 검증 {len(va):,} / 예측 {len(te):,}, "
              f"AUC {roc_auc_score(y[te], preds.iloc[te]):.3f}")

    test = rows[year[rows] >= TEST_YEARS[0]]
    prob = preds.to_numpy()
    df = pd.DataFrame({"row": test, "date": p["date"].to_numpy()[test], "year": year[test],
                       "prob": prob[test], "y": y[test], "code": p["code"].to_numpy()[test]})
    df["rank_day"] = df.groupby("date")["prob"].rank(ascending=False, method="first")
    print(f"\n2) 시험 기간(2023~2026) 전체 AUC {roc_auc_score(df['y'], df['prob']):.3f}, 아무 종목·아무 날 승률 {df['y'].mean():.1%}")

    print(f"\n[매일 확률 상위 K종목을 샀을 때 승률 ({S.WINDOW}일 안에 +{S.TARGET:.0%})]")
    lines = []
    for k in [1, 3, 5, 10, 20]:
        s = df[df["rank_day"] <= k]
        by = s.groupby("year")["y"].mean()
        lines.append({"상위": f"{k}종목/일", "거래수": len(s), "승률": f"{s['y'].mean():.1%}",
                      **{str(yy): f"{by.get(yy, np.nan):.0%}" for yy in TEST_YEARS}})
    print(pd.DataFrame(lines).to_string(index=False))

    print("\n[확률 기준별 승률]")
    lines = []
    for th in [0.4, 0.5, 0.6, 0.7, 0.8]:
        s = df[df["prob"] >= th]
        if len(s) == 0:
            continue
        by = s.groupby("year")["y"].mean()
        lines.append({"확률 ≥": th, "거래수": len(s), "하루 평균": f"{len(s) / df['date'].nunique():.1f}건",
                      "승률": f"{s['y'].mean():.1%}", **{str(yy): f"{by.get(yy, np.nan):.0%}" for yy in TEST_YEARS}})
    print(pd.DataFrame(lines).to_string(index=False))

    # ---- 손익: 매일 확률 상위 3종목 (같은 종목 20일 안 중복 매수 제외) ----
    pick = df[df["rank_day"] <= 3].sort_values("date")
    last_buy, keep = {}, []            # 같은 종목은 성공 판정 기간 안에 다시 사지 않음
    for r, code, d in zip(pick["row"], pick["code"], p["date_idx"].to_numpy()[pick["row"]]):
        if code in last_buy and d - last_buy[code] < max(S.COOLDOWN, S.WINDOW):
            continue
        last_buy[code] = d
        keep.append(r)
    keep = np.array(keep)
    m = B.path_matrix(p, P, keep)
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    bench = idx[S.BENCH].dropna()
    bench = bench[bench.index >= pd.Timestamp("2023-01-01")]
    print(f"\n[매일 확률 상위 3종목 매수 ({max(S.COOLDOWN, S.WINDOW)}일 안 중복 제외) — {len(keep)}건, 승률 {np.mean(y[keep]):.1%}]")
    print(f"   비교: {S.BENCH} 지수 2023~2026 연평균 {B.curve_stats(bench)['연평균수익률']:+.1%}, "
          f"최대낙폭 {B.curve_stats(bench)['최대낙폭']:.0%}")
    res = []
    for xname, legs in EXITS.items():
        ret, hold, value = B.run_exit(m, legs)
        t = pd.DataFrame({"ret": ret, "hold": hold, "entry_idx": m["date_idx"][:, 0],
                          "tv20": prob[keep], "row_key": np.arange(len(keep))})
        curve = B.portfolio(t, dates, [value[k] for k in range(len(keep))])
        cs = B.curve_stats(curve)
        yr = curve.resample("YE").last()
        yr = pd.concat([pd.Series([curve.iloc[0]], index=[curve.index[0]]), yr]).pct_change().dropna()
        res.append({"매도": xname, "거래당 평균": f"{ret.mean():+.1%}", "중간값": f"{np.median(ret):+.1%}",
                    "수익 난 비율": f"{(ret > 0).mean():.0%}", "보유": f"{hold.mean():.0f}일",
                    "계좌 연평균": f"{cs['연평균수익률']:+.1%}", "샤프": f"{cs['샤프지수']:.2f}",
                    "최대낙폭": f"{cs['최대낙폭']:.0%}",
                    **{str(d.year): f"{v:+.0%}" for d, v in yr.items()}})
    print(pd.DataFrame(res).to_string(index=False))

    imp = pd.concat(importances, axis=1).mean(axis=1).sort_values(ascending=False)
    print("\n[모델이 중요하게 본 특징 상위 10개]")
    print((imp / imp.sum()).head(10).map("{:.1%}".format).to_string())
    picks = df[df["rank_day"] <= 3].merge(
        pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})[["code", "name"]], on="code", how="left")
    picks.drop(columns="row").to_csv(os.path.join(S.RESULT_DIR, "ml_win_picks.csv"), index=False, encoding="utf-8-sig")
    (imp / imp.sum()).to_csv(os.path.join(S.RESULT_DIR, "ml_win_importance.csv"), encoding="utf-8-sig")
    pd.DataFrame(res).to_csv(os.path.join(S.RESULT_DIR, "ml_win_exits.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
