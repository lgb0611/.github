"""
매수 신호 × 매도 규칙 조합 중 '최고의 전략 5개' 찾기

고정 조건
- 매수: 신호가 뜬 날 종가를 보고 다음날 시가에 매수
- 성공(승률): 매수 후 20거래일 안에 고가가 매수가 대비 +15% 이상

선정 방법
- 매수 신호 62개 (기존 31개 × '시장 상승장일 때만' 필터 유무)
- 매도 규칙 20개 (익절, 손절, 추적 손절, 이평선 이탈, 기간 청산 조합)
- 2016~2022(발견 기간)에서
    1) 승률 40% 이상(기준 29%)이고 신호가 300번 이상인 조합 중
    2) 거래당 평균 수익률(비용 차감)이 가장 높은 조합을 고르고
    3) 서로 다른 매수 신호 5개만 남김
- 2023~2026(확인 기간)으로 다시 검증, 계좌 시뮬레이션으로 실제 운용 성과 확인

실행: python best_strategies.py   (collect_data.py를 먼저 실행해야 함)
"""
import os

import matplotlib
import numpy as np
import pandas as pd

import strategies as S

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULT_DIR = S.RESULT_DIR
H = 60                  # 최대 보유 기간 (60거래일 지나면 무조건 청산)
COST = S.COST
SPLIT_DATE = S.SPLIT_DATE
MIN_WIN_RATE = 0.40
MIN_TRADES = 300
SLOTS = 10              # 계좌 시뮬레이션: 최대 동시 보유 종목 수 (종목당 자산의 1/10)

# ---------------------------------------------------------------------------
# 매도 규칙: 각 규칙은 [(비중, 조건), ...] — 비중별로 따로 팔 수 있음 (예: 50%는 익절, 50%는 추적)
#   tp: 익절 (+x% 도달 시 지정가 매도)      sl: 손절 (-x% 도달 시 매도)
#   trail: 추적 손절 (매수 후 최고 종가 대비 -x%로 마감하면 다음날 시가 매도)
#   ma: 종가가 이 이동평균선 아래로 마감하면 다음날 시가 매도
#   time: n거래일째 종가에 매도
# ---------------------------------------------------------------------------
EXITS = {
    "원래 규칙 (25일선 50% / 60일선 50%)": [(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))],
    "원래 규칙 + 손절 -7%": [(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))],
    "익절 +15% / 손절 -7% / 20일 청산": [(1, dict(tp=0.15, sl=-0.07, time=20))],
    "익절 +15% / 손절 -5% / 20일 청산": [(1, dict(tp=0.15, sl=-0.05, time=20))],
    "익절 +15% / 손절 -10% / 20일 청산": [(1, dict(tp=0.15, sl=-0.10, time=20))],
    "익절 +15% / 손절 -7% / 10일 청산": [(1, dict(tp=0.15, sl=-0.07, time=10))],
    "익절 +15% / 20일 청산 (손절 없음)": [(1, dict(tp=0.15, time=20))],
    "익절 +10% / 손절 -5% / 20일 청산": [(1, dict(tp=0.10, sl=-0.05, time=20))],
    "익절 +20% / 손절 -7% / 20일 청산": [(1, dict(tp=0.20, sl=-0.07, time=20))],
    "익절 +15% / 손절 -7% / 20일선 이탈": [(1, dict(tp=0.15, sl=-0.07, ma="ma20"))],
    "익절 +15% / 손절 -7% / 25일선 이탈": [(1, dict(tp=0.15, sl=-0.07, ma="ma25"))],
    "50% +15% 익절, 50% 추적손절 10% / 손절 -7%":
        [(0.5, dict(tp=0.15, sl=-0.07)), (0.5, dict(trail=0.10, sl=-0.07))],
    "50% +15% 익절, 50% 20일선 이탈 / 손절 -7%":
        [(0.5, dict(tp=0.15, sl=-0.07)), (0.5, dict(ma="ma20", sl=-0.07))],
    "50% +15% 익절, 50% +30% 익절 / 손절 -7% / 40일 청산":
        [(0.5, dict(tp=0.15, sl=-0.07, time=40)), (0.5, dict(tp=0.30, sl=-0.07, time=40))],
    "50% +15% 익절, 50% 25일선 이탈 / 손절 -7%":
        [(0.5, dict(tp=0.15, sl=-0.07)), (0.5, dict(ma="ma25", sl=-0.07))],
    "추적손절 10% / 손절 -7%": [(1, dict(trail=0.10, sl=-0.07))],
    "추적손절 15% / 손절 -10%": [(1, dict(trail=0.15, sl=-0.10))],
    "5일선 이탈 / 손절 -7%": [(1, dict(ma="ma5", sl=-0.07))],
    "10일선 이탈 / 손절 -7%": [(1, dict(ma="ma10", sl=-0.07))],
    "20일선 이탈 / 손절 -7%": [(1, dict(ma="ma20", sl=-0.07))],
}
MA_COLS = ["ma5", "ma10", "ma20", "ma25", "ma60"]


