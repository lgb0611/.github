"""
역발상 검증: 헤지펀드(레버리지 펀드)의 나스닥100 선물 순포지션이 크게 마이너스일 때 사면 더 잘 오르나?

데이터: cftc_nasdaq.py와 같음 (CFTC NASDAQ-100 Consolidated, FRED NASDAQ100), 2010.06 ~ 2026.09
매수 시점: CFTC 보고서는 화요일 기준 → 금요일 발표 → 다음 월요일 종가에 매수 (미래 정보 사용 없음)
보유 기간: 4주(20거래일) / 13주(63) / 26주(126) / 52주(252)

비교 방법
- 신호가 난 주에 샀을 때 vs 아무 주에나 샀을 때 (같은 기간)
- 우연일 확률(p): 신호 날짜들을 통째로 1~15년 밀어서 다시 계산했을 때
  실제보다 좋은 결과가 나오는 비율. 0.05보다 작아야 '우연이 아니다'라고 봄
- 독립 구간: 신호가 13주 넘게 끊겼다가 다시 나면 새 구간으로 셈 (연속된 주는 사실상 한 번의 기회)

실행: python cftc_contrarian.py
"""
import os

import matplotlib
import numpy as np
import pandas as pd

import cftc_nasdaq as C

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HORIZONS = {"4주": 20, "13주": 63, "26주": 126, "52주": 252}
LOOKBACK = 156   # 최근 3년(156주) 중 순위
GAP = 13         # 신호가 13주 넘게 끊기면 새 구간
SHORT_NAMES = {"아무 때나 (기준)": "아무 때나 (기준)", "달러 기준 -$20B 이하": "달러 -$20B 이하",
               "달러 기준 -$30B 이하": "달러 -$30B 이하", "미결제약정 대비 -15% 이하": "미결제약정 -15% 이하",
               "미결제약정 대비 -20% 이하": "미결제약정 -20% 이하",
               "최근 3년 중 하위 10% (+마이너스)": "3년 중 하위 10%", "4주 새 -10%p 이상 급감": "4주 새 -10%p 급감"}


def add_forward_returns(df, ndx):
    # 보고일(화) + 6일 = 다음 월요일, 휴일이면 그다음 거래일 종가에 매수
    entry = ndx.index.searchsorted(df.index + pd.Timedelta(days=6))
    df["entry_date"] = [ndx.index[i] if i < len(ndx) else pd.NaT for i in entry]
    px = ndx.values
    for name, h in HORIZONS.items():
        r = np.full(len(df), np.nan)
        ok = entry + h < len(px)
        r[ok] = (px[entry[ok] + h] / px[entry[ok]] - 1) * 100
        df[f"next_{name}"] = r
    df["pct_rank_3y"] = df["net_pct_oi"].rolling(LOOKBACK).apply(lambda x: (x <= x[-1]).mean() * 100, raw=True)
    return df


def make_signals(df):
    net = df["net_pct_oi"]
    return {
        "달러 기준 -$20B 이하": df["net_bn"] <= -20,
        "달러 기준 -$30B 이하": df["net_bn"] <= -30,
        "미결제약정 대비 -15% 이하": net <= -15,
        "미결제약정 대비 -20% 이하": net <= -20,
        "최근 3년 중 하위 10% (+마이너스)": (df["pct_rank_3y"] <= 10) & (net < 0),
        "4주 새 -10%p 이상 급감": net.diff(4) <= -10,
    }


def episode_starts(sig):
    idx = np.flatnonzero(sig)
    if len(idx) == 0:
        return idx
    return np.r_[idx[0], idx[1:][np.diff(idx) > GAP]]


def shift_pvalue(sig, ret, stat):
    """신호 날짜를 통째로 밀었을 때(1년~끝-1년) 실제 이상으로 좋은 결과가 나오는 비율."""
    actual = stat(ret[sig])
    sims = np.array([stat(ret[np.roll(sig, k)]) for k in range(52, len(ret) - 52)])
    return (sims >= actual).mean()


