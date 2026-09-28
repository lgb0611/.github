"""
거래대금 순위 + 신고가 돌파: '20일 안에 +15%'를 가장 자주 달성하는 조건 찾기

- 거래대금 순위: 신호 당일 (종가 × 거래량) 전 종목 순위 (1위 = 가장 많음)
- 신고가: 20일 / 52주 / 104주 / 역사적 신고가 돌파 (종가 기준, 20일 안 중복 제외)
- 순위 조건: 상위 10 / 20 / 30 / 50 / 100 / 200위 / 제한 없음, 상승장 필터 유무
- 평가: 승률 = 매수 후 20거래일 안에 고가가 +15% 이상 오른 비율 (성공 기준)
        손익 = 매도 규칙 "25일선 이탈 시 50%, 60일선 이탈 시 50%" (손절 없음, 최대 1년 보유)로 계산한
               거래당 평균·중간값, 계좌 시뮬레이션(최대 10종목)
- 조건 고르기는 2016~22(발견), 검증은 2023~26(확인)과 미국 데이터(MARKET=us)

실행: python tv_rank_test.py   /   MARKET=us python tv_rank_test.py
"""
import itertools
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
RANKS = [10, 20, 30, 50, 100, 200, None]
MIN_TRADES = 100
B.H = 250
EXIT = [(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))]   # 25일선 이탈 50%, 60일선 이탈 50%