def path_matrix(p, P, rows):
    """각 거래의 매수일부터 H일 동안의 시가/고가/저가/종가/이평선을 (거래 수 × H) 표로 만듦."""
    end = rows + P.left[rows]                       # 그 종목의 마지막 행
    e = rows + 1                                    # 매수일 = 신호 다음날
    k = e[:, None] + np.arange(H)[None, :]
    valid = k <= end[:, None]
    k = np.minimum(k, end[:, None])
    m = {c: p[c].to_numpy()[k] for c in ["open", "high", "low", "close"] + MA_COLS}
    m["valid"] = valid
    m["date_idx"] = p["date_idx"].to_numpy()[k]
    return m


def first_true(mask):
    """행마다 처음 True가 나오는 열 번호 (없으면 -1)"""
    has = mask.any(axis=1)
    return np.where(has, mask.argmax(axis=1), -1)


def run_leg(m, rule):
    """한 비중(leg)의 매도 시점·가격을 계산. 같은 날이면 손절 → 익절 순서로 보수적으로 가정."""
    O, Hi, L, C, V = m["open"], m["high"], m["low"], m["close"], m["valid"]
    n = O.shape[0]
    E = O[:, 0]
    rows = np.arange(n)
    best_t = np.full(n, np.inf)
    best_px = np.full(n, np.nan)
    best_day = np.zeros(n, dtype=int)

    def consider(t, px, day):
        better = (t >= 0) & (t < best_t)
        best_t[better] = t[better]
        best_px[better] = px[better]
        best_day[better] = day[better]

    if "sl" in rule:
        stop = E * (1 + rule["sl"])
        k = first_true((L <= stop[:, None]) & V)
        kk = np.maximum(k, 0)
        px = np.minimum(O[rows, kk], stop)          # 시가가 이미 손절가 아래면 시가에 체결
        consider(np.where(k >= 0, k + 0.1, -1), px, kk)
    if "tp" in rule:
        target = E * (1 + rule["tp"])
        k = first_true((Hi >= target[:, None]) & V)
        kk = np.maximum(k, 0)
        px = np.maximum(O[rows, kk], target)        # 시가가 이미 목표가 위면 시가에 체결
        consider(np.where(k >= 0, k + 0.2, -1), px, kk)

    close_signal = np.zeros_like(V)
    if "trail" in rule:
        peak = np.maximum.accumulate(C, axis=1)
        close_signal |= C < peak * (1 - rule["trail"])
    if "ma" in rule:
        close_signal |= C < m[rule["ma"]]
    if close_signal.any():
        k = first_true(close_signal & V)
        kk = np.maximum(k, 0)
        nxt = np.minimum(kk + 1, H - 1)
        has_next = (kk + 1 < H) & V[rows, nxt]
        px = np.where(has_next, O[rows, nxt], C[rows, kk])  # 다음날 시가 (없으면 당일 종가)
        consider(np.where(k >= 0, k + 0.5, -1), px, np.where(has_next, nxt, kk))
    if "time" in rule:
        k = np.full(n, rule["time"] - 1)
        ok = V[rows, k]
        consider(np.where(ok, k + 0.4, -1), C[rows, k], k)

    # 위 조건이 하나도 안 걸리면 최대 보유기간 끝(또는 데이터 끝) 종가에 청산
    last = V.sum(axis=1) - 1
    consider(last + 0.45, C[rows, last], last)
    return best_px / E - 1, best_day