def signal_table(df, signals):
    rows = []
    for name, s in [("아무 때나 (기준)", pd.Series(True, index=df.index))] + list(signals.items()):
        row = {"신호": name}
        s = s.fillna(False)
        for h in HORIZONS:
            ret = df[f"next_{h}"]
            ok = ret.notna().values
            sig, r = s.values[ok], ret.values[ok]
            if h == "13주":
                row["신호 주 수"] = int(sig.sum())
                row["독립 구간"] = len(episode_starts(sig))
                row["처음 발생"] = f"{df.index[s.values][0]:%Y-%m}"
            row[f"{h} 뒤 평균(%)"] = round(r[sig].mean(), 1)
            row[f"{h} 뒤 상승확률(%)"] = round((r[sig] > 0).mean() * 100, 1)
            if name != "아무 때나 (기준)" and h in ("13주", "26주"):
                row[f"{h} 평균 p"] = round(shift_pvalue(sig, r, np.mean), 2)
                row[f"{h} 상승확률 p"] = round(shift_pvalue(sig, r, lambda x: (x > 0).mean()), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def correlations(df):
    """순포지션 수준과 이후 수익률의 순위 상관계수 (+ 같은 방식의 우연일 확률)."""
    rows = []
    for col, label in [("net_pct_oi", "미결제약정 대비 %"), ("pct_rank_3y", "최근 3년 중 순위")]:
        for h in HORIZONS:
            x = df[[col, f"next_{h}"]].dropna()
            a, b = x[col].rank().values, x[f"next_{h}"].rank().values
            rho = np.corrcoef(a, b)[0, 1]
            sims = np.array([np.corrcoef(np.roll(a, k), b)[0, 1] for k in range(52, len(a) - 52)])
            # 역발상이 맞다면 상관이 마이너스(숏이 많을수록 이후 수익 ↑)여야 함
            rows.append({"순포지션 지표": label, "보유": h, "상관계수": round(rho, 3),
                         "우연일 확률(p)": round((sims <= rho).mean(), 2), "주 수": len(x)})
    return pd.DataFrame(rows)


def draw(df, ndx, signals, table, main):
    C.set_korean_font()
    fig = plt.figure(figsize=(12, 10.5), facecolor=C.SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.35, wspace=0.42)
    ax_t, ax_s, ax_b = fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
    for ax in (ax_t, ax_s, ax_b):
        ax.set_facecolor(C.SURFACE)
        ax.tick_params(colors=C.MUTED, labelcolor=C.INK2, length=0)
        for sp in ["top", "right", "left"]:
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color("#c3c2b7")

    # 1) 지수 위에 신호 표시 (구간 첫 주, 13주 뒤 올랐으면 파랑 / 내렸으면 빨강)
    ax = ax_t
    ax.grid(axis="y", color=C.GRID, lw=1)
    shown = ndx.loc["2019-07":]   # 신호는 2020년부터만 나옴
    ax.plot(shown.index, shown.values, color=C.INK2, lw=1.2)
    ax.set_yscale("log")
    ticks = [7500, 10000, 15000, 20000, 30000]
    ax.set_yticks(ticks, [f"{t:,}" for t in ticks])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    s = signals[main].fillna(False).values
    for i in episode_starts(s):
        d, r = df["entry_date"].iloc[i], df["next_13주"].iloc[i]
        color = C.MUTED if np.isnan(r) else (C.BLUE if r > 0 else C.RED)
        ax.plot(d, ndx[d], "o", ms=9, color=color, mec=C.SURFACE, mew=2, zorder=3)
        if not np.isnan(r):
            ax.annotate(f"{r:+.1f}%", (d, ndx[d]), xytext=(0, 12), textcoords="offset points",
                        ha="center", color=C.INK, fontsize=9)
    ax.set_title(f"역발상 매수 시점: 순포지션 {main} (구간 첫 주, 숫자 = 13주 뒤 수익률)",
                 loc="left", color=C.INK, fontsize=12, fontweight="bold")
    pending = df["next_13주"].iloc[episode_starts(s)].isna().any()
    for c, lab in [(C.BLUE, "13주 뒤 상승"), (C.RED, "13주 뒤 하락")] + ([(C.MUTED, "아직 13주 안 됨")] if pending else []):
        ax.plot([], [], "o", ms=8, color=c, mec=C.SURFACE, mew=2, label=lab)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=C.INK2)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # 2) 산점도: 순포지션 vs 13주 뒤 수익률 + 5%p 구간 평균
    ax = ax_s
    ax.grid(color=C.GRID, lw=1)
    x = df[["net_pct_oi", "next_13주"]].dropna()
    ax.scatter(x["net_pct_oi"], x["next_13주"], s=10, color=C.BLUE, alpha=0.25, lw=0)
    bins = np.arange(-35, 45, 5)
    g = x.groupby(pd.cut(x["net_pct_oi"], bins), observed=True)["next_13주"].agg(["mean", "size"])
    g = g[g["size"] >= 15]
    mids = [iv.mid for iv in g.index]
    ax.plot(mids, g["mean"], color=C.INK, lw=2, marker="o", ms=5, mec=C.SURFACE, mew=1.5, label="5%p 구간 평균")
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.axhline(x["next_13주"].mean(), color=C.MUTED, lw=1.5, label=f"전체 평균 ({x['next_13주'].mean():.1f}%)")
    ax.set_xlabel("순포지션 (미결제약정 대비 %)  ← 숏 많음 · 롱 많음 →", color=C.INK2, fontsize=9)
    ax.set_ylabel("13주 뒤 나스닥100 수익률 (%)", color=C.INK2, fontsize=9)
    rho = np.corrcoef(x["net_pct_oi"].rank(), x["next_13주"].rank())[0, 1]
    ax.set_title(f"순포지션과 13주 뒤 수익률 (상관계수 {rho:.2f})", loc="left", color=C.INK, fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=C.INK2)

    # 3) 막대: 13주 뒤 상승 확률, 신호별 vs 아무 때나
    ax = ax_b
    t = table.iloc[::-1]
    base = table.iloc[0]["13주 뒤 상승확률(%)"]
    y = np.arange(len(t))
    colors = [C.MUTED if n == "아무 때나 (기준)" else C.BLUE for n in t["신호"]]
    ax.barh(y, t["13주 뒤 상승확률(%)"], height=0.55, color=colors)
    ax.axvline(base, color=C.INK, lw=1)
    for yi, (v, n, ep) in enumerate(zip(t["13주 뒤 상승확률(%)"], t["신호"], t["독립 구간"])):
        ax.text(v + 1, yi, f"{v:.0f}%" + ("" if n == "아무 때나 (기준)" else f"  ({ep}번)"),
                va="center", color=C.INK, fontsize=9)
    ax.set_yticks(y, [SHORT_NAMES[n] for n in t["신호"]], fontsize=9)
    ax.set_xlim(0, 110)
    ax.set_xlabel("13주 뒤 오른 비율 (%)  ·  괄호 = 독립 구간 수", color=C.INK2, fontsize=9)
    ax.set_title("13주 뒤 상승 확률", loc="left", color=C.INK, fontsize=12, fontweight="bold")

    fig.text(0.125, 0.035, "기간 2010.06~2026.09. 매수 = CFTC 발표 다음 월요일 종가. "
             "자료: CFTC Traders in Financial Futures (NASDAQ-100 Consolidated), FRED NASDAQ100.",
             color=C.MUTED, fontsize=9)
    plt.savefig(os.path.join(C.RESULT_DIR, "cftc_contrarian.png"), dpi=110, bbox_inches="tight", facecolor=C.SURFACE)
    plt.close()


