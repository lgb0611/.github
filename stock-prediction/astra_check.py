"""
GPT Astra가 제시한 '강한 52주 신고가 돌파' 조건 검증

진입 (신호일 종가 기준, 다음날 시가 매수)
 1) 종가 > 직전 252일 고가            2) 60일선 / 120일선 - 1 > 0      3) 120일선 / 240일선 - 1 > 0
 4) 60일선 20일 변화율 > 0            5) 거래량 / 직전 20일 평균 >= 1.3  6) 20일선 이격 <= 20%
 7) 자료 요건 충족 종목 중 20일선 위 비중 >= 60%     8) 전종목 60일선 위 비중 >= 45%
 9) 20일선 10일 변화율 > 0            10) 14일 RSI(단순 평균) <= 70
 11) 120일 상대강도 백분위 >= 80%     12) 당일 등락률 >= 7%             13) 직전 20일 고저폭 / 전일 종가 >= 14%
 공통: 253거래일 종가 확보, 최근 20일 정상 거래(거래량 > 0), 20일 거래량 중앙값 >= 1만 주, 종가 >= 1,000원,
       최근 253일 안에 하루 45% 넘는 가격 변화가 있으면 제외
매도: 매수일을 1일째로 세어 90번째 거래일 종가까지 보유, 다음 거래일 시가에 전량 매도. 손절 없음. 왕복 비용 0.3%

실행: python astra_check.py   /   MARKET=us python astra_check.py (미국에 그대로 적용)
"""
import os

import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
import vcp_test as V
from ath_low_gap import SG_STOCKS

HOLD = 90
COST = 0.003
BASE = dict(vol_x=1.3, gap20=0.20, breadth20=0.60, breadth60=0.45, rsi=70, rs=0.80, day=0.07, range20=0.14)


def prepare():
    p, P, out, universe, dates = B.load_all()
    c, h, l, v = p["close"], p["high"], p["low"], p["volume"]
    for n in [60, 120, 240]:
        p[f"ma{n}"] = P.roll(c, n)
    p["hh252"] = P.shift(P.roll(h, 252, "max"), 1)
    p["ma60_20"] = P.shift(p["ma60"], 20)
    p["ma20_10"] = P.shift(p["ma20"], 10)
    p["range20p"] = (P.shift(P.roll(h, 20, "max"), 1) - P.shift(P.roll(l, 20, "min"), 1)) / p["prev_close"]
    common = ((P.pos >= 252) & (P.roll((v > 0).astype(float), 20, "min") == 1)
              & (P.roll(v, 20, "median") >= 10000) & (c >= S.MIN_PRICE)
              & (P.roll((p["ret1"].abs() > 0.45).astype(float), 253, "max") == 0)).fillna(False)
    p["common"] = common
    # 시장 지표: 자료 요건 충족 종목 기준 20일선 위 비중, 전종목 60일선 위 비중, 120일 상대강도 백분위
    p["above20"] = np.where(common, (c > p["ma20"]).astype(float), np.nan)
    p["above60"] = np.where(p["ma60"].notna(), (c > p["ma60"]).astype(float), np.nan)
    p["breadth20"] = p["date"].map(p.groupby("date")["above20"].mean())
    p["breadth60"] = p["date"].map(p.groupby("date")["above60"].mean())
    p["ret120"] = np.where(common, c / P.shift(c, 120) - 1, np.nan)
    p["rs120"] = p.groupby("date")["ret120"].rank(pct=True)
    return p, P, out, universe, dates


