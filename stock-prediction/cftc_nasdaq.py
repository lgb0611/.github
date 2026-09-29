"""
나스닥100 선물: 레버리지 펀드(헤지펀드 등) 순포지션 vs 나스닥100 지수, 10년 비교

원본 데이터
- 포지션: 미국 CFTC 'Traders in Financial Futures' 보고서(선물만), "NASDAQ-100 Consolidated"
  (E-mini·Micro·기본 계약을 합친 값, 매주 화요일 기준, 금요일 발표)
  https://publicreporting.cftc.gov/resource/gpe5-46if
- 지수: FRED NASDAQ100 (나스닥100 일별 종가)

달러 금액 = 계약 수 × 계약 승수($20 또는 $100) × 그날 나스닥100 지수
(Goldman Sachs 그래프와 같은 방식. 2026-08-04 숏 $83.7B, 순포지션 -$59.8B로 일치)

실행: python cftc_nasdaq.py
"""
import os

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

RESULT_DIR = "results_us"
START = "2016-09-01"   # 10년
CFTC_URL = ("https://publicreporting.cftc.gov/resource/gpe5-46if.csv"
            "?$where=cftc_contract_market_code='20974%2B'"
            "&$order=report_date_as_yyyy_mm_dd&$limit=5000")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NASDAQ100&cosd=2009-01-01"
FORWARD_WEEKS = [4, 13, 26]

# 색 (밝은 배경 기준)
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, RED = "#2a78d6", "#e34948"


def set_korean_font():
    """컴퓨터에 있는 한글 글꼴을 찾아서 씁니다 (윈도우·맥·리눅스)."""
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "WenQuanYi Zen Hei"]:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_data(start=START):
    cftc = pd.read_csv(CFTC_URL)
    cftc["date"] = pd.to_datetime(cftc["report_date_as_yyyy_mm_dd"])
    # 2023년 중반 전에는 $100 계약 기준, 이후는 $20(E-mini) 기준으로 계약 수를 셈
    cftc["mult"] = cftc["contract_units"].str.extract(r"\$(\d+)").astype(float)

    ndx = pd.read_csv(FRED_URL, parse_dates=["observation_date"])
    ndx = pd.to_numeric(ndx.set_index("observation_date")["NASDAQ100"], errors="coerce").dropna()

    df = cftc.set_index("date")[["mult", "open_interest_all",
                                 "lev_money_positions_long", "lev_money_positions_short"]]
    df.columns = ["mult", "oi", "long_contracts", "short_contracts"]
    df["ndx"] = ndx.reindex(df.index, method="ffill")   # 휴일이면 직전 종가
    usd_bn = df["mult"] * df["ndx"] / 1e9
    df["long_bn"] = df["long_contracts"] * usd_bn
    df["short_bn"] = df["short_contracts"] * usd_bn
    df["net_bn"] = df["long_bn"] - df["short_bn"]
    df["net_pct_oi"] = (df["long_contracts"] - df["short_contracts"]) / df["oi"] * 100
    for w in FORWARD_WEEKS:
        df[f"ndx_next_{w}w"] = (df["ndx"].shift(-w) / df["ndx"] - 1) * 100
    return df.loc[start:], ndx.loc[start:]


