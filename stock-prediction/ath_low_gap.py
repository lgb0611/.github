"""
역사적 신고가 돌파 + '20일선과 가까울 때만' 매수

5부에서 역사적 신고가 돌파일의 주가는 25일선보다 평균 25% 위에 있어서
-7% 손절이 이평선 매도보다 거의 항상 먼저 걸렸습니다.
그래서 20일선 이격도(종가 / 20일선 - 1)가 작은 상태에서 돌파할 때만 사면 어떤지 시험합니다.

비교
- 20일선 이격 상한: 5% / 10% / 15% / 20% / 제한 없음
- 매도: A) 손절 -7%, 25일선 이탈 50%, 60일선 이탈 50%  (최대 1년 보유)
        B) +15% 익절 / 20일째 청산 / 손절 없음 (4부 최종)
- 상승장 필터(지수 60일선 위) 유무

실행: python ath_low_gap.py   (collect_data.py를 먼저 실행해야 함)
"""
import os

import matplotlib
import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULT_DIR = S.RESULT_DIR
SPLIT_DATE = S.SPLIT_DATE
B.H = 250
STOP_RET = -0.07 - S.COST + 1e-6
SG_STOCKS = ["삼천리", "대성홀딩스", "선광", "다우데이타", "서울가스", "세방", "하림지주", "다올투자증권"]
GAPS = [0.05, 0.10, 0.15, 0.20, np.inf]
EXITS = {
    "A) 손절-7%/25일선/60일선": [(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))],
    "B) +15%익절/20일청산": [(1, dict(tp=0.15, time=20))],
}


