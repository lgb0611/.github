"""
역사적 신고가 돌파 + 손절 -7% + 25일선/60일선 분할 매도 전략 검증

규칙
- 매수: 종가가 역사적 신고가(데이터 내 10년) 돌파 → 다음날 시가 매수
- 손절: 매수가 대비 -7% 도달 시 전량 매도 (장중 저가 기준, 시가가 이미 아래면 시가)
- 매도: 종가 25일선 이탈 시 50%, 60일선 이탈 시 나머지 50% (각각 다음날 시가)
- 최대 보유 250거래일(약 1년)
- 성공(승률): 매수 후 20거래일 안에 고가 +15% 이상 (고정 기준)

비교
- 상승장 필터(지수 60일선 위) 유무, 손절 유무, 4부 최종 전략(+15% 익절 / 20일 청산)

실행: python ath_ma_exit.py   (collect_data.py를 먼저 실행해야 함)
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
STOP_RET = -0.07 - S.COST + 1e-6   # 손절로 끝난 거래의 수익률(-7% - 비용), 소수점 오차 여유
B.H = 250   # 60일선 이탈까지 오래 들고 갈 수 있으므로 최대 보유 기간을 1년으로

USER_RULE = [(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))]
VARIANTS = {
    "① 요청 전략 (손절 -7%, 25일선 50% / 60일선 50%)": (False, USER_RULE),
    "② 요청 전략 + 상승장만": (True, USER_RULE),
    "③ 손절 없이 25일선 50% / 60일선 50%": (False, [(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))]),
    "④ 4부 최종 전략 (상승장만, +15% 익절 / 20일 청산)": (True, [(1, dict(tp=0.15, time=20))]),
}


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터 준비 중...")
    p, P, out, universe, dates = B.load_all()
    c = p["close"]
    sig = ((c > p["hh_all"]) & (P.pos >= 500)).fillna(False)
    recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
    sig = (sig & (recent == 0)).to_numpy() & universe
    bull = p["bull"].to_numpy()
    success = out["success"].to_numpy()
    split = pd.Timestamp(SPLIT_DATE)

    print("2) 전략별 거래 결과 및 계좌 시뮬레이션 (최대 10종목, 거래대금 큰 순)...")
    rows, curves, trades_all = [], {}, {}
    for name, (need_bull, legs) in VARIANTS.items():
        r = np.where(sig & bull)[0] if need_bull else np.where(sig)[0]
        m = B.path_matrix(p, P, r)
        ret, hold, value = B.run_exit(m, legs)
        t = pd.DataFrame({"row": r, "date": p["date"].to_numpy()[r], "code": p["code"].to_numpy()[r],
                          "ret": ret, "hold": hold, "success": success[r],
                          "entry_idx": m["date_idx"][:, 0], "tv20": p["tv20"].to_numpy()[r],
                          "row_key": np.arange(len(r))})
        t["early"] = t["date"] < split
        trades_all[name] = t
        curve = B.portfolio(t, dates, [value[i] for i in range(len(t))])
        curves[name] = curve
        for label, part, cpart in [("발견 2016~22", t[t["early"]], curve[curve.index < split]),
                                   ("확인 2023~26", t[~t["early"]], curve[curve.index >= split])]:
            cs = B.curve_stats(cpart)
            win, loss = part["ret"][part["ret"] > 0], part["ret"][part["ret"] <= 0]
            rows.append({
                "전략": name, "기간": label, "거래수": len(part),
                "승률(20일 +15%)": part["success"].mean(),
                "거래당 평균": part["ret"].mean(), "수익 난 비율": (part["ret"] > 0).mean(),
                "평균 이익": win.mean(), "평균 손실": loss.mean(),
                "-7% 이상 손실 비율": (part["ret"] <= STOP_RET).mean(),
                "평균 보유일": part["hold"].mean(),
                "계좌 연평균": cs["연평균수익률"], "계좌 최대낙폭": cs["최대낙폭"], "샤프": cs["샤프지수"],
            })
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULT_DIR, "ath_ma_exit.csv"), index=False, encoding="utf-8-sig")

    show = res.copy()
    for col in ["승률(20일 +15%)", "수익 난 비율", "-7% 이상 손실 비율"]:
        show[col] = show[col].map("{:.1%}".format)
    for col in ["거래당 평균", "평균 이익", "평균 손실", "계좌 연평균", "계좌 최대낙폭"]:
        show[col] = show[col].map("{:+.1%}".format)
    show["평균 보유일"] = show["평균 보유일"].map("{:.0f}일".format)
    show["샤프"] = show["샤프"].map("{:.2f}".format)
    pd.set_option("display.width", 300)
    pd.set_option("display.unicode.east_asian_width", True)
    print(show.to_string(index=False))

    # 연도별 계좌 수익률
    yearly = pd.DataFrame({n: c.resample("YE").last().pct_change() for n, c in curves.items()})
    first = {n: c.resample("YE").last().iloc[0] / c.iloc[0] - 1 for n, c in curves.items()}
    for n in yearly.columns:
        yearly.loc[yearly.index[0], n] = first[n] if pd.isna(yearly[n].iloc[0]) else yearly[n].iloc[0]
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    yearly["코스피"] = idx["KOSPI"].resample("YE").last().pct_change().reindex(yearly.index)
    yearly.index = yearly.index.year
    yearly.columns = ["①", "②", "③", "④", "코스피"]
    print("\n연도별 계좌 수익률 (2026년은 9월까지)")
    print(yearly.map(lambda v: f"{v:+.1%}" if pd.notna(v) else "-").to_string())

    # 손익 분포 (① 기준)
    t1 = trades_all[list(VARIANTS)[0]]
    bins = [-1, STOP_RET, -0.03, 0, 0.1, 0.3, 1, 100]
    labels = ["-7% 손절", "-7~-3%", "-3~0%", "0~10%", "10~30%", "30~100%", "100% 이상"]
    dist = pd.cut(t1["ret"], bins, labels=labels).value_counts(normalize=True).reindex(labels)
    print("\n① 거래 손익 분포")
    print(dist.map("{:.1%}".format).to_string())

    # 차트
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    for (name, cv), lab in zip(curves.items(), ["1", "2", "3", "4"]):
        axes[0].plot(cv / cv.iloc[0], label=f"#{lab}")
    k = idx["KOSPI"].reindex(curves[list(VARIANTS)[0]].index).ffill()
    axes[0].plot(k / k.iloc[0], label="KOSPI", color="black", linestyle="--")
    axes[0].axvline(split, color="k", alpha=0.3)
    axes[0].set_yscale("log")
    axes[0].set_title("Account simulation (max 10 positions, log scale)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].hist(t1["ret"].clip(-0.2, 1.0) * 100, bins=60, color="tab:blue")
    axes[1].axvline(0, color="k", lw=0.8)
    axes[1].set_title("#1 trade return distribution (%, clipped at 100)")
    axes[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "ath_ma_exit.png"), dpi=110)
    print("\n차트 범례: " + ", ".join(f"#{i + 1}={n}" for i, n in enumerate(VARIANTS)))


if __name__ == "__main__":
    main()