def main():
    os.makedirs(C.RESULT_DIR, exist_ok=True)
    print("1) 데이터 받는 중 (2010년부터)...")
    df, ndx = C.load_data("2010-01-01")
    df = add_forward_returns(df, ndx)
    print(f"   {df.index[0]:%Y-%m-%d} ~ {df.index[-1]:%Y-%m-%d}, {len(df)}주")

    pd.set_option("display.width", 250)
    corr = correlations(df)
    corr.to_csv(os.path.join(C.RESULT_DIR, "cftc_contrarian_corr.csv"), index=False)
    print("2) 순포지션 수준 vs 이후 수익률 순위 상관 (마이너스여야 역발상이 맞음)")
    print(corr.to_string(index=False))

    signals = make_signals(df)
    table = signal_table(df, signals)
    table.to_csv(os.path.join(C.RESULT_DIR, "cftc_contrarian.csv"), index=False)
    print("3) 신호별 이후 나스닥100 수익률")
    print(table.to_string(index=False))

    main_signal = "미결제약정 대비 -20% 이하"
    rows = []
    for name, s in signals.items():
        for i in episode_starts(s.fillna(False).values):
            r = df.iloc[i]
            rows.append({"신호": name, "보고일": f"{df.index[i]:%Y-%m-%d}", "매수일": f"{r['entry_date']:%Y-%m-%d}",
                         "순포지션 %": round(r["net_pct_oi"], 1), "순포지션 $B": round(r["net_bn"], 1),
                         **{f"{h} 뒤(%)": round(r[f"next_{h}"], 1) for h in HORIZONS}})
    ep = pd.DataFrame(rows)
    ep.to_csv(os.path.join(C.RESULT_DIR, "cftc_contrarian_episodes.csv"), index=False)
    print(f"4) 구간별 결과 ({main_signal})")
    print(ep[ep["신호"] == main_signal].drop(columns="신호").to_string(index=False))

    draw(df, ndx, signals, table, main_signal)
    print(f"5) 저장: {C.RESULT_DIR}/cftc_contrarian.png, cftc_contrarian.csv, cftc_contrarian_corr.csv, cftc_contrarian_episodes.csv")


if __name__ == "__main__":
    main()
