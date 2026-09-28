"""
대형주(한국 시가총액 5조 원 이상, 미국 300억 달러 이상)만 매수할 때 최적의 매도 조건과 성과 개선 여부

- 과거 시가총액 추정: (현재 시가총액 ÷ 현재 주가) = 주식 수, × 그날 종가(액면분할 반영)
  → 증자·자사주 매입으로 주식 수가 바뀐 경우는 반영되지 않음
- 매수 신호 5개 × (시총 조건 있음 / 없음) × 매도 후보 약 80개(13부 단기 59개 + 14부 중기 20개)
- 한국 발견 기간(2016~22) 계좌 샤프지수로 고르고, 한국 확인 기간과 미국 두 기간으로 검증

실행: python largecap.py && MARKET=us python largecap.py && python largecap.py summary
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import requests

import best_strategies as B
import exit_opt as X
import midterm as M
import strategies as S
import vcp_test as V

SPLIT = np.datetime64(S.SPLIT_DATE)
CAP_MIN = {"kr": 5e12, "us": 30e9}[S.MARKET]          # 5조 원 / 300억 달러
MIN_TRADES = 30                                        # 한국 발견 기간 거래가 이보다 적으면 순위에서 제외


def current_caps(p):
    """종목별 주식 수 추정치 = 현재 시가총액 / 현재 주가."""
    if S.MARKET == "kr":
        lst = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
        last_close = p.groupby("code")["close"].last()
        cap = lst.set_index("code")["market_cap_억"] * 1e8
        return cap / last_close.reindex(cap.index)
    path = os.path.join(S.DATA_DIR, "market_cap.csv")
    if not os.path.exists(path):
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true"
        rows = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()["data"]["rows"]
        df = pd.DataFrame(rows)
        df["code"] = df["symbol"].str.replace("/", "-", regex=False)
        df["market_cap"] = pd.to_numeric(df["marketCap"], errors="coerce")
        df["last_price"] = pd.to_numeric(df["lastsale"].str.replace("$", "", regex=False), errors="coerce")
        df[["code", "market_cap", "last_price"]].to_csv(path, index=False)
    df = pd.read_csv(path).dropna().set_index("code")
    df = df[df["last_price"] > 0]
    return df["market_cap"] / df["last_price"]


def all_exits():
    ex = {X.name_of(legs): legs for legs in X.exit_candidates()}
    for name, legs in M.EXITS.items():
        ex.setdefault(name, legs)
    return ex


def run_market(exits=None, out_name="largecap.csv", only=None, caps=(True, False)):
    """only: 이 매수 신호만 계산 (None이면 5개 전부), caps: 대형주 조건 (True=대형주만, False=전체)"""
    print(f"[{S.MARKET.upper()}] 1) 데이터 준비 중...")
    p, P, out, ok, dates = M.prepare()
    shares = current_caps(p)
    p["mcap"] = p["close"] * p["code"].map(shares)
    big = (p["mcap"] >= CAP_MIN).to_numpy()
    print(f"   시가총액 기준 통과 종목 수(최근일): {int(((p['date'] == p['date'].max()) & big).sum())}")

    c = p["close"]
    rank = (c * p["volume"]).groupby(p["date"]).rank(ascending=False, method="first").to_numpy()
    bull = p["bull"].to_numpy()
    gap = (c / p["ma20"] - 1).to_numpy()
    tt = p["trend_template"].to_numpy()

    def cooled(cond):
        cond = cond.fillna(False)
        recent = P.shift(P.roll(cond.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        return (cond & (recent == 0)).to_numpy() & ok

    ath, w52 = cooled((c > p["hh_all"]) & (P.pos >= 500)), cooled(c > p["hh250"])
    entries = {
        "역사적 신고가 + 상승장": ath & bull,
        "역사적 신고가 + 거래대금 상위 10위 + 상승장": ath & bull & (rank <= 10),
        "역사적 신고가 + 이격 20% 이하 + 트렌드 템플릿 + 상승장": ath & bull & (gap <= 0.20) & tt,
        "52주 신고가 + 거래대금 상위 30위 + 상승장": w52 & bull & (rank <= 30),
        "52주 신고가 + 상승장": w52 & bull,
    }
    exits = exits or all_exits()
    success = out["success"].to_numpy()
    rows = []
    for ename, sig in entries.items():
        if only and ename not in only:
            continue
        for cap_on in caps:
            r = np.where(sig & big)[0] if cap_on else np.where(sig)[0]
            m = B.path_matrix(p, P, r)
            early = p["date"].to_numpy()[r] < SPLIT
            for xname, legs in exits.items():
                ret, hold, value = B.run_exit(m, legs)
                t = pd.DataFrame({"date": p["date"].to_numpy()[r], "ret": ret, "hold": hold,
                                  "entry_idx": m["date_idx"][:, 0], "tv20": -rank[r], "row_key": np.arange(len(r))})
                curve = B.portfolio(t, dates, [value[k] for k in range(len(r))])
                row = {"매수": ename, "시총조건": "대형주만" if cap_on else "전체", "매도": xname}
                for label, pm, before in [("발견", early, True), ("확인", ~early, False)]:
                    cs = V.seg_stats(curve, before)
                    row.update({f"{label}_거래수": int(pm.sum()), f"{label}_승률": success[r][pm].mean(),
                                f"{label}_거래평균": ret[pm].mean(), f"{label}_중간값": np.median(ret[pm]) if pm.any() else np.nan,
                                f"{label}_수익비율": (ret[pm] > 0).mean(), f"{label}_보유일": hold[pm].mean(),
                                f"{label}_10%이상손실": (ret[pm] <= -0.10 - S.COST + 1e-6).mean(),
                                f"{label}_연평균": cs["연평균수익률"], f"{label}_최대낙폭": cs["최대낙폭"],
                                f"{label}_샤프": cs["샤프지수"]})
                row["투자비중"] = V.avg_exposure(t, len(dates)) if len(t) else np.nan
                rows.append(row)
            del m
            print(f"   [{ename} / {'대형주만' if cap_on else '전체'}] 신호 {len(r)}건 × 매도 {len(exits)}개 완료")
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(S.RESULT_DIR, out_name), index=False, encoding="utf-8-sig")


def summary():
    kr = pd.read_csv(os.path.join(S.BASE, "results", "largecap.csv"))
    us = pd.read_csv(os.path.join(S.BASE, "results_us", "largecap.csv"))
    key = ["매수", "시총조건", "매도"]
    d = kr.merge(us, on=key, suffixes=("_kr", "_us"))
    pd.set_option("display.width", 340)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda x, a, fmt: (x[f"발견_{a}"].map(lambda v: f(v, fmt)) + " → " + x[f"확인_{a}"].map(lambda v: f(v, fmt))).values

    def show(x):
        return pd.DataFrame({
            "매수": x["매수"].values, "시총": x["시총조건"].values, "매도": x["매도"].values,
            "보유일": x["발견_보유일_kr"].map(lambda v: f(v, "{:.0f}")).values,
            "한국 거래수": arrow(x, "거래수_kr", "{:.0f}"), "한국 승률": arrow(x, "승률_kr", "{:.0%}"),
            "한국 거래평균": arrow(x, "거래평균_kr", "{:+.1%}"), "한국 연평균": arrow(x, "연평균_kr", "{:+.1%}"),
            "한국 샤프": arrow(x, "샤프_kr", "{:.2f}"), "한국 낙폭": arrow(x, "최대낙폭_kr", "{:.0%}"),
            "미국 거래수": arrow(x, "거래수_us", "{:.0f}"), "미국 거래평균": arrow(x, "거래평균_us", "{:+.1%}"),
            "미국 연평균": arrow(x, "연평균_us", "{:+.1%}"), "미국 샤프": arrow(x, "샤프_us", "{:.2f}"),
        })

    big = d[(d["시총조건"] == "대형주만") & (d["발견_거래수_kr"] >= MIN_TRADES)]
    print(f"[1] 대형주만: 한국 발견 기간 샤프 상위 10개 (한국 발견 거래 {MIN_TRADES}건 이상) — 발견 2016~22 → 확인 2023~26")
    print(show(big.sort_values("발견_샤프_kr", ascending=False).head(10)).to_string(index=False))
    mid = big[big["발견_보유일_kr"] >= 20]
    print("\n[2] 대형주만 + 평균 보유 20일 이상: 한국 발견 기간 샤프 상위 5개")
    print(show(mid.sort_values("발견_샤프_kr", ascending=False).head(5)).to_string(index=False))

    print("\n[3] 매수 신호별 최적 매도(한국 발견 기간 샤프 기준)에서 대형주 조건이 성과를 개선했나")
    out = []
    for ename in d["매수"].unique():
        for cap in ["대형주만", "전체"]:
            x = d[(d["매수"] == ename) & (d["시총조건"] == cap) & (d["발견_거래수_kr"] >= MIN_TRADES)]
            if len(x):
                out.append(x.sort_values("발견_샤프_kr", ascending=False).head(1))
    print(show(pd.concat(out)).to_string(index=False))

    print("\n[4] 같은 매도로 비교: 13·14부 최적 매도에서 대형주 조건 유무")
    for xname in ["+10% 익절 / 20일 청산", "40일 보유"]:
        x = d[d["매도"] == xname].sort_values(["매수", "시총조건"])
        print(f"\n  매도: {xname}")
        print(show(x).to_string(index=False))
    d.to_csv(os.path.join(S.BASE, "results", "largecap_summary.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    summary() if len(sys.argv) > 1 and sys.argv[1] == "summary" else run_market()
