"""
공포·공매도·포지션·설문 지표로 나스닥100 매수 타이밍 잡기: 어떤 지표가 통했나?

지표 (모두 무료 공개 데이터)
- VIX: S&P500 옵션으로 계산한 공포지수 (FRED VIXCLS, 1990~)
- DIX / GEX: SqueezeMetrics. DIX = 다크풀(장외) 거래 중 공매도 비율, GEX = 옵션 딜러의 감마 노출 (2011~)
- 풋콜 비율: CBOE 주식옵션 풋 거래량 ÷ 콜 거래량, 10일 평균 (2006~2019.10, 이후 무료 파일 없음)
- 공매도잔고: FINRA. QQQ(나스닥100 ETF)와 나스닥 상장 종목 전체 (2017.12~)
  공매도잔고 ÷ 하루 평균 거래량 = '며칠치 거래량만큼 공매도가 쌓였나'(days to cover)
- 헤지펀드 선물 순포지션: CFTC (19·20부와 같은 데이터, 2010~)
- AAII 투자자 심리조사: 미국 개인투자자협회 회원에게 매주 "앞으로 6개월 주가가 오를까/그대로/내릴까"를 묻는 설문 (1987~)
  매주 목요일 발표. 강세-약세 차이 = 오른다 % - 내린다 %

방법 (20부와 같음)
- 매주 금요일까지 발표된 값으로 신호 판단 → 다음 거래일(월요일) 종가에 나스닥100 매수
  (공매도잔고는 결제일 약 8영업일 뒤 발표 → 결제일 + 12일부터 사용, CFTC는 화요일 기준 → 금요일 발표)
- '2년 중 상위/하위 10%' = 최근 104주 값 중 순위 (그때까지 알 수 있는 값만 사용)
- 비교 기준: 같은 지표를 쓸 수 있는 같은 기간에 아무 주에나 샀을 때
- 우연일 확률(p): 신호 날짜를 통째로 밀어서 다시 계산했을 때 실제 이상으로 좋은 결과가 나온 비율

실행: python sentiment_timing.py   (처음에는 나스닥 공매도잔고를 받느라 약 20분, 이후 data_us/에 저장된 파일 사용)
"""
import io
import os
import time

import matplotlib
import numpy as np
import pandas as pd
import requests

import cftc_contrarian as K
import cftc_nasdaq as C

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DATA_DIR = "data_us"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
DIX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
PC_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
FINRA_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
SI_LAG_DAYS = 12
RANK_WEEKS = 104
START = "1990-06-01"


def fred(series_id):
    s = pd.read_csv(FRED_URL.format(series_id), parse_dates=["observation_date"]).set_index("observation_date")[series_id]
    return pd.to_numeric(s, errors="coerce").dropna()


def finra(body):
    for t in range(5):
        try:
            r = requests.post(FINRA_URL, json=body, timeout=60,
                              headers={"Content-Type": "application/json", "Accept": "application/json"})
            r.raise_for_status()
            return (r.json() if r.text else []), int(r.headers.get("record-total", 0))
        except requests.RequestException:
            time.sleep(2 ** t)
    raise RuntimeError("FINRA 데이터를 받지 못했습니다")


def load_qqq_short():
    rows, _ = finra({"limit": 5000, "fields": ["settlementDate", "currentShortPositionQuantity", "averageDailyVolumeQuantity"],
                     "compareFilters": [{"compareType": "equal", "fieldName": "symbolCode", "fieldValue": "QQQ"}],
                     "dateRangeFilters": [{"fieldName": "settlementDate", "startDate": "2010-01-01", "endDate": "2099-12-31"}]})
    d = pd.DataFrame(rows)
    d["date"] = pd.to_datetime(d["settlementDate"])
    d = d.set_index("date").sort_index()
    return d["currentShortPositionQuantity"] / d["averageDailyVolumeQuantity"]


