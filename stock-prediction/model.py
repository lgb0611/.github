"""
주가 예측 모델: "앞으로 5거래일 동안 이 종목이 다른 종목들보다 많이 오를까?"를 예측합니다.

주가 '숫자' 자체를 맞히는 건 거의 불가능하므로,
매주 전 종목 중 '상대적으로 더 오를 종목'의 순위를 매기는 방식으로 문제를 바꿨습니다.

실행: python model.py   (collect_data.py를 먼저 실행해야 함)
결과: results/ 폴더에 성과 요약, 차트, 중요 변수 저장
"""
import os

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "data")
RESULT_DIR = os.path.join(BASE, "results")

HORIZON = 5            # 며칠 뒤를 예측할지 (5거래일 = 약 1주)
TOP_N = 20             # 매주 살 종목 수
COST = 0.0025          # 사고팔 때 드는 비용 합계 (수수료 + 거래세 + 슬리피지 추정, 0.25%)
MIN_TRADING_VALUE = 1e9  # 최근 20일 평균 거래대금 10억 원 이상만 (너무 거래가 적은 종목 제외)
TRAIN_END = "2022-12-31"   # 학습 기간: 2016 ~ 2022
VALID_END = "2023-12-31"   # 검증 기간: 2023
                           # 시험 기간: 2024 ~ 현재 (모델이 한 번도 보지 못한 데이터)

FEATURES = [
    "ret_1", "ret_5", "ret_20", "ret_60", "ret_120", "ret_250",
    "vol_20", "vol_60", "ma_gap_5", "ma_gap_20", "ma_gap_60", "ma_gap_120",
    "high_gap_250", "low_gap_250", "rsi_14", "volume_ratio", "log_trading_value",
    "range_20", "mkt_ret_5", "mkt_ret_20",
]


def make_features(p):
    """과거 가격만으로 종목의 특징(지표)을 계산합니다. 미래 정보는 절대 쓰지 않습니다."""
    p = p.sort_values(["code", "date"]).copy()
    # 거래정지일은 시가가 0으로 들어와 있으므로 종가로 채움
    p.loc[p["open"] == 0, ["open", "high", "low"]] = np.nan
    for c in ["open", "high", "low"]:
        p[c] = p[c].fillna(p["close"])

    g = p.groupby("code", group_keys=False)
    close = p["close"]
    daily_ret = g["close"].pct_change()
    p["daily_ret"] = daily_ret
    p["trading_value"] = close * p["volume"]

    # 수익률: 최근 n일 동안 얼마나 올랐나
    for n in [1, 5, 20, 60, 120, 250]:
        p[f"ret_{n}"] = g["close"].pct_change(n)
    # 변동성: 얼마나 출렁이나
    p["vol_20"] = g["daily_ret"].transform(lambda s: s.rolling(20).std())
    p["vol_60"] = g["daily_ret"].transform(lambda s: s.rolling(60).std())
    # 이동평균과의 거리
    for n in [5, 20, 60, 120]:
        p[f"ma_gap_{n}"] = close / g["close"].transform(lambda s: s.rolling(n).mean()) - 1
    # 1년 최고가/최저가 대비 위치
    p["high_gap_250"] = close / g["high"].transform(lambda s: s.rolling(250).max()) - 1
    p["low_gap_250"] = close / g["low"].transform(lambda s: s.rolling(250).min()) - 1
    # RSI (과매수/과매도 지표)
    up = daily_ret.clip(lower=0)
    down = -daily_ret.clip(upper=0)
    avg_up = up.groupby(p["code"]).transform(lambda s: s.rolling(14).mean())
    avg_down = down.groupby(p["code"]).transform(lambda s: s.rolling(14).mean())
    p["rsi_14"] = avg_up / (avg_up + avg_down + 1e-12)
    # 거래량: 최근 5일이 평소(60일)보다 많은가
    p["volume_ratio"] = (g["volume"].transform(lambda s: s.rolling(5).mean())
                         / (g["volume"].transform(lambda s: s.rolling(60).mean()) + 1))
    p["avg_trading_value_20"] = g["trading_value"].transform(lambda s: s.rolling(20).mean())
    p["log_trading_value"] = np.log1p(p["avg_trading_value_20"])
    # 최근 20일 평균 하루 변동폭
    p["range_20"] = ((p["high"] - p["low"]) / close).groupby(p["code"]).transform(
        lambda s: s.rolling(20).mean())

    # 시장 전체 흐름 (전 종목 평균 수익률)
    mkt = p.groupby("date")["daily_ret"].mean().clip(-0.2, 0.2)
    mkt_index = (1 + mkt.fillna(0)).cumprod()
    p["mkt_ret_5"] = p["date"].map(mkt_index.pct_change(5))
    p["mkt_ret_20"] = p["date"].map(mkt_index.pct_change(20))

    # ----- 정답(타깃): 다음날 시가에 사서 HORIZON일 뒤 시가에 판 수익률 -----
    next_open = g["open"].shift(-1)
    exit_open = g["open"].shift(-1 - HORIZON)
    p["fwd_ret"] = exit_open / next_open - 1
    # 데이터 오류 제거: 미래 구간에 하루 ±35% 넘는 움직임(가격제한폭 초과)이 있으면 제외
    big_move = (daily_ret.abs() > 0.35).astype(float)
    future_big = big_move.groupby(p["code"]).transform(
        lambda s: s[::-1].rolling(HORIZON + 1, min_periods=1).max()[::-1].shift(-1))
    p.loc[future_big > 0, "fwd_ret"] = np.nan
    # 다음날 거래정지 등으로 살 수 없으면 제외
    p.loc[g["volume"].shift(-1) == 0, "fwd_ret"] = np.nan
    return p