def signal(p, th=BASE, drop=None):
    c = p["close"]
    conds = {
        "52주 신고가": c > p["hh252"],
        "60>120일선": p["ma60"] > p["ma120"],
        "120>240일선": p["ma120"] > p["ma240"],
        "60일선 상승": p["ma60"] > p["ma60_20"],
        "거래량 배수": p["volume"] / p["vma20"] >= th["vol_x"],
        "20일선 이격": c / p["ma20"] - 1 <= th["gap20"],
        "20일선 위 비중": p["breadth20"] >= th["breadth20"],
        "60일선 위 비중": p["breadth60"] >= th["breadth60"],
        "20일선 상승": p["ma20"] > p["ma20_10"],
        "RSI": p["rsi"] <= th["rsi"],
        "상대강도": p["rs120"] >= th["rs"],
        "당일 등락률": p["ret1"] >= th["day"],
        "20일 고저폭": p["range20p"] >= th["range20"],
    }
    m = p["common"].copy()
    for k, v in conds.items():
        if k != drop:
            m &= v.fillna(False)
    return m.to_numpy()


def trades(p, P, sig, dedupe=False):
    """다음날 시가 매수(1일째) → 90일째 종가까지 보유 → 91일째 시가 매도. 91일째 자료가 있는 신호만."""
    rows = np.where(sig & (P.left >= HOLD + 1))[0]
    if dedupe:   # 같은 종목이 보유 중(90일 안)에 다시 신호 나면 제외
        keep, last = [], {}
        for r, code, d in zip(rows, p["code"].to_numpy()[rows], p["date_idx"].to_numpy()[rows]):
            if code in last and d - last[code] <= HOLD:
                continue
            last[code] = d
            keep.append(r)
        rows = np.array(keep, dtype=int)
    o = p["open"].to_numpy()
    ret = o[rows + 1 + HOLD] / o[rows + 1] - 1 - COST
    # 같은 기간 그 종목 시장 지수(코스피·코스닥 / 나스닥·NYSE) 수익률
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    d0 = p["date"].to_numpy()[rows + 1]
    d1 = p["date"].to_numpy()[rows + 1 + HOLD]
    mk = pd.Series(p["market"].to_numpy()[rows]).fillna(S.BENCH).to_numpy()   # 시장 정보가 없으면 대표 지수로
    mret = np.array([idx[m_].asof(b) / idx[m_].asof(a) - 1 for m_, a, b in zip(mk, d0, d1)])
    return pd.DataFrame({"row": rows, "date": p["date"].to_numpy()[rows], "code": p["code"].to_numpy()[rows],
                         "ret": ret, "mkt": mret, "excess": ret - mret})


def stats(t):
    if len(t) == 0:
        return "0건"
    r = np.sort(t["ret"].to_numpy())
    return (f"{len(t)}건, 평균 {t['ret'].mean():+.1%}, 중간값 {t['ret'].median():+.1%}, 이익 {(t['ret'] > 0).mean():.0%}, "
            f"하위10% {r[:max(1, len(r) // 10)].mean():+.1%}, 최악 {r[0]:+.1%}, 시장 {t['mkt'].mean():+.1%}, 초과 {t['excess'].mean():+.1%}")