def main():
    os.makedirs(S.RESULT_DIR, exist_ok=True)
    print("1) 데이터 준비 중...")
    p, P, out, universe, dates = B.load_all()
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    not_sg = ~p["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"])).to_numpy()
    c = p["close"]
    tv_rank = (c * p["volume"]).groupby(p["date"]).rank(ascending=False, method="first").to_numpy()
    bull = p["bull"].to_numpy()
    success = out["success"].to_numpy()

    breakouts = {
        "20일 신고가": c > p["hh20"],
        "52주 신고가": c > p["hh250"],
        "104주 신고가": c > P.shift(P.roll(p["high"], 520, "max"), 1),
        "역사적 신고가": (c > p["hh_all"]) & (P.pos >= 500),
    }
    rows = []
    for bname, cond in breakouts.items():
        sig = cond.fillna(False)
        recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        pool = np.where((sig & (recent == 0)).to_numpy() & universe & not_sg)[0]
        print(f"2) [{bname}] 신호 {len(pool):,}건 계산 중...")
        m = B.path_matrix(p, P, pool)
        ret, hold, value = B.run_exit(m, EXIT)
        entry_idx = m["date_idx"][:, 0]
        del m
        early = p["date"].to_numpy()[pool] < np.datetime64(SPLIT)
        rank = tv_rank[pool]
        for top, use_bull in itertools.product(RANKS, [False, True]):
            vm = (rank <= top if top else np.ones(len(pool), bool)) & (bull[pool] if use_bull else True)
            row = {"신고가": bname, "거래대금 순위": f"상위 {top}위" if top else "제한 없음",
                   "상승장만": "예" if use_bull else "아니오"}
            for label, pm in [("발견", early), ("확인", ~early)]:
                sel = vm & pm
                row[f"{label}_거래수"] = int(sel.sum())
                row[f"{label}_승률"] = success[pool][sel].mean() if sel.any() else np.nan
                row[f"{label}_거래평균"] = ret[sel].mean() if sel.any() else np.nan
                row[f"{label}_거래중간값"] = np.median(ret[sel]) if sel.any() else np.nan
                row[f"{label}_수익비율"] = (ret[sel] > 0).mean() if sel.any() else np.nan
                row[f"{label}_보유일"] = hold[sel].mean() if sel.any() else np.nan
            if vm.sum() >= 5:
                t = pd.DataFrame({"date": p["date"].to_numpy()[pool][vm], "ret": ret[vm], "hold": hold[vm],
                                  "entry_idx": entry_idx[vm], "tv20": -rank[vm],   # 같은 날엔 거래대금 순위 높은 종목부터
                                  "row_key": np.arange(vm.sum())})
                curve = B.portfolio(t, dates, [value[k] for k in np.where(vm)[0]])
                for label, before in [("발견", True), ("확인", False)]:
                    cs = V.seg_stats(curve, before)
                    row[f"{label}_연평균"], row[f"{label}_최대낙폭"] = cs["연평균수익률"], cs["최대낙폭"]
                row["투자비중"] = V.avg_exposure(t, len(dates))
            rows.append(row)

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(S.RESULT_DIR, "tv_rank_test.csv"), index=False, encoding="utf-8-sig")

    base_all = universe & not_sg
    early_all = p["date"].to_numpy() < np.datetime64(SPLIT)
    print(f"\n[{S.MARKET.upper()}] 참고: 조건 없이 아무 종목·아무 날 승률 "
          f"{success[base_all & early_all].mean():.0%} → {success[base_all & ~early_all].mean():.0%}")

    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda d, a, b, fmt: d[a].map(lambda v: f(v, fmt)) + " → " + d[b].map(lambda v: f(v, fmt))

    def show(d):
        return pd.DataFrame({
            "신고가": d["신고가"], "거래대금": d["거래대금 순위"], "상승장": d["상승장만"],
            "거래수": arrow(d, "발견_거래수", "확인_거래수", "{:,.0f}"),
            "승률": arrow(d, "발견_승률", "확인_승률", "{:.0%}"),
            "거래당 평균": arrow(d, "발견_거래평균", "확인_거래평균", "{:+.1%}"),
            "거래당 중간값": arrow(d, "발견_거래중간값", "확인_거래중간값", "{:+.1%}"),
            "수익 난 비율": arrow(d, "발견_수익비율", "확인_수익비율", "{:.0%}"),
            "보유일": arrow(d, "발견_보유일", "확인_보유일", "{:.0f}"),
            "계좌 연평균": arrow(d, "발견_연평균", "확인_연평균", "{:+.1%}"),
            "최대낙폭": arrow(d, "발견_최대낙폭", "확인_최대낙폭", "{:.0%}"),
            "투자비중": d["투자비중"].map(lambda v: f(v, "{:.0%}")),
        })

    print("\n매도: 25일선 이탈 50% / 60일선 이탈 50% (손절 없음)")
    print("\n[상승장 필터 없음] 신고가 × 거래대금 순위 (발견 2016~22 → 확인 2023~26)")
    print(show(res[res["상승장만"] == "아니오"]).to_string(index=False))
    ok = res[res["발견_거래수"] >= MIN_TRADES].sort_values("발견_승률", ascending=False)
    print(f"\n[발견 기간 승률 상위 10개 조합] (발견 기간 거래 {MIN_TRADES}건 이상)")
    print(show(ok.head(10)).to_string(index=False))

    # 차트: 신고가별, 거래대금 순위별 승률 (상승장 필터 없음)
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    xlab = [str(r) if r else "all" for r in RANKS]
    for ax, label in zip(axes, ["발견", "확인"]):
        for k, bname in enumerate(breakouts):
            d = res[(res["신고가"] == bname) & (res["상승장만"] == "아니오")]
            ax.plot(xlab, d[f"{label}_승률"] * 100, marker="o", label=["20-day", "52-week", "104-week", "All-time"][k])
        ax.set_title(f"[{S.MARKET.upper()}] Win rate (+15% within 20d) by trading-value rank, "
                     f"{'2016-22' if label == '발견' else '2023-26'}")
        ax.set_xlabel("Trading value rank on signal day (top N)")
        ax.set_ylabel("Win rate (%)")
        ax.legend()
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(S.RESULT_DIR, "tv_rank_test.png"), dpi=110)


if __name__ == "__main__":
    main()
