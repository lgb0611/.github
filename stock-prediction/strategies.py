"""
기술적 매수 전략 비교: 어떤 매수 신호가 '20일 안에 +15%'를 가장 자주 달성하나?

규칙
- 매수: 신호가 뜬 날(t) 종가를 보고, 다음날(t+1) 시가에 매수
- 성공: 매수 후 20거래일 안에 고가가 매수가보다 15% 이상 오르면 성공
- 매도: 종가가 25일선 아래로 내려가면 50%, 60일선 아래로 내려가면 나머지 50%를
        각각 다음날 시가에 매도
- 같은 종목에서 같은 신호가 최근 20일 안에 이미 떴으면 중복으로 보고 제외
- 전략 고르기는 2016~2022(발견 기간)로 하고, 2023~2026(확인 기간)으로 다시 검증

실행: python strategies.py   (collect_data.py를 먼저 실행해야 함)
결과: results/strategies_all.csv, results/strategies_top5.csv, results/strategies_top5.png
"""
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "data")
RESULT_DIR = os.path.join(BASE, "results")

TARGET = 0.15            # 성공 기준: +15%
WINDOW = 20              # 성공 판정 기간: 20거래일
COOLDOWN = 20            # 같은 신호 중복 제외 기간
COST = 0.0025            # 왕복 거래비용 (수수료 + 거래세 + 슬리피지)
MIN_TRADING_VALUE = 1e9  # 20일 평균 거래대금 10억 원 이상
MIN_PRICE = 1000
SPLIT_DATE = "2023-01-01"  # 이전 = 발견 기간, 이후 = 확인 기간
MIN_TRADES = 300           # 발견 기간 신호가 이보다 적으면 순위에서 제외


# ---------------------------------------------------------------------------
# 종목별 계산 도우미 (데이터가 종목·날짜순으로 정렬되어 있다고 가정)
# 전체를 한 번에 계산한 뒤, 다른 종목 데이터가 섞인 앞/뒤 구간만 지워서 빠르게 처리
# ---------------------------------------------------------------------------
class Panel:
    def __init__(self, df):
        self.df = df
        self.pos = df.groupby("code").cumcount().to_numpy()                   # 종목 내 몇 번째 날
        self.left = df.groupby("code")["code"].transform("size").to_numpy() - self.pos - 1  # 남은 날 수

    def shift(self, s, k):
        out = s.shift(k)
        bad = self.pos < k if k > 0 else self.left < -k
        out[bad] = np.nan
        return out

    def roll(self, s, n, how="mean"):
        out = getattr(s.rolling(n), how)()
        out[self.pos < n - 1] = np.nan
        return out


def load():
    p = pd.read_parquet(os.path.join(DATA_DIR, "prices.parquet"))
    p = p.sort_values(["code", "date"]).reset_index(drop=True)
    # 거래정지일은 시가·고가·저가가 0 → 종가로 채움
    # (조건을 먼저 저장해 둬야 함: 시가를 먼저 채우면 고가·저가가 0으로 남는 버그가 있었음)
    halt = p["open"] == 0
    for c in ["open", "high", "low"]:
        p[c] = p[c].where(~halt, p["close"]).astype(float)
    # 일부 종목은 저가만 0으로 들어온 날이 있음 → 시가·종가 중 낮은 값으로
    bad_low = p["low"] <= 0
    p.loc[bad_low, "low"] = p.loc[bad_low, ["open", "close"]].min(axis=1)
    # 수정주가 반올림 등으로 종가가 고가보다 높은 날이 있음 → 고가는 그날 최고, 저가는 그날 최저로 정리
    ohlc = p[["open", "high", "low", "close"]]
    p["high"], p["low"] = ohlc.max(axis=1), ohlc.min(axis=1)
    p["close"] = p["close"].astype(float)
    p["volume"] = p["volume"].astype(float)
    return p