def main():
    p, P, out, universe, dates = prepare()
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    name_of = names.set_index("code")["name"]
    print(f"[{S.MARKET.upper()}] 1) 조건 그대로 재현 (신호 다음날 시가 매수, 90일 보유, 비용 0.3%)")
    t = trades(p, P, signal(p))
    t["year"] = t["date"].dt.year
    print("   전체:", stats(t))
    td = trades(p, P, signal(p), dedupe=True)
    print("   보유 중 같은 종목 재신호 제외:", stats(td))
    print("   2016~2022:", stats(t[t["date"] < "2023-01-01"]))
    print("   2023~2026:", stats(t[t["date"] >= "2023-01-01"]))
    print("   2024년 이후:", stats(t[t["date"] >= "2024-01-01"]))
    print("\n   연도별:")
    for y_, g in t.groupby("year"):
        print(f"     {y_}: {stats(g)}")

    print("\n2) 소수 대박 의존도")
    s = t.sort_values("ret", ascending=False)
    for k in [0, 1, 3, 5, 10]:
        print(f"   상위 {k}건 제외: 평균 {s['ret'].iloc[k:].mean():+.1%}, 중간값 {s['ret'].iloc[k:].median():+.1%}")
    top = s.head(8).copy()
    top["name"] = top["code"].map(name_of)
    print("   상위 8건:", ", ".join(f"{n}({d.date()}) {r:+.0%}" for n, d, r in zip(top["name"], top["date"], top["ret"])))
    sg = t["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"]))
    print(f"   SG 주가조작 8종목 포함 {int(sg.sum())}건 → 제외하면: {stats(t[~sg])}")

    print("\n3) 비교 기준 (같은 90일 보유)")
    c = p["close"]
    base52 = (p["common"] & (c > p["hh252"])).to_numpy()
    print("   52주 신고가 돌파만:", stats(trades(p, P, base52, dedupe=True)))
    print("   52주 신고가 + 당일 +7% 이상:", stats(trades(p, P, base52 & (p["ret1"] >= 0.07).to_numpy(), dedupe=True)))

    print("\n4) 조건 하나씩 빼기 (빼도 결과가 비슷하면 그 조건은 효과가 작음)")
    for drop in ["60>120일선", "120>240일선", "60일선 상승", "거래량 배수", "20일선 이격", "20일선 위 비중", "60일선 위 비중",
                 "20일선 상승", "RSI", "상대강도", "당일 등락률", "20일 고저폭"]:
        print(f"   '{drop}' 빼면: {stats(trades(p, P, signal(p, drop=drop)))}")

    print("\n5) 기준값 민감도 (하나씩 조금 바꾸기)")
    tweaks = {"vol_x": [1.2, 1.5], "gap20": [0.15, 0.25], "breadth20": [0.55, 0.65], "breadth60": [0.40, 0.50],
              "rsi": [65, 75], "rs": [0.75, 0.85], "day": [0.06, 0.08], "range20": [0.12, 0.16]}
    for k, vals in tweaks.items():
        outs = []
        for v in vals:
            th = dict(BASE, **{k: v})
            tt = trades(p, P, signal(p, th))
            outs.append(f"{v}: {len(tt)}건 평균 {tt['ret'].mean():+.1%} (2016~22 {tt[tt['date'] < '2023-01-01']['ret'].mean():+.1%})")
        print(f"   {k} (기본 {BASE[k]}) → " + " | ".join(outs))

    print("\n6) 계좌 시뮬레이션 (최대 10종목, 종목당 1/10, 같은 날엔 거래대금 큰 순, 90일째 종가 청산)")
    r = td["row"].to_numpy()
    m = B.path_matrix(p, P, r)
    ret, hold, value = B.run_exit(m, [(1, dict(time=HOLD))])
    tt = pd.DataFrame({"ret": ret - (COST - S.COST), "hold": hold, "entry_idx": m["date_idx"][:, 0],
                       "tv20": p["tv20"].to_numpy()[r], "row_key": np.arange(len(r))})
    curve = B.portfolio(tt, dates, [value[k] for k in range(len(r))])
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    bench = idx[S.BENCH].reindex(curve.index).ffill()
    for label, seg, bs in [("전체", curve, bench), ("2016~22", curve[curve.index < "2023-01-01"], bench[bench.index < "2023-01-01"]),
                           ("2023~26", curve[curve.index >= "2023-01-01"], bench[bench.index >= "2023-01-01"])]:
        cs, bc = B.curve_stats(seg), B.curve_stats(bs)
        print(f"   {label}: 연평균 {cs['연평균수익률']:+.1%}, 최대낙폭 {cs['최대낙폭']:.0%}, 샤프 {cs['샤프지수']:.2f} | "
              f"{S.BENCH} 연평균 {bc['연평균수익률']:+.1%}, 최대낙폭 {bc['최대낙폭']:.0%}")
    print(f"   평균 투자 비중 {V.avg_exposure(tt, len(dates)):.0%}")
    t.to_csv(os.path.join(S.RESULT_DIR, "astra_trades.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