def gap_label(g):
    return "제한 없음" if np.isinf(g) else f"{g:.0%} 이하"


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터 준비 중...")
    p, P, out, universe, dates = B.load_all()
    c = p["close"]
    sig = ((c > p["hh_all"]) & (P.pos >= 500)).fillna(False)
    recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
    sig = (sig & (recent == 0)).to_numpy() & universe
    gap = (c / p["ma20"] - 1).to_numpy()
    bull = p["bull"].to_numpy()
    success = out["success"].to_numpy()
    split = pd.Timestamp(SPLIT_DATE)

    g_all = gap[sig]
    print(f"   역사적 신고가 돌파 신호 {sig.sum():,}건의 20일선 이격도: "
          f"5% 이하 {np.mean(g_all <= .05):.0%}, 10% 이하 {np.mean(g_all <= .10):.0%}, "
          f"15% 이하 {np.mean(g_all <= .15):.0%}, 20% 이하 {np.mean(g_all <= .20):.0%}, 중간값 {np.median(g_all):.1%}")

    print("2) 조합별 거래 결과 + 계좌 시뮬레이션 (최대 10종목, 거래대금 큰 순)...")
    rows, curves = [], {}
    for use_bull in [False, True]:
        for g in GAPS:
            mask = sig & (gap <= g) & (bull if use_bull else True)
            r = np.where(mask)[0]
            m = B.path_matrix(p, P, r)
            for ename, legs in EXITS.items():
                ret, hold, value = B.run_exit(m, legs)
                t = pd.DataFrame({"date": p["date"].to_numpy()[r], "ret": ret, "hold": hold,
                                  "success": success[r], "entry_idx": m["date_idx"][:, 0],
                                  "tv20": p["tv20"].to_numpy()[r], "row_key": np.arange(len(r))})
                curve = B.portfolio(t, dates, [value[i] for i in range(len(t))])
                key = (use_bull, g, ename)
                curves[key] = curve
                row = {"상승장만": "예" if use_bull else "아니오", "20일선 이격": gap_label(g), "매도": ename}
                for label, part, cp in [("발견", t[t["date"] < split], curve[curve.index < split]),
                                        ("확인", t[t["date"] >= split], curve[curve.index >= split])]:
                    cs = B.curve_stats(cp)
                    row.update({
                        f"{label}_거래수": len(part), f"{label}_승률": part["success"].mean(),
                        f"{label}_거래평균": part["ret"].mean(), f"{label}_수익비율": (part["ret"] > 0).mean(),
                        f"{label}_손절비율": (part["ret"] <= STOP_RET).mean(),
                        f"{label}_보유일": part["hold"].mean(),
                        f"{label}_연평균": cs["연평균수익률"], f"{label}_최대낙폭": cs["최대낙폭"],
                        f"{label}_샤프": cs["샤프지수"],
                    })
                rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULT_DIR, "ath_low_gap.csv"), index=False, encoding="utf-8-sig")

    def two(a, b, f):
        return res[a].map(f.format) + " → " + res[b].map(f.format)

    show = res[["상승장만", "20일선 이격", "매도"]].copy()
    show["거래수"] = two("발견_거래수", "확인_거래수", "{:,.0f}")
    show["승률"] = two("발견_승률", "확인_승률", "{:.0%}")
    show["거래평균"] = two("발견_거래평균", "확인_거래평균", "{:+.1%}")
    show["수익비율"] = two("발견_수익비율", "확인_수익비율", "{:.0%}")
    show["손절비율"] = two("발견_손절비율", "확인_손절비율", "{:.0%}")
    show["계좌 연평균"] = two("발견_연평균", "확인_연평균", "{:+.1%}")
    show["최대낙폭"] = two("발견_최대낙폭", "확인_최대낙폭", "{:.0%}")
    show["샤프"] = two("발견_샤프", "확인_샤프", "{:.2f}")
    pd.set_option("display.width", 300)
    pd.set_option("display.unicode.east_asian_width", True)
    for ename in EXITS:
        print(f"\n[{ename}]  표기: 발견 2016~22 → 확인 2023~26")
        print(show[show["매도"] == ename].drop(columns="매도").to_string(index=False))

    # 2023년 4월 SG증권발 주가조작 사태 종목: 2022년에 조작으로 오른 주가가 결과를 크게 부풀림
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    sg_codes = set(names.loc[names["name"].isin(SG_STOCKS), "code"])
    not_sg = ~p["code"].isin(sg_codes).to_numpy()
    print(f"\n[주가조작 종목 제외 검증] SG 사태 {len(sg_codes)}종목 ({', '.join(SG_STOCKS)}) 제외, 발견 → 확인")
    checks = [("A", 0.20, False), ("A", 0.20, True), ("A", 0.15, False), ("A", 0.10, False),
              ("A", np.inf, False), ("B", np.inf, True)]
    for ex_key, g, use_bull in checks:
        ename = [e for e in EXITS if e.startswith(ex_key)][0]
        for exclude in [False, True]:
            mask = sig & (gap <= g) & (bull if use_bull else True) & (not_sg if exclude else True)
            r = np.where(mask)[0]
            m = B.path_matrix(p, P, r)
            ret, hold, value = B.run_exit(m, EXITS[ename])
            t = pd.DataFrame({"ret": ret, "hold": hold, "entry_idx": m["date_idx"][:, 0],
                              "tv20": p["tv20"].to_numpy()[r], "row_key": np.arange(len(r))})
            cv = B.portfolio(t, dates, [value[i] for i in range(len(t))])
            a, b = B.curve_stats(cv[cv.index < split]), B.curve_stats(cv[cv.index >= split])
            print(f"   {ename[:2]} 이격 {gap_label(g):7s} {'상승장만' if use_bull else '        '} "
                  f"{'SG 제외' if exclude else '전체   '}: 연평균 {a['연평균수익률']:+.1%} → {b['연평균수익률']:+.1%}, "
                  f"샤프 {a['샤프지수']:.2f} → {b['샤프지수']:.2f}")

    # 차트: 매도 A, 상승장 필터 없음 기준 이격 상한별 계좌 곡선 + 이격별 거래평균
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    ename = list(EXITS)[0]
    for g in GAPS:
        cv = curves[(False, g, ename)]
        axes[0].plot(cv / cv.iloc[0], label="no limit" if np.isinf(g) else f"gap <= {g:.0%}")
    axes[0].axvline(split, color="k", alpha=0.3)
    axes[0].set_yscale("log")
    axes[0].set_title("Exit A (stop -7%, MA25/MA60): account by MA20 gap limit")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    sub = res[(res["상승장만"] == "아니오")]
    x = np.arange(len(GAPS))
    for i, en in enumerate(EXITS):
        s = sub[sub["매도"] == en]
        axes[1].bar(x + (i - 0.5) * 0.4, s["확인_연평균"] * 100, 0.4, label=f"Exit {en[0]} (2023-26)")
        axes[1].scatter(x + (i - 0.5) * 0.4, s["발견_연평균"] * 100, color=f"C{i}", edgecolor="k",
                        zorder=3, s=40, label=f"Exit {en[0]} (2016-22)")
    axes[1].set_xticks(x, ["<=5%", "<=10%", "<=15%", "<=20%", "none"])
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].set_title("Account CAGR % (bars: 2023-26, dots: 2016-22, incl. SG stocks)")
    axes[1].legend()
    axes[1].grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "ath_low_gap.png"), dpi=110)


if __name__ == "__main__":
    main()