def add_indicators(p, P):
    c, h, l, o, v = p["close"], p["high"], p["low"], p["open"], p["volume"]
    p["prev_close"] = P.shift(c, 1)
    p["ret1"] = c / p["prev_close"] - 1
    for n in [5, 10, 20, 25, 60, 120]:
        p[f"ma{n}"] = P.roll(c, n)
    p["ma20_prev"] = P.shift(p["ma20"], 1)
    p["ma5_prev"] = P.shift(p["ma5"], 1)
    p["ma60_prev"] = P.shift(p["ma60"], 1)
    p["ma20_5ago"] = P.shift(p["ma20"], 5)
    p["ma60_5ago"] = P.shift(p["ma60"], 5)
    p["vma20"] = P.shift(P.roll(v, 20), 1)                 # 어제까지 20일 평균 거래량
    p["tv20"] = P.roll(c * v, 20)                          # 20일 평균 거래대금
    # 어제까지의 n일 최고가 (오늘 이걸 넘으면 '돌파')
    for n in [20, 60, 120, 250]:
        p[f"hh{n}"] = P.shift(P.roll(h, n, "max"), 1)
    p["ll20"] = P.shift(P.roll(l, 20, "min"), 1)
    p["hh_all"] = p.groupby("code")["high"].cummax().groupby(p["code"]).shift(1)
    # 볼린저밴드 (20일, 2표준편차)
    std20 = P.roll(c, 20, "std")
    p["bb_up"] = p["ma20"] + 2 * std20
    p["bb_dn"] = p["ma20"] - 2 * std20
    p["bb_width"] = (p["bb_up"] - p["bb_dn"]) / p["ma20"]
    p["bb_width_min120"] = P.shift(P.roll(p["bb_width"], 120, "min"), 1)
    # RSI 14
    up = p["ret1"].clip(lower=0)
    dn = -p["ret1"].clip(upper=0)
    p["rsi"] = P.roll(up, 14) / (P.roll(up, 14) + P.roll(dn, 14) + 1e-12) * 100
    p["rsi_prev"] = P.shift(p["rsi"], 1)
    # MACD (12, 26, 9)
    ema = lambda s, n: s.groupby(p["code"]).transform(lambda x: x.ewm(span=n, adjust=False).mean())
    macd = ema(c, 12) - ema(c, 26)
    sig = macd.groupby(p["code"]).transform(lambda x: x.ewm(span=9, adjust=False).mean())
    p["macd"] = macd.where(P.pos >= 35)
    p["macd_sig"] = sig.where(P.pos >= 35)
    p["macd_prev"] = P.shift(p["macd"], 1)
    p["macd_sig_prev"] = P.shift(p["macd_sig"], 1)
    # 스토캐스틱 (14, 3)
    ll14, hh14 = P.roll(l, 14, "min"), P.roll(h, 14, "max")
    p["stoch_k"] = P.roll((c - ll14) / (hh14 - ll14 + 1e-12) * 100, 3)
    p["stoch_d"] = P.roll(p["stoch_k"], 3)
    p["stoch_k_prev"] = P.shift(p["stoch_k"], 1)
    p["stoch_d_prev"] = P.shift(p["stoch_d"], 1)
    # 최근 20일 동안 상한가(+29% 이상)가 있었나
    p["limit_up"] = (p["ret1"] >= 0.29).astype(float)
    p["up_days3"] = P.roll((p["ret1"] > 0).astype(float), 3, "sum")
    p["box60"] = P.shift(P.roll(h, 60, "max") / P.roll(l, 60, "min") - 1, 1)   # 60일 박스 폭
    p["ma_spread"] = (p[["ma5", "ma20", "ma60"]].max(axis=1)
                      / p[["ma5", "ma20", "ma60"]].min(axis=1) - 1)
    p["ma_spread_prev"] = P.shift(p["ma_spread"], 1)
    return p


