"""
20거래일 이상 들고 가는 중기 매매법 찾기

1) 신호 매매 + 중기 매도: 매수 신호 4개 × 중기 매도 20개 (평균 보유 20일 이상만 후보)
2) 모멘텀 순환 매매: 20거래일마다 '최근 많이 오른' 상위 N종목을 똑같은 비중으로 보유
   (전체 종목 중 / 20일 평균 거래대금 상위 200종목 중 두 가지)

- 고르기는 한국 발견 기간(2016~22)만 사용, 한국 확인 기간(2023~26)과 미국 두 기간으로 검증
- 비용 0.25%(왕복), SG 주가조작 8종목 제외, 현재 상장 종목만(생존 편향 주의)

실행: python midterm.py && MARKET=us python midterm.py && python midterm.py summary
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
import vcp_test as V
from ath_low_gap import SG_STOCKS

B.H = 250
SPLIT = pd.Timestamp(S.SPLIT_DATE)
REBAL = 20          # 순환 매매 교체 주기 (거래일)

EXITS = {
    "40일 보유": [(1, dict(time=40))],
    "60일 보유": [(1, dict(time=60))],
    "120일 보유": [(1, dict(time=120))],
    "고점 대비 -15% 추적": [(1, dict(trail=0.15))],
    "고점 대비 -20% 추적": [(1, dict(trail=0.20))],
    "고점 대비 -25% 추적": [(1, dict(trail=0.25))],
    "고점 대비 -20% 추적 / 손절 -10%": [(1, dict(trail=0.20, sl=-0.10))],
    "20일 보유 후 고점 대비 -15% 추적": [(1, dict(trail=0.15, min_hold=20))],
    "50일선 이탈": [(1, dict(ma="ma50"))],
    "60일선 이탈": [(1, dict(ma="ma60"))],
    "60일선 이탈 / 손절 -10%": [(1, dict(ma="ma60", sl=-0.10))],
    "60일선 이탈 / 손절 -15%": [(1, dict(ma="ma60", sl=-0.15))],
    "20일 보유 후 20일선 이탈": [(1, dict(ma="ma20", min_hold=20))],
    "20일 보유 후 20일선 이탈 / 손절 -10%": [(1, dict(ma="ma20", min_hold=20, sl=-0.10))],
    "25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25")), (0.5, dict(ma="ma60"))],
    "20일 보유 후 25일선 50% / 60일선 50%": [(0.5, dict(ma="ma25", min_hold=20)), (0.5, dict(ma="ma60", min_hold=20))],
    "50% +30% 익절 + 50% 고점 대비 -20% 추적": [(0.5, dict(tp=0.30)), (0.5, dict(trail=0.20))],
    "+50% 익절 / 고점 대비 -20% 추적": [(1, dict(tp=0.50, trail=0.20))],
    "60일 보유 / 손절 -10%": [(1, dict(time=60, sl=-0.10))],
    "+30% 익절 / 60일 보유 / 손절 -10%": [(1, dict(tp=0.30, time=60, sl=-0.10))],
}


def prepare():
    p, P, out, universe, dates = B.load_all()
    p = V.add_minervini(p, P)
    if "ma50" not in B.MA_COLS:
        B.MA_COLS.append("ma50")
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    not_sg = ~p["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"])).to_numpy()
    return p, P, out, universe & not_sg, dates


def signal_part(p, P, out, ok, dates):
    c = p["close"]
    rank = (c * p["volume"]).groupby(p["date"]).rank(ascending=False, method="first").to_numpy()
    bull = p["bull"].to_numpy()
    gap = (c / p["ma20"] - 1).to_numpy()
    tt = p["trend_template"].to_numpy()

    def cooled(cond):
        cond = cond.fillna(False)
        recent = P.shift(P.roll(cond.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        return (cond & (recent == 0)).to_numpy() & ok

    ath = cooled((c > p["hh_all"]) & (P.pos >= 500))
    entries = {
        "역사적 신고가 + 상승장": ath & bull,
        "역사적 신고가 + 거래대금 상위 10위 + 상승장": ath & bull & (rank <= 10),
        "역사적 신고가 + 이격 20% 이하 + 트렌드 템플릿 + 상승장": ath & bull & (gap <= 0.20) & tt,
        "52주 신고가 + 거래대금 상위 30위 + 상승장": cooled(c > p["hh250"]) & bull & (rank <= 30),
    }
    success = out["success"].to_numpy()
    rows = []
    for ename, sig in entries.items():
        r = np.where(sig)[0]
        m = B.path_matrix(p, P, r)
        early = p["date"].to_numpy()[r] < np.datetime64(SPLIT)
        for xname, legs in EXITS.items():
            ret, hold, value = B.run_exit(m, legs)
            t = pd.DataFrame({"date": p["date"].to_numpy()[r], "ret": ret, "hold": hold,
                              "entry_idx": m["date_idx"][:, 0], "tv20": -rank[r], "row_key": np.arange(len(r))})
            curve = B.portfolio(t, dates, [value[k] for k in range(len(r))])
            row = {"방식": "신호 매매", "매수": ename, "매도": xname}
            for label, pm, before in [("발견", early, True), ("확인", ~early, False)]:
                cs = V.seg_stats(curve, before)
                row.update({f"{label}_거래수": int(pm.sum()), f"{label}_승률": success[r][pm].mean(),
                            f"{label}_거래평균": ret[pm].mean(), f"{label}_수익비율": (ret[pm] > 0).mean(),
                            f"{label}_보유일": hold[pm].mean(), f"{label}_연평균": cs["연평균수익률"],
                            f"{label}_최대낙폭": cs["최대낙폭"], f"{label}_샤프": cs["샤프지수"]})
            row["투자비중"] = V.avg_exposure(t, len(dates))
            rows.append(row)
        print(f"   [{ename}] 신호 {len(r)}건 완료")
    return rows


def rotation_part(p, ok, dates):
    """20거래일마다 점수 상위 N종목을 똑같은 비중으로 보유 (다음날 시가에 교체)."""
    piv = lambda col: p.pivot(index="date", columns="code", values=col)
    O, C = piv("open"), piv("close")
    ok_df = pd.DataFrame({"date": p["date"], "code": p["code"], "ok": ok}).pivot(
        index="date", columns="code", values="ok").fillna(False).astype(bool)
    bull = p.pivot(index="date", columns="code", values="bull").fillna(False).astype(bool)
    tt = p.pivot(index="date", columns="code", values="trend_template").fillna(False).astype(bool)
    rs = piv("rs")
    scores = {
        "12개월 모멘텀 (최근 1개월 제외)": C.shift(20) / C.shift(250) - 1,
        "6개월 수익률": C / C.shift(126) - 1,
        "상대강도(RS) 점수": rs,
        "트렌드 템플릿 종목 중 RS 순": rs.where(tt),
    }
    Cf = C.ffill()
    tv_rank = piv("tv20").rank(axis=1, ascending=False)     # 20일 평균 거래대금 순위
    idx_dates = C.index
    rebal_days = np.arange(260, len(idx_dates) - 1, REBAL)
    rows = []
    for (sname, score), n, use_bull, big in itertools.product(scores.items(), [10, 20], [False, True], [None, 200]):
        period_ret, period_date, prev = [], [], set()
        for a, b in zip(rebal_days[:-1], rebal_days[1:]):
            sc = score.iloc[a].where(ok_df.iloc[a])
            if big:                                   # 거래가 활발한 큰 종목 안에서만 고르기
                sc = sc.where(tv_rank.iloc[a] <= big)
            picks = list(sc.dropna().nlargest(n).index)
            if use_bull:
                picks = [k for k in picks if bull.iloc[a][k]]
            buy = O.iloc[a + 1].reindex(picks)
            sell = O.iloc[b + 1].reindex(picks).fillna(Cf.iloc[b].reindex(picks))
            r = (sell / buy - 1).fillna(0).clip(lower=-1)
            gross = r.sum() / n                      # 빈 자리는 현금(수익 0)
            turnover = len(set(picks) - prev) / n
            period_ret.append(gross - S.COST * turnover)
            period_date.append(idx_dates[b + 1])
            prev = set(picks)
        pr = pd.Series(period_ret, index=period_date)
        row = {"방식": "순환 매매",
               "매수": (f"거래대금 상위 {big}종목 중 " if big else "") + f"{sname} 상위 {n}종목",
               "매도": f"{REBAL}일마다 교체"
               + (" (지수 약세 시 현금)" if use_bull else "")}
        for label, seg in [("발견", pr[pr.index < SPLIT]), ("확인", pr[pr.index >= SPLIT])]:
            curve = (1 + seg).cumprod()
            years = len(seg) * REBAL / 250
            row.update({f"{label}_연평균": curve.iloc[-1] ** (1 / years) - 1,
                        f"{label}_최대낙폭": (curve / curve.cummax() - 1).min(),
                        f"{label}_샤프": seg.mean() / seg.std() * np.sqrt(250 / REBAL),
                        f"{label}_보유일": REBAL, f"{label}_거래평균": seg.mean()})
        rows.append(row)
        print(f"   [순환] {row['매수']} {row['매도']} 완료")
    return rows


def bench_row():
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    s = idx[S.BENCH].dropna()
    s = s[s.index >= pd.Timestamp("2017-01-01")]
    row = {"방식": "지수", "매수": f"{S.BENCH} 지수 보유", "매도": "-"}
    for label, seg in [("발견", s[s.index < SPLIT]), ("확인", s[s.index >= SPLIT])]:
        cs = B.curve_stats(seg)
        row.update({f"{label}_연평균": cs["연평균수익률"], f"{label}_최대낙폭": cs["최대낙폭"], f"{label}_샤프": cs["샤프지수"]})
    return row


def run_market():
    print(f"[{S.MARKET.upper()}] 1) 데이터 준비 중...")
    p, P, out, ok, dates = prepare()
    print("2) 신호 매매 + 중기 매도 계산 중...")
    rows = signal_part(p, P, out, ok, dates)
    print("3) 모멘텀 순환 매매 계산 중...")
    rows += rotation_part(p, ok, dates)
    rows.append(bench_row())
    pd.DataFrame(rows).to_csv(os.path.join(S.RESULT_DIR, "midterm.csv"), index=False, encoding="utf-8-sig")


def summary():
    kr = pd.read_csv(os.path.join(S.BASE, "results", "midterm.csv"))
    us = pd.read_csv(os.path.join(S.BASE, "results_us", "midterm.csv"))
    key = ["방식", "매수", "매도"]
    us_b = us[us["방식"] == "지수"].iloc[0]
    kr_b = kr[kr["방식"] == "지수"].iloc[0]
    d = kr[kr["방식"] != "지수"].merge(us[us["방식"] != "지수"], on=key, suffixes=("_kr", "_us"))
    d = d[(d["방식"] == "순환 매매") | (d["발견_보유일_kr"] >= 20)]      # 중기: 평균 보유 20일 이상
    pd.set_option("display.width", 330)
    pd.set_option("display.unicode.east_asian_width", True)
    f = lambda v, fmt: fmt.format(v) if pd.notna(v) else "-"
    arrow = lambda x, a, fmt: x[f"발견_{a}"].map(lambda v: f(v, fmt)) + " → " + x[f"확인_{a}"].map(lambda v: f(v, fmt))

    def show(x):
        return pd.DataFrame({
            "매수": x["매수"], "매도": x["매도"],
            "보유일": x["발견_보유일_kr"].map(lambda v: f(v, "{:.0f}")),
            "한국 연평균": arrow(x, "연평균_kr", "{:+.1%}").values, "한국 샤프": arrow(x, "샤프_kr", "{:.2f}").values,
            "한국 낙폭": arrow(x, "최대낙폭_kr", "{:.0%}").values,
            "미국 연평균": arrow(x, "연평균_us", "{:+.1%}").values, "미국 샤프": arrow(x, "샤프_us", "{:.2f}").values,
            "미국 낙폭": arrow(x, "최대낙폭_us", "{:.0%}").values,
        })

    print(f"비교: 코스피 지수 연평균 {kr_b['발견_연평균']:+.1%} → {kr_b['확인_연평균']:+.1%} (샤프 {kr_b['발견_샤프']:.2f} → {kr_b['확인_샤프']:.2f}, "
          f"낙폭 {kr_b['발견_최대낙폭']:.0%} → {kr_b['확인_최대낙폭']:.0%}) / 나스닥 {us_b['발견_연평균']:+.1%} → {us_b['확인_연평균']:+.1%} "
          f"(샤프 {us_b['발견_샤프']:.2f} → {us_b['확인_샤프']:.2f}, 낙폭 {us_b['발견_최대낙폭']:.0%} → {us_b['확인_최대낙폭']:.0%})")
    print(f"\n[1] 한국 발견 기간(2016~22) 계좌 샤프지수로 고른 상위 10개 (평균 보유 20일 이상, 후보 {len(d)}개) — 발견 → 확인")
    print(show(d.sort_values("발견_샤프_kr", ascending=False).head(10)).to_string(index=False))
    for kind in ["신호 매매", "순환 매매"]:
        x = d[d["방식"] == kind].sort_values("발견_샤프_kr", ascending=False).head(5)
        print(f"\n[2] {kind} 상위 5개 (한국 발견 기간 샤프 기준)")
        print(show(x).to_string(index=False))
    cols = ["발견_샤프_kr", "확인_샤프_kr", "발견_샤프_us", "확인_샤프_us"]
    d["네 곳 최소 샤프"] = d[cols].min(axis=1)
    print("\n[3] 참고: 네 곳 중 가장 나쁜 샤프지수가 높은 순 (네 곳을 모두 보고 고른 것이라 검증 아님)")
    print(show(d.sort_values("네 곳 최소 샤프", ascending=False).head(8)).to_string(index=False))
    d.to_csv(os.path.join(S.BASE, "results", "midterm_summary.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    summary() if len(sys.argv) > 1 and sys.argv[1] == "summary" else run_market()