def load_nasdaq_short(dates):
    """나스닥 상장 종목 전체(FINRA 시장 구분 NNM)의 공매도잔고 합 ÷ 하루 평균 거래량 합. 받은 날짜는 저장해 두고 재사용."""
    path = os.path.join(DATA_DIR, "nasdaq_short_interest.csv")
    old = pd.read_csv(path, parse_dates=["date"]) if os.path.exists(path) else pd.DataFrame(columns=["date", "short", "adv"])
    todo = [d for d in dates if d not in set(old["date"])]
    rows = []
    for i, d in enumerate(todo):
        short = adv = off = 0
        while True:
            x, total = finra({"limit": 5000, "offset": off,
                              "fields": ["currentShortPositionQuantity", "averageDailyVolumeQuantity"],
                              "compareFilters": [{"compareType": "equal", "fieldName": "settlementDate", "fieldValue": f"{d:%Y-%m-%d}"},
                                                 {"compareType": "equal", "fieldName": "marketClassCode", "fieldValue": "NNM"}]})
            short += sum(v["currentShortPositionQuantity"] or 0 for v in x)
            adv += sum(v["averageDailyVolumeQuantity"] or 0 for v in x)
            off += 5000
            if off >= total:
                break
        rows.append({"date": d, "short": short, "adv": adv})
        if i % 20 == 0:
            print(f"   나스닥 공매도잔고 {i + 1}/{len(todo)} ({d:%Y-%m-%d})")
    if rows:
        old = pd.concat([old, pd.DataFrame(rows)]).sort_values("date")
        os.makedirs(DATA_DIR, exist_ok=True)
        old.to_csv(path, index=False)
    s = old.set_index("date")
    return s["short"] / s["adv"]


def load_put_call():
    pc = pd.read_csv(PC_URL, skiprows=2)
    pc.columns = [c.strip() for c in pc.columns]
    pc.index = pd.to_datetime(pc["DATE"].str.strip(), format="mixed")
    return pc["P/C Ratio"].astype(float).rolling(10).mean().dropna()


