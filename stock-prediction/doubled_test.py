"""
1년간 2배 이상 오른 종목: '빠질 때 매수' vs '신고가 돌파 매수' 비교

대상: 최근 60일 최고 종가가 1년(250거래일) 전 종가의 2배 이상인 종목 (= 1년 새 2배 이상 오른 상태)
매수 신호 (신호 다음날 시가 매수, 같은 신호는 20일 안에 중복 제외)
- 돌파: 52주 신고가 돌파 / 역사적 신고가 돌파
- 조정: 최근 60일 최고 종가 대비 -15% / -25% / -35%까지 처음 빠진 날,
        20일선 눌림(저가가 20일선 터치 후 20일선 위 마감, 20일선 상승 중), 60일선 터치
- 비교: 대상 종목을 아무 날에나 매수
평가
- 매도 규칙과 무관한 비교: 매수 후 20·60·120거래일 뒤 종가 수익률
- 기존 매도 방식 A(손절 -7% / 25일선 50% / 60일선 50%), B(+15% 익절 / 20일 청산)의 거래당 수익·계좌 시뮬레이션

실행: python doubled_test.py            (한국)
      MARKET=us python doubled_test.py  (미국)
"""
import os

import matplotlib
import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
import vcp_test as V
from ath_low_gap import SG_STOCKS

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SPLIT = V.SPLIT
HORIZONS = [20, 60, 120]
B.H = 250