def define_strategies(p):
    """각 전략의 '매수 신호' 조건. 모두 신호 당일 종가까지의 정보만 사용."""
    c, o, h, l, v = p["close"], p["open"], p["high"], p["low"], p["volume"]
    vol_x = v / p["vma20"]
    bull = c > p["ma20"]
    trend_up = (p["ma20"] > p["ma60"]) & (p["ma20"] > p["ma20_5ago"]) & (p["ma60"] > p["ma60_5ago"])
    return {
        # ---- 신고가 돌파 ----
        "52주 신고가 돌파": c > p["hh250"],
        "52주 신고가 돌파 + 거래량 2배": (c > p["hh250"]) & (vol_x >= 2),
        "52주 신고가 돌파 + 거래량 3배 + 양봉 5%↑": (c > p["hh250"]) & (vol_x >= 3) & (p["ret1"] >= 0.05),
        "역사적 신고가 돌파 (10년 내)": (c > p["hh_all"]) & (P.pos >= 500),
        "120일 신고가 돌파 + 거래량 2배": (c > p["hh120"]) & (vol_x >= 2),
        "60일 신고가 돌파 + 거래량 2배": (c > p["hh60"]) & (vol_x >= 2),
        "20일 신고가 돌파 + 거래량 2배": (c > p["hh20"]) & (vol_x >= 2),
        "박스권(60일 폭 30% 이내) 상단 돌파": (c > p["hh60"]) & (p["box60"] <= 0.30) & (vol_x >= 1.5),
        # ---- 눌림목 ----
        "20일선 눌림목 (정배열 중 20일선 터치 후 양봉)":
            trend_up & (l <= p["ma20"] * 1.01) & (c > p["ma20"]) & (c > o),
        "20일선 눌림목 + 거래량 감소":
            trend_up & (l <= p["ma20"] * 1.01) & (c > p["ma20"]) & (c > o) & (vol_x < 0.8),
        "60일선 눌림목 (상승추세 중 60일선 터치 후 양봉)":
            (p["ma60"] > p["ma60_5ago"]) & (p["ma60"] > p["ma120"]) & (l <= p["ma60"] * 1.01)
            & (c > p["ma60"]) & (c > o),
        "5일선 눌림목 (강한 추세 중)":
            trend_up & (p["ma5"] > p["ma20"]) & (l <= p["ma5"]) & (c > p["ma5"]) & (c > o)
            & (c / p["ma60"] - 1 > 0.15),
        # ---- 이동평균 교차 ----
        "골든크로스 5/20": (p["ma5"] > p["ma20"]) & (p["ma5_prev"] <= p["ma20_prev"]),
        "골든크로스 20/60": (p["ma20"] > p["ma60"]) & (p["ma20_prev"] <= p["ma60_prev"]),
        "정배열 전환 (5>20>60>120)":
            (p["ma5"] > p["ma20"]) & (p["ma20"] > p["ma60"]) & (p["ma60"] > p["ma120"])
            & ~((p["ma5_prev"] > p["ma20_prev"]) & (p["ma20_prev"] > p["ma60_prev"])),
        "이평선 밀집(3% 이내) 후 5%↑ 양봉 돌파":
            (p["ma_spread_prev"] <= 0.03) & (p["ret1"] >= 0.05) & (c > p[["ma5", "ma20", "ma60"]].max(axis=1)),
        # ---- 거래량 / 장대양봉 ----
        "거래량 3배 + 5%↑ 양봉": (vol_x >= 3) & (p["ret1"] >= 0.05) & (c > o),
        "거래량 5배 + 10%↑ 장대양봉": (vol_x >= 5) & (p["ret1"] >= 0.10) & (c > o),
        "상한가 (+29% 이상)": p["ret1"] >= 0.29,
        "15~29% 급등 (상한가 제외)": (p["ret1"] >= 0.15) & (p["ret1"] < 0.29),
        "갭상승 3%↑ 후 양봉 유지": (o >= p["prev_close"] * 1.03) & (c > o) & (vol_x >= 2),
        "3일 연속 상승 + 60일선 위": (p["up_days3"] == 3) & (c > p["ma60"]) & (vol_x >= 1.5),
        # ---- 볼린저밴드 ----
        "볼린저밴드 상단 돌파": (c > p["bb_up"]) & (vol_x >= 1.5),
        "볼린저 스퀴즈(120일 최소 폭) 후 상단 돌파":
            (p["bb_width"].shift(1) <= p["bb_width_min120"] * 1.1) & (c > p["bb_up"]),
        "볼린저밴드 하단 이탈 후 복귀": (p["prev_close"] < p["bb_dn"].shift(1)) & (c > p["bb_dn"]) & (c > o),
        # ---- 과매도 반등 ----
        "RSI 30 상향 돌파 (과매도 탈출)": (p["rsi_prev"] < 30) & (p["rsi"] >= 30),
        "이격도 과매도 (20일선 대비 -20%) 후 양봉": (c / p["ma20"] < 0.80) & (c > o),
        "20일 최저가 이탈 후 반등 양봉 (5%↑)": (p["prev_close"] < p["ll20"]) & (p["ret1"] >= 0.05),
        # ---- 지표 교차 ----
        "MACD 골든크로스 (0선 위)":
            (p["macd"] > p["macd_sig"]) & (p["macd_prev"] <= p["macd_sig_prev"]) & (p["macd"] > 0),
        "MACD 골든크로스 (0선 아래)":
            (p["macd"] > p["macd_sig"]) & (p["macd_prev"] <= p["macd_sig_prev"]) & (p["macd"] < 0),
        "스토캐스틱 20 이하 골든크로스":
            (p["stoch_k"] > p["stoch_d"]) & (p["stoch_k_prev"] <= p["stoch_d_prev"]) & (p["stoch_k"] < 20),
        # ---- 비교 기준 ----
        "(기준) 아무 날이나 매수": pd.Series(True, index=p.index),
    }