def load_aaii():
    """AAII 설문 엑셀 파일 (브라우저처럼 접속해야 받아짐). 못 받으면 data_us/에 저장해 둔 파일 사용."""
    path = os.path.join(DATA_DIR, "aaii_sentiment.csv")
    try:
        r = requests.get(AAII_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"})
        r.raise_for_status()
        x = pd.read_excel(io.BytesIO(r.content), header=None, usecols=range(4))
        x.columns = ["date", "bullish", "neutral", "bearish"]
        x["date"] = pd.to_datetime(x["date"], errors="coerce", format="mixed")
        x = x.dropna(subset=["date"]).set_index("date").apply(pd.to_numeric, errors="coerce").dropna()
        os.makedirs(DATA_DIR, exist_ok=True)
        x.to_csv(path)
    except Exception as e:   # 사이트가 막히면 예전에 받은 파일로
        print(f"   AAII 다운로드 실패({e}) → {path} 사용")
        x = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return x.sort_index()


def to_weekly(s, fridays, max_age_days):
    """매주 금요일 기준으로 그때까지 알려진 마지막 값. 너무 오래된 값(데이터가 끊김)은 비움."""
    s = s.dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    v = s.reindex(fridays, method="ffill")
    last = pd.Series(s.index, index=s.index).reindex(fridays, method="ffill")
    v[(fridays - pd.DatetimeIndex(last)).days > max_age_days] = np.nan
    return v


def rank_2y(s):
    s = s.dropna()
    return s.rolling(RANK_WEEKS).apply(lambda x: (x <= x[-1]).mean() * 100, raw=True)


def build_panel():
    print("1) 데이터 받는 중...")
    ndx = fred("NASDAQ100")
    vix = fred("VIXCLS")
    dix = pd.read_csv(DIX_URL, parse_dates=["date"]).set_index("date")
    pc = load_put_call()
    qqq = load_qqq_short()
    nas = load_nasdaq_short(list(qqq.index))
    cftc, _ = C.load_data("2010-01-01")
    aaii = load_aaii()

    fridays = pd.date_range(START, ndx.index[-1], freq="W-FRI")
    W = pd.DataFrame(index=fridays)
    W["VIX"] = to_weekly(vix, fridays, 7)
    W["DIX"] = to_weekly(dix["dix"].rolling(5).mean(), fridays, 7)
    W["GEX"] = to_weekly(dix["gex"].rolling(5).mean() / 1e9, fridays, 7)
    W["풋콜"] = to_weekly(pc, fridays, 7)
    qqq.index = qqq.index + pd.Timedelta(days=SI_LAG_DAYS)
    nas.index = nas.index + pd.Timedelta(days=SI_LAG_DAYS)
    W["QQQ 공매도"] = to_weekly(qqq, fridays, 25)
    W["나스닥 공매도"] = to_weekly(nas, fridays, 25)
    net = cftc["net_pct_oi"].copy()
    net.index = net.index + pd.Timedelta(days=3)   # 화요일 기준 → 금요일 발표
    W["헤지펀드 순포지션"] = to_weekly(net, fridays, 10)
    W["AAII 약세"] = to_weekly(aaii["bearish"] * 100, fridays, 10)
    W["AAII 강세-약세"] = to_weekly((aaii["bullish"] - aaii["bearish"]) * 100, fridays, 10)
    for col in list(W.columns):
        W[col + " 순위"] = rank_2y(W[col]).reindex(fridays)

    # 금요일 신호 → 다음 거래일 종가 매수
    entry = ndx.index.searchsorted(fridays + pd.Timedelta(days=1))
    px = ndx.values
    for name, h in K.HORIZONS.items():
        r = np.full(len(W), np.nan)
        ok = entry + h < len(px)
        r[ok] = (px[entry[ok] + h] / px[entry[ok]] - 1) * 100
        W[f"next_{name}"] = r
    W["entry_date"] = [ndx.index[i] if i < len(ndx) else pd.NaT for i in entry]
    return W, ndx


# (이름, 쓰는 지표, 순위 사용 여부, 조건)
SIGNALS = [
    ("VIX 30 이상", "VIX", False, lambda W: W["VIX"] >= 30),
    ("VIX 2년 중 상위 10%", "VIX", True, lambda W: W["VIX 순위"] >= 90),
    ("GEX 0 미만 (딜러 감마 마이너스)", "GEX", False, lambda W: W["GEX"] < 0),
    ("DIX 0.45 이상 (다크풀 공매도 비율 높음)", "DIX", False, lambda W: W["DIX"] >= 0.45),
    ("풋콜 비율 2년 중 상위 10%", "풋콜", True, lambda W: W["풋콜 순위"] >= 90),
    ("AAII 약세 응답 50% 이상", "AAII 약세", False, lambda W: W["AAII 약세"] >= 50),
    ("AAII 강세-약세 -20%p 이하", "AAII 강세-약세", False, lambda W: W["AAII 강세-약세"] <= -20),
    ("AAII 강세-약세 2년 중 하위 10%", "AAII 강세-약세", True, lambda W: W["AAII 강세-약세 순위"] <= 10),
    ("QQQ 공매도잔고 2년 중 상위 10%", "QQQ 공매도", True, lambda W: W["QQQ 공매도 순위"] >= 90),
    ("나스닥 공매도잔고 2년 중 상위 10%", "나스닥 공매도", True, lambda W: W["나스닥 공매도 순위"] >= 90),
    ("헤지펀드 선물 순포지션 -20% 이하", "헤지펀드 순포지션", False, lambda W: W["헤지펀드 순포지션"] <= -20),
    ("헤지펀드 선물 순포지션 2년 중 하위 10%", "헤지펀드 순포지션", True, lambda W: W["헤지펀드 순포지션 순위"] <= 10),
]


def evaluate(W):
    rows = []
    for name, col, ranked, rule in SIGNALS:
        usable = W[col].notna() & (W[col + " 순위"].notna() if ranked else True)
        sig_all = rule(W).fillna(False) & usable
        row = {"신호": name, "기간": f"{W.index[usable][0]:%Y.%m}~{W.index[usable][-1]:%Y.%m}"}
        for h in K.HORIZONS:
            ret = W[f"next_{h}"]
            ok = (usable & ret.notna()).values
            sig, r = sig_all.values[ok], ret.values[ok]
            if h == "13주":
                row["신호 주 수"] = int(sig.sum())
                row["독립 구간"] = len(K.episode_starts(sig))
                row["13주 뒤 최악(%)"] = round(r[sig].min(), 1)
            row[f"{h} 뒤 평균(%)"] = round(r[sig].mean(), 1)
            row[f"{h} 기준 평균(%)"] = round(r.mean(), 1)
            row[f"{h} 뒤 상승확률(%)"] = round((r[sig] > 0).mean() * 100, 1)
            row[f"{h} 기준 상승확률(%)"] = round((r > 0).mean() * 100, 1)
            if h in ("13주", "26주"):
                row[f"{h} 평균 p"] = round(K.shift_pvalue(sig, r, np.mean), 2)
                row[f"{h} 상승확률 p"] = round(K.shift_pvalue(sig, r, lambda x: (x > 0).mean()), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def draw(W, ndx, table):
    C.set_korean_font()
    fig = plt.figure(figsize=(13, 13.5), facecolor=C.SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[0.8, 1.2], hspace=0.3, wspace=0.08)
    ax_t, ax_m, ax_h = fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
    for ax in (ax_t, ax_m, ax_h):
        ax.set_facecolor(C.SURFACE)
        ax.tick_params(colors=C.MUTED, labelcolor=C.INK2, length=0)
        for sp in ["top", "right", "left"]:
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color("#c3c2b7")

    # 1) VIX 30 이상일 때 산 시점 (구간 첫 주)
    ax = ax_t
    ax.grid(axis="y", color=C.GRID, lw=1)
    shown = ndx.loc[START:]
    ax.plot(shown.index, shown.values, color=C.INK2, lw=1.1)
    ax.set_yscale("log")
    ticks = [250, 500, 1000, 2500, 5000, 10000, 25000]
    ax.set_yticks(ticks, [f"{t:,}" for t in ticks])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    s = (W["VIX"] >= 30).values
    for i in K.episode_starts(s):
        d, r = W["entry_date"].iloc[i], W["next_13주"].iloc[i]
        color = C.MUTED if np.isnan(r) else (C.BLUE if r > 0 else C.RED)
        ax.plot(d, ndx[d], "o", ms=8, color=color, mec=C.SURFACE, mew=2, zorder=3)
    for c, lab in [(C.BLUE, "13주 뒤 상승"), (C.RED, "13주 뒤 하락")]:
        ax.plot([], [], "o", ms=8, color=c, mec=C.SURFACE, mew=2, label=lab)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=C.INK2)
    ax.set_title("나스닥100 지수와 'VIX 30 이상'에서 산 시점 (구간 첫 주)", loc="left", color=C.INK, fontsize=12, fontweight="bold")
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # 2) 신호 vs 같은 기간 아무 때나: 13주 뒤 평균 수익률 / 상승 확률
    t = table.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(t))
    for ax, key, title, unit in [(ax_m, "평균(%)", "13주 뒤 평균 수익률", "%"), (ax_h, "상승확률(%)", "13주 뒤 상승 확률", "%")]:
        ax.grid(axis="x", color=C.GRID, lw=1)
        base, sig = t[f"13주 기준 {key}"], t[f"13주 뒤 {key}"]
        pcol = "13주 평균 p" if key == "평균(%)" else "13주 상승확률 p"
        for yi in y:
            better = sig[yi] > base[yi]
            ax.plot([base[yi], sig[yi]], [yi, yi], color=GRID_LINE, lw=2, zorder=1)
            ax.plot(base[yi], yi, "o", ms=8, color=C.MUTED, mec=C.SURFACE, mew=2, zorder=2)
            ax.plot(sig[yi], yi, "o", ms=9, color=C.BLUE if better else C.RED, mec=C.SURFACE, mew=2, zorder=3)
            star = " *" if t[pcol][yi] < 0.05 else ""
            # 라벨은 신호 점 바깥쪽에 (좋아졌으면 오른쪽, 나빠졌으면 왼쪽)
            ax.annotate(f"{sig[yi]:.0f}{unit}{star}", (sig[yi], yi), xytext=(9 if better else -9, 0),
                        textcoords="offset points", va="center", ha="left" if better else "right",
                        color=C.INK, fontsize=9, fontweight="bold" if star else "normal")
        ax.set_title(title, loc="left", color=C.INK, fontsize=12, fontweight="bold")
        ax.set_ylim(-0.6, len(t) - 0.4)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax_m.set_yticks(y, [f"{n}  ({e}번)" for n, e in zip(t["신호"], t["독립 구간"])], fontsize=9)
    ax_h.set_yticks(y, [""] * len(y))
    lo, hi = min(t["13주 뒤 평균(%)"].min(), 0), t["13주 뒤 평균(%)"].max()
    ax_m.set_xlim(lo - 4, hi + 5)
    ax_h.set_xlim(35, 100)
    ax_m.plot([], [], "o", ms=8, color=C.MUTED, label="같은 기간 아무 때나")
    ax_m.plot([], [], "o", ms=8, color=C.BLUE, label="신호 때 매수 (더 좋음)")
    ax_m.plot([], [], "o", ms=8, color=C.RED, label="신호 때 매수 (더 나쁨)")
    ax_m.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=C.INK2)

    fig.text(0.02, 0.035, "괄호 = 독립 구간 수, * = 우연일 확률 5% 미만. 금요일 신호 → 다음 거래일 종가 매수. "
             "자료: FRED(VIX, NASDAQ100), SqueezeMetrics(DIX, GEX), CBOE(풋콜), AAII, FINRA(공매도잔고), CFTC.",
             color=C.MUTED, fontsize=9)
    plt.savefig(os.path.join(C.RESULT_DIR, "sentiment_timing.png"), dpi=110, bbox_inches="tight", facecolor=C.SURFACE)
    plt.close()