def main():
    os.makedirs(S.RESULT_DIR, exist_ok=True)
    print("1) 데이터 준비 중...")
    p, P, out, universe, dates = B.load_all()
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    not_sg = ~p["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"])).to_numpy()
    c, lo = p["close"], p["low"]
    peak60 = P.roll(c, 60, "max")
    doubled = (peak60 >= 2 * P.shift(c, 250)).fillna(False)
    dd = c / peak60 - 1                                   # 최근 60일 고점 대비 하락률
    dd_prev = P.shift(dd, 1)
    ma20_up = p["ma20"] > p["ma20_5ago"]

    raw = {
        "돌파: 52주 신고가": c > p["hh250"],
        "돌파: 역사적 신고가": (c > p["hh_all"]) & (P.pos >= 500),
        "조정: 고점 대비 -15% 도달": (dd <= -0.15) & (dd_prev > -0.15),
        "조정: 고점 대비 -25% 도달": (dd <= -0.25) & (dd_prev > -0.25),
        "조정: 고점 대비 -35% 도달": (dd <= -0.35) & (dd_prev > -0.35),
        "조정: 20일선 눌림": ma20_up & (lo <= p["ma20"]) & (c > p["ma20"]),
        "조정: 60일선 터치": (lo <= p["ma60"]) & (c > p["ma60"]),
    }
    base_ok = universe & not_sg & doubled.to_numpy()
    signals = {}
    for name, cond in raw.items():
        sig = cond.fillna(False)
        recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        signals[name] = (sig & (recent == 0)).to_numpy() & base_ok
    # 비교 기준: 대상 종목을 아무 날에나 (20일마다 한 번씩 뽑아 겹침을 줄임)
    signals["(비교) 아무 날이나"] = base_ok & (P.pos % 20 == 0)

    success = out["success"].to_numpy()
    rows, curves = [], {}
    print("2) 신호별 계산 중...")
    for name, sig in signals.items():
        r = np.where(sig)[0]
        m = B.path_matrix(p, P, r)
        entry = m["open"][:, 0]
        early = p["date"].to_numpy()[r] < np.datetime64(SPLIT)
        row = {"신호": name, "발견_거래수": int(early.sum()), "확인_거래수": int((~early).sum()),
               "고점대비_중간값": np.nanmedian(dd.to_numpy()[r])}
        for h in HORIZONS:
            ok = m["valid"][:, h - 1]
            fr = np.where(ok, m["close"][:, h - 1] / entry - 1, np.nan)
            for label, pm in [("발견", early), ("확인", ~early)]:
                v = fr[pm & ok]
                row[f"{label}_{h}일_평균"] = v.mean()
                row[f"{label}_{h}일_중간값"] = np.median(v) if len(v) else np.nan
                row[f"{label}_{h}일_상승비율"] = (v > 0).mean()
        # 매수 후 20일 안에 가장 크게 빠진 폭 (중간값) = 버텨야 하는 고통
        worst = np.nanmin(np.where(m["valid"][:, :20], m["low"][:, :20], np.nan), axis=1) / entry - 1
        row["20일내_최대하락_중간값"] = np.nanmedian(worst)
        for label, pm in [("발견", early), ("확인", ~early)]:
            row[f"{label}_승률"] = success[r][pm].mean()
        for ex, legs in V.EXITS.items():
            ret, hold, value = B.run_exit(m, legs)
            t = pd.DataFrame({"date": p["date"].to_numpy()[r], "ret": ret, "hold": hold,
                              "entry_idx": m["date_idx"][:, 0], "tv20": p["tv20"].to_numpy()[r],
                              "row_key": np.arange(len(r))})
            curve = B.portfolio(t, dates, [value[k] for k in range(len(r))])
            curves[(name, ex)] = curve
            for label, before in [("발견", True), ("확인", False)]:
                part = t[t["date"] < SPLIT] if before else t[t["date"] >= SPLIT]
                cs = V.seg_stats(curve, before)
                row[f"{ex}_{label}_거래평균"] = part["ret"].mean()
                row[f"{ex}_{label}_연평균"] = cs["연평균수익률"]
                row[f"{ex}_{label}_최대낙폭"] = cs["최대낙폭"]
        rows.append(row)
        del m

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(S.RESULT_DIR, "doubled_test.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda a, b, fmt: res[a].map(lambda v: f(v, fmt)) + " → " + res[b].map(lambda v: f(v, fmt))

    print(f"\n[{S.MARKET.upper()}] 매수 후 N일 뒤 수익률 (평균 / 중간값, 표기: 발견 2016~22 → 확인 2023~26)")
    t1 = pd.DataFrame({"신호": res["신호"], "거래수": arrow("발견_거래수", "확인_거래수", "{:,.0f}"),
                       "매수시 고점대비": res["고점대비_중간값"].map(lambda v: f(v, "{:.0%}"))})
    for h in HORIZONS:
        t1[f"{h}일 평균"] = arrow(f"발견_{h}일_평균", f"확인_{h}일_평균", "{:+.1%}")
        t1[f"{h}일 중간값"] = arrow(f"발견_{h}일_중간값", f"확인_{h}일_중간값", "{:+.1%}")
    print(t1.to_string(index=False))

    t2 = pd.DataFrame({"신호": res["신호"],
                       "60일 뒤 오른 비율": arrow("발견_60일_상승비율", "확인_60일_상승비율", "{:.0%}"),
                       "20일내 최대하락(중간값)": res["20일내_최대하락_중간값"].map(lambda v: f(v, "{:.1%}")),
                       "승률(20일 +15%)": arrow("발견_승률", "확인_승률", "{:.0%}")})
    for ex in V.EXITS:
        t2[f"{ex} 거래평균"] = arrow(f"{ex}_발견_거래평균", f"{ex}_확인_거래평균", "{:+.1%}")
        t2[f"{ex} 계좌 연평균"] = arrow(f"{ex}_발견_연평균", f"{ex}_확인_연평균", "{:+.1%}")
        t2[f"{ex} 최대낙폭"] = arrow(f"{ex}_발견_최대낙폭", f"{ex}_확인_최대낙폭", "{:.0%}")
    print("\n매도 방식 A(손절-7%/25·60일선), B(+15% 익절/20일)로 운용했을 때 (계좌: 최대 10종목)")
    print(t2.to_string(index=False))

    # 차트: 신호별 60일 뒤 평균 수익률 (두 기간)
    fig, axes = plt.subplots(1, 2, figsize=(17, 6))
    labels = ["52w high", "ATH", "-15% dip", "-25% dip", "-35% dip", "MA20 pullback", "MA60 touch", "Any day"]
    x = np.arange(len(res))
    for ax, h in zip(axes, [60, 120]):
        ax.bar(x - 0.2, res[f"발견_{h}일_평균"] * 100, 0.4, label="2016-22", alpha=0.6)
        ax.bar(x + 0.2, res[f"확인_{h}일_평균"] * 100, 0.4, label="2023-26")
        ax.set_xticks(x, labels[:len(res)], rotation=30)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(f"[{S.MARKET.upper()}] Stocks up 2x+ in a year: avg return {h} days after entry (%)")
        ax.legend()
        ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(os.path.join(S.RESULT_DIR, "doubled_test.png"), dpi=110)


if __name__ == "__main__":
    main()