def run_exit(m, legs):
    """매도 규칙 하나를 적용한 거래별 수익률, 보유일, 일별 평가가치(계좌 시뮬레이션용)."""
    E = m["open"][:, 0]
    ret = np.zeros(len(E))
    hold = np.zeros(len(E))
    value = np.zeros_like(m["close"])
    day_axis = np.arange(H)[None, :]
    for w, rule in legs:
        r, d = run_leg(m, rule)
        ret += w * r
        hold = np.maximum(hold, d + 1)
        leg_val = np.where(day_axis < d[:, None], m["close"] / E[:, None], (1 + r)[:, None])
        value += w * leg_val
    return ret - COST, hold, value


def load_all():
    p = S.load()
    P = S.Panel(p)
    S.P = P
    p = S.add_indicators(p, P)
    out = S.compute_outcomes(p, P)
    dates = np.sort(p["date"].unique())
    p["date_idx"] = np.searchsorted(dates, p["date"].to_numpy())

    # 시장 상승장 필터: 종목이 속한 시장 지수(코스피/코스닥)가 60일선 위
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet"))
    idx["ma60"] = idx.groupby("index")["close"].transform(lambda s: s.rolling(60).mean())
    idx["bull"] = idx["close"] > idx["ma60"]
    market = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    p = p.merge(market[["code", "market"]], on="code", how="left")
    p = p.merge(idx[["index", "date", "bull"]].rename(columns={"index": "market"}),
                on=["market", "date"], how="left")
    p["bull"] = p["bull"].fillna(False).astype(bool)

    universe = ((p["tv20"] >= S.MIN_TRADING_VALUE) & (p["close"] >= S.MIN_PRICE)
                & (p["volume"] > 0) & out["ok"]).to_numpy()
    return p, P, out, universe, dates


def entry_signals(p, P):
    base = S.define_strategies(p)
    base.pop("(기준) 아무 날이나 매수")
    signals = {}
    for name, cond in base.items():
        sig = cond.fillna(False).astype(bool)
        recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        sig = sig & (recent == 0)
        signals[name] = sig.to_numpy()
        signals[name + " [상승장만]"] = (sig & p["bull"]).to_numpy()
    return signals


def stats(df):
    if len(df) == 0:
        return dict(n=0, win=np.nan, avg=np.nan, med=np.nan, prof=np.nan, hold=np.nan, pf=np.nan)
    gain, loss = df["ret"][df["ret"] > 0].sum(), -df["ret"][df["ret"] < 0].sum()
    return dict(n=len(df), win=df["success"].mean(), avg=df["ret"].mean(), med=df["ret"].median(),
                prof=(df["ret"] > 0).mean(), hold=df["hold"].mean(), pf=gain / loss if loss > 0 else np.nan)


def portfolio(trades, dates, value_paths, start=None):
    """최대 SLOTS종목, 종목당 자산의 1/SLOTS씩 투자하는 실제 계좌 흉내. 같은 날 신호가 많으면 거래대금 큰 순."""
    trades = trades.sort_values(["entry_idx", "tv20"], ascending=[True, False])
    if start is not None:
        trades = trades[trades["entry_idx"] >= start]
    by_day = {d: g for d, g in trades.groupby("entry_idx")}
    first = int(trades["entry_idx"].min()) if start is None else start
    cash, positions, curve = 1.0, [], []
    for d in range(first, len(dates)):
        # 오늘 평가: 보유 종목 가치 갱신, 청산된 종목은 현금화
        equity_pos, still = 0.0, []
        for pos in positions:
            k = d - pos["entry_idx"]
            path = pos["path"]
            v = path[min(k, len(path) - 1)]
            if k >= pos["hold"] - 1 or k >= len(path) - 1:
                cash += pos["amount"] * pos["final"]
            else:
                equity_pos += pos["amount"] * v
                still.append(pos)
        positions = still
        equity = cash + equity_pos
        # 신규 매수 (매수일 = entry_idx)
        if d in by_day:
            for _, t in by_day[d].iterrows():
                if len(positions) >= SLOTS:
                    break
                amount = min(equity / SLOTS, cash)
                if amount <= 0:
                    break
                cash -= amount
                path = value_paths[int(t["row_key"])]
                positions.append(dict(entry_idx=d, amount=amount, path=path,
                                      hold=int(t["hold"]), final=1 + t["ret"]))
                equity_pos += amount * path[0]
        curve.append(cash + sum(pp["amount"] * pp["path"][min(d - pp["entry_idx"], len(pp["path"]) - 1)]
                                for pp in positions))
    return pd.Series(curve, index=pd.to_datetime(dates[first:first + len(curve)]))