def compute_outcomes(p, P):
    """모든 날짜에 대해 '다음날 시가에 샀다면' 결과를 미리 계산."""
    idx = np.arange(len(p))
    code_end = idx + P.left                     # 각 행이 속한 종목의 마지막 행 번호

    entry_i = idx + 1
    valid_entry = P.left >= 1
    entry_px = p["open"].shift(-1).to_numpy()
    entry_vol = p["volume"].shift(-1).to_numpy()

    # 성공 여부: 매수일(t+1) ~ t+20 사이 최고가 / 매수가
    fwd_max = p["high"][::-1].rolling(WINDOW).max()[::-1].shift(-1).to_numpy()
    fwd_max[P.left < WINDOW] = np.nan
    max_gain = fwd_max / entry_px - 1
    # 데이터 오류 제거: 미래 20일 안에 하루 ±35% 넘는 변동이 있으면 제외
    bad = (p["ret1"].abs() > 0.35).astype(float)
    bad_fwd = bad[::-1].rolling(WINDOW + 1, min_periods=1).max()[::-1].shift(-1).to_numpy()

    # 매도: 매수일 종가부터 확인해서 처음으로 이평선 아래로 마감한 날 → 그 다음날 시가에 매도
    close, open_ = p["close"].to_numpy(), p["open"].to_numpy()
    last_close = close[code_end]

    def exit_leg(ma_col):
        below = (p["close"] < p[ma_col]).to_numpy()
        nxt = pd.Series(np.where(below, idx, np.nan)).bfill().to_numpy()  # i 이후 첫 이탈 행
        j = np.full(len(p), np.nan)
        j[valid_entry] = nxt[entry_i[valid_entry]]
        ok = ~np.isnan(j) & (j <= code_end)           # 같은 종목 안에서 이탈이 있었나
        j_int = np.where(ok, j, 0).astype(int)
        sell_i = np.minimum(j_int + 1, code_end)      # 이탈 다음날 (마지막 날이면 그날 종가)
        sell_px = np.where(j_int + 1 <= code_end, open_[sell_i], close[j_int])
        ret = np.where(ok, sell_px / entry_px - 1, last_close / entry_px - 1)  # 아직 보유 중이면 마지막 종가
        days = np.where(ok, sell_i - idx, code_end - idx)
        return ret, days, ok

    r25, d25, ok25 = exit_leg("ma25")
    r60, d60, ok60 = exit_leg("ma60")
    trade_ret = 0.5 * r25 + 0.5 * r60 - COST

    return pd.DataFrame({
        "date": p["date"], "code": p["code"],
        "max_gain": max_gain, "success": (max_gain >= TARGET).astype(float),
        "trade_ret": trade_ret, "hold_days": 0.5 * d25 + 0.5 * d60,
        "closed": ok25 & ok60,
        "ok": valid_entry & (entry_vol > 0) & (entry_px > 0) & (bad_fwd == 0) & ~np.isnan(max_gain),
    })