def build_dataset(p):
    """모델 학습용 표를 만듭니다."""
    ok = (
        (p["avg_trading_value_20"] >= MIN_TRADING_VALUE)
        & (p["close"] >= 1000)          # 동전주 제외
        & (p["volume"] > 0)
        & p["fwd_ret"].notna()
        & p[FEATURES].notna().all(axis=1)
    )
    d = p.loc[ok, ["date", "code", "close"] + FEATURES + ["fwd_ret"]].copy()
    # 같은 날 모든 종목 중 수익률 순위 (0~1). 0.5보다 크면 '평균보다 잘함'
    d["fwd_rank"] = d.groupby("date")["fwd_ret"].rank(pct=True)
    d["target"] = (d["fwd_rank"] > 0.5).astype(int)
    return d


def train(d):
    train_set = d[d["date"] <= TRAIN_END]
    valid_set = d[(d["date"] > TRAIN_END) & (d["date"] <= VALID_END)]
    # 학습 기간 끝의 정답이 검증 기간 가격을 보지 않도록 마지막 HORIZON+1일은 뺌
    cut = np.sort(train_set["date"].unique())[-(HORIZON + 1)]
    train_set = train_set[train_set["date"] < cut]

    params = dict(
        objective="binary", learning_rate=0.03, num_leaves=31, min_child_samples=500,
        feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10,
        verbose=-1, seed=42,
    )
    model = lgb.train(
        params,
        lgb.Dataset(train_set[FEATURES], train_set["target"]),
        num_boost_round=2000,
        valid_sets=[lgb.Dataset(valid_set[FEATURES], valid_set["target"])],
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    print(f"   학습 데이터: {len(train_set):,}줄, 최적 반복 횟수: {model.best_iteration}")
    return model


def backtest(test):
    """매주(5거래일마다) 점수 상위 TOP_N 종목을 똑같은 금액으로 사서 1주일 보유."""
    dates = np.sort(test["date"].unique())[::HORIZON]
    rows = []
    prev_holdings = set()
    for dt in dates:
        day = test[test["date"] == dt]
        top = day.nlargest(TOP_N, "score")
        holdings = set(top["code"])
        turnover = 1 - len(holdings & prev_holdings) / TOP_N  # 새로 바꾼 종목 비율
        rows.append({
            "date": dt,
            "model": top["fwd_ret"].mean() - COST * turnover,
            "market": day["fwd_ret"].mean(),   # 비교 기준: 전 종목 똑같이 산 경우
            "bottom": day.nsmallest(TOP_N, "score")["fwd_ret"].mean(),
            "turnover": turnover,
        })
        prev_holdings = holdings
    return pd.DataFrame(rows).set_index("date")


def summarize(r, col):
    periods_per_year = 250 / HORIZON
    total = (1 + r[col]).prod() - 1
    years = len(r) / periods_per_year
    cagr = (1 + total) ** (1 / years) - 1
    sharpe = r[col].mean() / r[col].std() * np.sqrt(periods_per_year)
    curve = (1 + r[col]).cumprod()
    mdd = (curve / curve.cummax() - 1).min()
    return {"누적수익률": f"{total:.1%}", "연평균수익률": f"{cagr:.1%}",
            "샤프지수": f"{sharpe:.2f}", "최대낙폭": f"{mdd:.1%}",
            "주간승률": f"{(r[col] > 0).mean():.1%}"}


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터 불러오고 지표 계산 중...")
    p = make_features(pd.read_parquet(os.path.join(DATA_DIR, "prices.parquet")))
    d = build_dataset(p)
    print(f"   학습 가능한 데이터: {len(d):,}줄 (하루 평균 {d.groupby('date').size().mean():.0f}종목)")

    print("2) 모델 학습 중 (LightGBM)...")
    model = train(d)

    print("3) 시험 기간(2024~) 평가 중...")
    test = d[d["date"] > VALID_END].copy()
    test["score"] = model.predict(test[FEATURES], num_iteration=model.best_iteration)

    auc = roc_auc_score(test["target"], test["score"])
    daily_ic = test.groupby("date").apply(
        lambda x: x["score"].corr(x["fwd_ret"], method="spearman"), include_groups=False)
    print(f"   AUC: {auc:.4f}  (0.5 = 동전 던지기, 높을수록 좋음)")
    print(f"   IC 평균: {daily_ic.mean():.4f}, IC>0 비율: {(daily_ic > 0).mean():.1%}")

    # 점수 구간(10분위)별 실제 평균 수익률
    test["decile"] = test.groupby("date")["score"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) + 1)
    decile_ret = test.groupby("decile")["fwd_ret"].mean()

    r = backtest(test)
    summary = pd.DataFrame({
        f"모델 상위 {TOP_N}종목 (비용 차감)": summarize(r, "model"),
        "전 종목 동일비중 (시장)": summarize(r, "market"),
        f"모델 하위 {TOP_N}종목 (비용 미차감)": summarize(r, "bottom"),
    })
    print("\n" + summary.to_string())
    print(f"\n   평균 교체율: {r['turnover'].mean():.0%} / 주")

    # ----- 결과 저장 -----
    importance = pd.Series(model.feature_importance("gain"), index=FEATURES).sort_values()
    summary.to_csv(os.path.join(RESULT_DIR, "summary.csv"), encoding="utf-8-sig")
    decile_ret.to_csv(os.path.join(RESULT_DIR, "decile_returns.csv"), encoding="utf-8-sig")
    r.to_csv(os.path.join(RESULT_DIR, "weekly_returns.csv"), encoding="utf-8-sig")
    with open(os.path.join(RESULT_DIR, "metrics.txt"), "w") as f:
        f.write(f"AUC {auc:.4f}\nIC_mean {daily_ic.mean():.4f}\nIC_positive {(daily_ic > 0).mean():.3f}\n")

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for col, label in [("model", f"Model top {TOP_N} (after cost)"),
                       ("market", "Market (equal weight)"),
                       ("bottom", f"Model bottom {TOP_N}")]:
        axes[0].plot((1 + r[col]).cumprod(), label=label)
    axes[0].set_title("Test period cumulative return (2024~)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].bar(decile_ret.index, decile_ret.values * 100)
    axes[1].set_title("Avg 5-day return by score decile (%)")
    axes[1].set_xlabel("Decile (1 = lowest score, 10 = highest)")
    axes[2].barh(importance.index, importance.values)
    axes[2].set_title("Feature importance")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "results.png"), dpi=110)

    # ----- 가장 최근 날짜 기준 모델 상위 종목 -----
    names = pd.read_csv(os.path.join(DATA_DIR, "stock_list.csv"), dtype={"code": str})
    latest = p[p["date"] == p["date"].max()]
    latest = latest[(latest["avg_trading_value_20"] >= MIN_TRADING_VALUE)
                    & (latest["close"] >= 1000) & latest[FEATURES].notna().all(axis=1)].copy()
    latest["score"] = model.predict(latest[FEATURES], num_iteration=model.best_iteration)
    picks = latest.nlargest(TOP_N, "score").merge(names, on="code")[
        ["code", "name", "market", "close", "score"]]
    picks.to_csv(os.path.join(RESULT_DIR, "latest_picks.csv"), index=False, encoding="utf-8-sig")
    print(f"\n4) {p['date'].max().date()} 기준 모델 상위 종목 (참고용):")
    print(picks.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