def curve_stats(c):
    years = (c.index[-1] - c.index[0]).days / 365.25
    daily = c.pct_change().dropna()
    return {"누적수익률": c.iloc[-1] / c.iloc[0] - 1, "연평균수익률": (c.iloc[-1] / c.iloc[0]) ** (1 / years) - 1,
            "최대낙폭": (c / c.cummax() - 1).min(), "샤프지수": daily.mean() / daily.std() * np.sqrt(250)}


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터·지표 준비 중...")
    p, P, out, universe, dates = load_all()
    signals = entry_signals(p, P)
    success = out["success"].to_numpy()
    date_arr = p["date"].to_numpy()
    early_mask = date_arr < np.datetime64(SPLIT_DATE)

    print(f"2) 매수 신호 {len(signals)}개 × 매도 규칙 {len(EXITS)}개 = {len(signals) * len(EXITS)}개 조합 계산 중...")
    rows = []
    for sname, sig in signals.items():
        r = np.where(sig & universe)[0]
        if len(r) == 0:
            continue
        m = path_matrix(p, P, r)
        for ename, legs in EXITS.items():
            ret, hold, _ = run_exit(m, legs)
            df = pd.DataFrame({"row": r, "ret": ret, "hold": hold, "success": success[r], "early": early_mask[r]})
            e, l = stats(df[df["early"]]), stats(df[~df["early"]])
            rows.append({"매수신호": sname, "매도규칙": ename,
                         **{f"발견_{k}": v for k, v in e.items()}, **{f"확인_{k}": v for k, v in l.items()}})
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULT_DIR, "best_all_combinations.csv"), index=False, encoding="utf-8-sig")

    # ---- 선정: 발견 기간만 보고 고름 ----
    cand = res[(res["발견_win"] >= MIN_WIN_RATE) & (res["발견_n"] >= MIN_TRADES)]
    cand = cand.sort_values("발견_avg", ascending=False)
    picked, used = [], set()
    for _, row in cand.iterrows():
        family = row["매수신호"].replace(" [상승장만]", "")
        if family in used:
            continue
        used.add(family)
        picked.append(row)
        if len(picked) == 5:
            break
    top = pd.DataFrame(picked).reset_index(drop=True)
    top.index = top.index + 1

    show = pd.DataFrame({
        "매수 신호": top["매수신호"], "매도 규칙": top["매도규칙"],
        "발견 승률": top["발견_win"].map("{:.1%}".format), "확인 승률": top["확인_win"].map("{:.1%}".format),
        "발견 평균수익": top["발견_avg"].map("{:+.2%}".format), "확인 평균수익": top["확인_avg"].map("{:+.2%}".format),
        "확인 수익난비율": top["확인_prof"].map("{:.1%}".format),
        "확인 손익비": top["확인_pf"].map("{:.2f}".format),
        "평균보유": top["확인_hold"].map("{:.0f}일".format),
        "신호수(발견/확인)": top["발견_n"].map("{:,.0f}".format) + " / " + top["확인_n"].map("{:,.0f}".format),
    })
    pd.set_option("display.width", 300)
    pd.set_option("display.unicode.east_asian_width", True)
    print("\n최고 전략 5개 (발견 기간으로 선정 → 확인 기간 검증)\n" + show.to_string())

    # 원래 규칙과 비교
    base_rows = res[res["매도규칙"] == "원래 규칙 (25일선 50% / 60일선 50%)"].set_index("매수신호")
    print("\n같은 매수 신호에 원래 매도 규칙을 썼을 때 확인 기간 평균수익:")
    for _, row in top.iterrows():
        print(f"   {row['매수신호']}: {base_rows.loc[row['매수신호'], '확인_avg']:+.2%}"
              f"  →  새 매도 규칙 {row['확인_avg']:+.2%}")
    show.to_csv(os.path.join(RESULT_DIR, "best_top5.csv"), encoding="utf-8-sig")

    # ---- 계좌 시뮬레이션 ----
    print(f"\n3) 계좌 시뮬레이션 (최대 {SLOTS}종목 동시 보유, 종목당 자산의 1/{SLOTS})")
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    tv = p["tv20"].to_numpy()
    sim_rows, curves = [], {}
    for i, row in top.iterrows():
        r = np.where(signals[row["매수신호"]] & universe)[0]
        m = path_matrix(p, P, r)
        ret, hold, value = run_exit(m, EXITS[row["매도규칙"]])
        df = pd.DataFrame({"row": r, "ret": ret, "hold": hold})
        entry_idx = m["date_idx"][:, 0]
        t = df.assign(entry_idx=entry_idx, tv20=tv[df["row"]], row_key=np.arange(len(df)))
        paths = [value[j] for j in range(len(df))]
        for label, start in [("전체", None), ("확인", int(np.searchsorted(dates, np.datetime64(SPLIT_DATE))))]:
            c = portfolio(t, dates, paths, start)
            st = curve_stats(c)
            k = idx["KOSPI"].reindex(c.index).ffill()
            q = idx["KOSDAQ"].reindex(c.index).ffill()
            sim_rows.append({"순위": i, "기간": label, **{kk: v for kk, v in st.items()},
                             "코스피": k.iloc[-1] / k.iloc[0] - 1, "코스닥": q.iloc[-1] / q.iloc[0] - 1})
            if label == "전체":
                curves[i] = c
    sim = pd.DataFrame(sim_rows)
    fmt = sim.copy()
    for col in ["누적수익률", "연평균수익률", "최대낙폭", "코스피", "코스닥"]:
        fmt[col] = fmt[col].map("{:+.1%}".format)
    fmt["샤프지수"] = fmt["샤프지수"].map("{:.2f}".format)
    print(fmt.to_string(index=False))
    sim.to_csv(os.path.join(RESULT_DIR, "best_portfolio.csv"), index=False, encoding="utf-8-sig")

    # ---- 차트 ----
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    for i, c in curves.items():
        axes[0].plot(c / c.iloc[0], label=f"#{i}")
    for name, color in [("KOSPI", "black"), ("KOSDAQ", "gray")]:
        s = idx[name].reindex(curves[1].index).ffill()
        axes[0].plot(s / s.iloc[0], label=name, color=color, linestyle="--")
    axes[0].axvline(pd.Timestamp(SPLIT_DATE), color="k", alpha=0.3)
    axes[0].set_yscale("log")
    axes[0].set_title(f"Account simulation (max {SLOTS} positions, log scale)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    x = np.arange(len(top))
    axes[1].bar(x - 0.2, top["발견_avg"] * 100, 0.4, label="Discovery (2016-22)")
    axes[1].bar(x + 0.2, top["확인_avg"] * 100, 0.4, label="Out-of-sample (2023-26)")
    axes[1].set_xticks(x, [f"#{i}" for i in top.index])
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].set_title("Average return per trade after cost (%)")
    axes[1].legend()
    axes[1].grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "best_top5.png"), dpi=110)
    print("\n차트 범례: " + ", ".join(f"#{i}={r['매수신호']} → {r['매도규칙']}" for i, r in top.iterrows()))


if __name__ == "__main__":
    main()