def take_profit_returns(p, P, trades):
    """비교용 매도 규칙: +15% 도달하면 그 가격에 전량 익절, 먼저 이평선을 이탈하면 원래 규칙대로 매도.
    (갭상승으로 시가가 이미 +15% 위면 시가에 매도)"""
    high, open_, close = p["high"].to_numpy(), p["open"].to_numpy(), p["close"].to_numpy()
    below25 = (p["close"] < p["ma25"]).to_numpy()
    below60 = (p["close"] < p["ma60"]).to_numpy()
    end_of = np.arange(len(p)) + P.left
    rets = []
    for i in trades.index:
        e, end = i + 1, end_of[i]
        entry = open_[e]
        target = entry * (1 + TARGET)
        legs, sold, k = [], 0, e          # legs: 매도된 비중별 수익률
        remaining = {"25": 0.5, "60": 0.5}
        while k <= end and remaining:
            if high[k] >= target:        # 익절 (지정가 주문 체결 가정)
                px = max(open_[k], target) if k > e else target
                legs += [(w, px / entry - 1) for w in remaining.values()]
                remaining = {}
                break
            for key, flag in [("25", below25), ("60", below60)]:
                if key in remaining and flag[k]:
                    px = open_[k + 1] if k + 1 <= end else close[k]
                    legs.append((remaining.pop(key), px / entry - 1))
            k += 1
        legs += [(w, close[end] / entry - 1) for w in remaining.values()]  # 아직 보유 중
        rets.append(sum(w * r for w, r in legs) - COST)
    return pd.Series(rets, index=trades.index)