GRID_LINE = "#c3c2b7"


def main():
    os.makedirs(C.RESULT_DIR, exist_ok=True)
    W, ndx = build_panel()
    table = evaluate(W)
    table.to_csv(os.path.join(C.RESULT_DIR, "sentiment_timing.csv"), index=False)
    pd.set_option("display.width", 250)
    show = ["신호", "기간", "독립 구간", "13주 뒤 평균(%)", "13주 기준 평균(%)", "13주 평균 p",
            "13주 뒤 상승확률(%)", "13주 기준 상승확률(%)", "13주 상승확률 p", "26주 뒤 평균(%)", "26주 기준 평균(%)", "13주 뒤 최악(%)"]
    print("2) 신호별 13주 뒤 나스닥100 수익률 (기준 = 같은 기간 아무 때나)")
    print(table[show].to_string(index=False))

    rows = []
    for name, col, ranked, rule in SIGNALS:
        s = rule(W).fillna(False).values
        for i in K.episode_starts(s):
            rows.append({"신호": name, "신호일": f"{W.index[i]:%Y-%m-%d}", "매수일": f"{W['entry_date'].iloc[i]:%Y-%m-%d}",
                         "지표 값": round(W[col].iloc[i], 3),
                         **{f"{h} 뒤(%)": round(W[f"next_{h}"].iloc[i], 1) for h in K.HORIZONS}})
    pd.DataFrame(rows).to_csv(os.path.join(C.RESULT_DIR, "sentiment_timing_episodes.csv"), index=False)

    draw(W, ndx, table)
    print(f"3) 저장: {C.RESULT_DIR}/sentiment_timing.png, sentiment_timing.csv, sentiment_timing_episodes.csv")


if __name__ == "__main__":
    main()