def forward_table(df):
    """순포지션(미결제약정 대비 %)을 5구간으로 나눠 이후 나스닥100 수익률 비교."""
    d = df.copy()
    d["group"] = pd.qcut(d["net_pct_oi"], 5, labels=["1 (숏 가장 많음)", "2", "3", "4", "5 (롱 가장 많음)"])
    rows = []
    for g, x in list(d.groupby("group", observed=True)) + [("전체", d)]:
        row = {"구간": g, "주 수": len(x),
               "순포지션 % 범위": f"{x['net_pct_oi'].min():.1f} ~ {x['net_pct_oi'].max():.1f}"}
        for w in FORWARD_WEEKS:
            r = x[f"ndx_next_{w}w"].dropna()
            row[f"{w}주 뒤 평균"] = round(r.mean(), 2)
            row[f"{w}주 뒤 상승 확률"] = round((r > 0).mean() * 100, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def draw(df, ndx):
    set_korean_font()
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True, facecolor=SURFACE,
                             gridspec_kw={"height_ratios": [1.1, 1, 0.8], "hspace": 0.28})
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, lw=1)
        ax.tick_params(colors=MUTED, labelcolor=INK2, length=0)
        for s in ["top", "right", "left"]:
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color("#c3c2b7")

    # 1) 나스닥100 지수 (로그 눈금: 같은 % 변화가 같은 높이)
    ax = axes[0]
    ax.plot(ndx.index, ndx.values, color=BLUE, lw=1.6)
    ax.set_yscale("log")
    ticks = [5000, 7500, 10000, 15000, 20000, 30000]
    ax.set_yticks(ticks, [f"{t:,}" for t in ticks])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_title("나스닥100 지수 (로그 눈금, 일별 종가)", loc="left", color=INK, fontsize=12, fontweight="bold")
    last = ndx.index[-1]
    ax.plot(last, ndx.iloc[-1], "o", ms=6, color=BLUE, mec=SURFACE, mew=2)
    ax.annotate(f"{ndx.iloc[-1]:,.0f}\n({last:%Y-%m-%d})", (last, ndx.iloc[-1]), xytext=(8, -4),
                textcoords="offset points", color=INK, fontsize=9, va="top")

    # 2) 순포지션 (달러)
    def signed_area(ax, s, fmt, title):
        ax.plot(s.index, s.values, color=INK2, lw=1.4)
        ax.fill_between(s.index, s.values, 0, where=s.values >= 0, color=BLUE, alpha=0.18, lw=0, interpolate=True)
        ax.fill_between(s.index, s.values, 0, where=s.values < 0, color=RED, alpha=0.18, lw=0, interpolate=True)
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.margins(y=0.12)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt))
        ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
        lo = s.idxmin()
        ax.plot(lo, s[lo], "o", ms=6, color=RED, mec=SURFACE, mew=2)
        ax.annotate(f"최저 {fmt(s[lo], None)}\n({lo:%Y-%m-%d})", (lo, s[lo]), xytext=(-10, 0),
                    textcoords="offset points", ha="right", va="center", color=INK, fontsize=9)
        e = s.index[-1]
        ax.plot(e, s.iloc[-1], "o", ms=6, color=INK2, mec=SURFACE, mew=2)
        ax.annotate(f"최근 {fmt(s.iloc[-1], None)}\n({e:%Y-%m-%d})", (e, s.iloc[-1]), xytext=(8, 0),
                    textcoords="offset points", va="center", color=INK, fontsize=9)

    signed_area(axes[1], df["net_bn"], lambda v, _: f"-${-v:,.0f}B" if v < 0 else f"${v:,.0f}B",
                "레버리지 펀드 순포지션, 나스닥100 선물 (롱 - 숏, 10억 달러, 주간)")
    # 3) 순포지션 (미결제약정 대비 %) - 지수가 오르면 달러 금액이 커지는 효과를 뺀 값
    signed_area(axes[2], df["net_pct_oi"], lambda v, _: f"{v:,.0f}%",
                "같은 순포지션을 전체 미결제약정 대비 %로 (지수 상승 효과 제거)")

    # Goldman 그래프가 보여준 구간 표시
    for ax in axes:
        ax.axvspan(pd.Timestamp("2023-01-01"), pd.Timestamp("2026-08-11"), color="#f0efec", zorder=0, lw=0)
    axes[0].text(pd.Timestamp("2023-01-15"), 5200, "Goldman 그래프 구간", color=MUTED, fontsize=9)

    axes[2].xaxis.set_major_locator(mdates.YearLocator())
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[2].set_xlim(df.index[0], df.index[-1] + pd.Timedelta(days=260))
    fig.text(0.125, 0.045, "자료: CFTC Traders in Financial Futures (NASDAQ-100 Consolidated, 선물만), FRED NASDAQ100. "
             "달러 금액 = 계약 수 × 승수 × 지수.", color=MUTED, fontsize=9)
    plt.savefig(os.path.join(RESULT_DIR, "cftc_nasdaq.png"), dpi=110, bbox_inches="tight", facecolor=SURFACE)
    plt.close()


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) CFTC·FRED 데이터 받는 중...")
    df, ndx = load_data()
    print(f"   {df.index[0]:%Y-%m-%d} ~ {df.index[-1]:%Y-%m-%d}, {len(df)}주")

    check = df.loc["2026-08-04", ["long_bn", "short_bn", "net_bn"]].round(1)
    print(f"2) Goldman 그래프 확인 (2026-08-04): 롱 ${check['long_bn']}B, 숏 ${check['short_bn']}B, 순 ${check['net_bn']}B")

    cols = ["ndx", "long_contracts", "short_contracts", "oi", "mult", "long_bn", "short_bn", "net_bn", "net_pct_oi"]
    df[cols].round(2).to_csv(os.path.join(RESULT_DIR, "cftc_nasdaq.csv"), index_label="date")

    wk = df["ndx"].pct_change()
    print("3) 같은 주 움직임 상관계수 (순포지션 변화 vs 지수 수익률)")
    print(f"   달러 기준 {df['net_bn'].diff().corr(wk):.2f} / % 기준 {df['net_pct_oi'].diff().corr(wk):.2f}")
    print(f"   순포지션 수준 vs 지난 13주 지수 수익률: {df['net_pct_oi'].corr(df['ndx'].pct_change(13)):.2f}")

    ft = forward_table(df)
    ft.to_csv(os.path.join(RESULT_DIR, "cftc_nasdaq_forward.csv"), index=False)
    print("4) 순포지션 5구간별 이후 나스닥100 수익률 (%)")
    print(ft.to_string(index=False))

    draw(df, ndx)
    print(f"5) 저장: {RESULT_DIR}/cftc_nasdaq.png, cftc_nasdaq.csv, cftc_nasdaq_forward.csv")


if __name__ == "__main__":
    main()