def summarize(trades):
    if len(trades) == 0:
        return {}
    return {
        "신호수": len(trades),
        "승률(20일내 +15%)": trades["success"].mean(),
        "평균수익률(매도규칙)": trades["trade_ret"].mean(),
        "수익률 중간값": trades["trade_ret"].median(),
        "수익 난 비율": (trades["trade_ret"] > 0).mean(),
        "평균 보유일": trades["hold_days"].mean(),
    }


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터 불러오고 지표 계산 중...")
    global P
    p = load()
    P = Panel(p)
    p = add_indicators(p, P)
    out = compute_outcomes(p, P)
    universe = (
        (p["tv20"] >= MIN_TRADING_VALUE) & (p["close"] >= MIN_PRICE) & (p["volume"] > 0) & out["ok"]
    )

    print("2) 전략별 신호 찾고 결과 계산 중...")
    rows, all_trades = [], {}
    for name, cond in define_strategies(p).items():
        sig = cond.fillna(False).astype(bool)
        if not name.startswith("(기준)"):
            # 최근 20일 안에 같은 신호가 있었으면 중복으로 제외
            recent = P.shift(P.roll(sig.astype(float), COOLDOWN, "sum"), 1).fillna(0)
            sig = sig & (recent == 0)
        t = out[sig & universe]
        all_trades[name] = t
        early, late = t[t["date"] < SPLIT_DATE], t[t["date"] >= SPLIT_DATE]
        row = {"전략": name}
        for label, part in [("발견", early), ("확인", late), ("전체", t)]:
            for k, val in summarize(part).items():
                row[f"{label}_{k}"] = val
        rows.append(row)

    res = pd.DataFrame(rows).set_index("전략")
    base = res.loc["(기준) 아무 날이나 매수"]
    ranked = (res.drop(index="(기준) 아무 날이나 매수")
                 .query("`발견_신호수` >= @MIN_TRADES")
                 .sort_values("발견_승률(20일내 +15%)", ascending=False))
    res_sorted = pd.concat([ranked, res.loc[["(기준) 아무 날이나 매수"]]])
    res_sorted.to_csv(os.path.join(RESULT_DIR, "strategies_all.csv"), encoding="utf-8-sig")

    cols = ["발견_신호수", "발견_승률(20일내 +15%)", "확인_신호수", "확인_승률(20일내 +15%)",
            "전체_평균수익률(매도규칙)", "전체_수익 난 비율", "전체_평균 보유일"]
    fmt = res_sorted[cols].copy()
    for col in cols:
        if "승률" in col or "수익" in col:
            fmt[col] = (fmt[col] * 100).map("{:.1f}%".format)
        elif "보유일" in col:
            fmt[col] = fmt[col].map("{:.0f}일".format)
        else:
            fmt[col] = fmt[col].map("{:,.0f}".format)
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    print("\n전략 순위 (발견 기간 승률 기준)\n" + fmt.to_string())

    top5 = ranked.head(5).copy()

    print("\n3) 상위 5개 전략: 매도 규칙별 평균 수익률 비교 (거래비용 차감)")
    compare = []
    for name in list(top5.index) + ["(기준) 아무 날이나 매수"]:
        t = all_trades[name]
        if name.startswith("(기준)"):
            t = t.sample(50000, random_state=0)
        tp = take_profit_returns(p, P, t)
        late = t["date"] >= SPLIT_DATE
        compare.append({
            "전략": name,
            "이평선 규칙_평균": t["trade_ret"].mean(), "이평선 규칙_수익 난 비율": (t["trade_ret"] > 0).mean(),
            "+15% 익절 추가_평균": tp.mean(), "+15% 익절 추가_수익 난 비율": (tp > 0).mean(),
            "+15% 익절 추가_확인기간 평균": tp[late].mean(),
        })
        if name in top5.index:
            top5.loc[name, "익절추가_평균수익률"] = tp.mean()
    compare = pd.DataFrame(compare).set_index("전략")
    print(compare.map("{:.1%}".format).to_string())
    compare.to_csv(os.path.join(RESULT_DIR, "strategies_exit_compare.csv"), encoding="utf-8-sig")
    top5.to_csv(os.path.join(RESULT_DIR, "strategies_top5.csv"), encoding="utf-8-sig")

    # 상위 5개 전략의 연도별 승률 차트
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, name in enumerate(list(top5.index) + ["(기준) 아무 날이나 매수"]):
        t = all_trades[name]
        yearly = t.groupby(t["date"].dt.year)["success"].mean() * 100
        ax.plot(yearly.index, yearly.values, marker="o",
                label=f"#{i + 1}" if i < 5 else "Baseline (any day)",
                linestyle="--" if i == 5 else "-", color="gray" if i == 5 else None)
    ax.axvline(2022.5, color="k", alpha=0.3)
    ax.text(2022.6, ax.get_ylim()[1] * 0.95, "out-of-sample →")
    ax.set_title("Win rate by year (+15% within 20 days) — top 5 strategies")
    ax.set_ylabel("Win rate (%)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "strategies_top5.png"), dpi=110)
    print("\n차트 범례: " + ", ".join(f"#{i + 1}={n}" for i, n in enumerate(top5.index)))
    print(f"\n기준(아무 날이나): 승률 {base['전체_승률(20일내 +15%)']:.1%}, "
          f"평균수익률 {base['전체_평균수익률(매도규칙)']:.2%}")


if __name__ == "__main__":
    main()
