"""
역사적 신고가 돌파 + 20일선 이격 20% 이하 + 미너비니 트렌드 템플릿

7부에서 효과가 있었던 두 가지(이격 줄이기, 트렌드 템플릿)를 합쳐 검증합니다.
- 트렌드 템플릿을 구성요소별로 나눠 무엇이 효과를 내는지 확인
- 52주 신고가 돌파에서도 같은 효과가 나오는지 재확인
- 무작위 비교(순열 검정), 연도별 수익, SG 주가조작 8종목 포함/제외 비교

실행: python gap_tt_test.py        역사적 신고가 기준
      python gap_tt_test.py 104w   104주(520거래일) 신고가 기준 (결과 파일 이름 끝에 _104w)
      (collect_data.py를 먼저 실행해야 함)
"""
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
import vcp_test as V
from ath_low_gap import SG_STOCKS

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULT_DIR = S.RESULT_DIR
MODE = sys.argv[1] if len(sys.argv) > 1 else "ath"
MAIN = {"ath": "역사적 신고가 돌파", "104w": "104주 신고가 돌파"}[MODE]
SUFFIX = "" if MODE == "ath" else f"_{MODE}"
CHART_LABEL = {"ath": "ATH", "104w": "104-week high"}[MODE]
SPLIT = V.SPLIT
EXITS = V.EXITS
EXIT_NAMES = V.EXIT_NAMES


def components(p, rows):
    """트렌드 템플릿 구성요소별 충족 여부 (신호 행 기준)."""
    g = lambda col: p[col].to_numpy()[rows]
    c = g("close")
    return {
        "정배열 (종가>50일>150일>200일)": (c > g("ma50")) & (g("ma50") > g("ma150")) & (g("ma150") > g("ma200")),
        "200일선 1개월 상승": g("ma200") > g("ma200_20ago"),
        "52주 저가 대비 +30% 이상": c >= g("ll250") * 1.3,
        "상대강도(RS) 70 이상": g("rs") >= 70,
    }


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터·지표 준비 중...")
    p, P, out, universe, dates = B.load_all()
    p = V.add_minervini(p, P)
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    is_sg = p["code"].isin(set(names.loc[names["name"].isin(SG_STOCKS), "code"])).to_numpy()
    success = out["success"].to_numpy()
    c = p["close"]

    def cooled(sig):
        sig = sig.fillna(False)
        recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        return (sig & (recent == 0)).to_numpy() & universe

    pools = {
        MAIN: cooled((c > p["hh_all"]) & (P.pos >= 500)) if MODE == "ath"
        else cooled(c > P.shift(P.roll(p["high"], 520, "max"), 1)),
        "52주 신고가 돌파": cooled(c > p["hh250"]),
    }
    rng = np.random.default_rng(0)
    table, perm_rows, curves, yearly = [], [], {}, {}

    for pool_name, pool in pools.items():
        rows_all = np.where(pool)[0]
        sg_row = is_sg[rows_all]
        gap = c.to_numpy()[rows_all] / p["ma20"].to_numpy()[rows_all] - 1
        tt = p["trend_template"].to_numpy()[rows_all]
        bull = p["bull"].to_numpy()[rows_all]
        comp = components(p, rows_all)
        low_gap = gap <= 0.20
        variants = {
            "기준: 신고가 돌파 전체": ~sg_row,
            "이격 20% 이하": low_gap & ~sg_row,
            "트렌드 템플릿만": tt & ~sg_row,
            "★ 이격 20% 이하 + 트렌드 템플릿": low_gap & tt & ~sg_row,
            "★ + 상승장만": low_gap & tt & bull & ~sg_row,
            "[민감도] 이격 15% 이하 + 트렌드 템플릿": (gap <= 0.15) & tt & ~sg_row,
            "[민감도] 이격 25% 이하 + 트렌드 템플릿": (gap <= 0.25) & tt & ~sg_row,
            "[참고] ★ + SG 8종목 포함": low_gap & tt,
        }
        for cname, cm in comp.items():
            variants[f"[구성요소] 이격 20% 이하 + {cname}"] = low_gap & cm & ~sg_row
        is_early = p["date"].to_numpy()[rows_all] < np.datetime64(SPLIT)

        print(f"\n2) [{pool_name}] 신호 {len(rows_all):,}건 계산 중...")
        for ex, legs in EXITS.items():
            m = B.path_matrix(p, P, rows_all)
            ret, hold, value = B.run_exit(m, legs)
            full = pd.DataFrame({"date": p["date"].to_numpy()[rows_all], "ret": ret, "hold": hold,
                                 "success": success[rows_all], "entry_idx": m["date_idx"][:, 0],
                                 "tv20": p["tv20"].to_numpy()[rows_all]})
            del m
            for vname, vm in variants.items():
                sub = full[vm].copy()
                sub["row_key"] = np.arange(len(sub))
                curve = B.portfolio(sub, dates, [value[k] for k in np.where(vm)[0]])
                curves[(pool_name, ex, vname)] = curve
                row = {"신호": pool_name, "매도": ex, "변형": vname,
                       "발견_거래수": int((vm & is_early).sum()), "확인_거래수": int((vm & ~is_early).sum()),
                       "투자비중": V.avg_exposure(sub, len(dates))}
                for label, before in [("발견", True), ("확인", False)]:
                    part = sub[sub["date"] < SPLIT] if before else sub[sub["date"] >= SPLIT]
                    cs = V.seg_stats(curve, before)
                    row.update({f"{label}_승률": part["success"].mean(), f"{label}_거래평균": part["ret"].mean(),
                                f"{label}_연평균": cs["연평균수익률"], f"{label}_샤프": cs["샤프지수"],
                                f"{label}_최대낙폭": cs["최대낙폭"]})
                table.append(row)
                if pool_name == MAIN and vname in (
                        "이격 20% 이하", "★ 이격 20% 이하 + 트렌드 템플릿", "★ + 상승장만"):
                    y = curve.resample("YE").last()
                    y = pd.concat([pd.Series([curve.iloc[0]], index=[curve.index[0]]), y]).pct_change().dropna()
                    yearly[f"{ex}) {vname}"] = pd.Series(y.values, index=y.index.year)

            # 무작위 비교: 이격 20% 이하 신호 안에서 트렌드 템플릿(및 구성요소) vs 나머지, 기간별로도
            base = low_gap & ~sg_row
            r = full["ret"].to_numpy()
            for tname, tm in [("트렌드 템플릿", tt)] + list(comp.items()):
                row = {"신호": pool_name, "매도": ex, "조건": tname}
                for label, pm in [("전체", np.ones_like(base)), ("발견", is_early), ("확인", ~is_early)]:
                    sel = base & pm
                    diff, pv = V.perm_test(r[sel], tm[sel], rng)
                    row[f"{label}_차이"], row[f"{label}_우연확률"] = diff, pv
                perm_rows.append(row)

    res = pd.DataFrame(table)
    res.to_csv(os.path.join(RESULT_DIR, f"gap_tt_test{SUFFIX}.csv"), index=False, encoding="utf-8-sig")
    perm = pd.DataFrame(perm_rows)
    perm.to_csv(os.path.join(RESULT_DIR, f"gap_tt_permutation{SUFFIX}.csv"), index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    fmt = lambda v, f: f.format(v) if pd.notna(v) else "-"
    arrow = lambda d, a, b, f: d[a].map(lambda v: fmt(v, f)) + " → " + d[b].map(lambda v: fmt(v, f))
    for (pool_name, ex), d in res.groupby(["신호", "매도"], sort=False):
        show = pd.DataFrame({
            "변형": d["변형"],
            "거래수": arrow(d, "발견_거래수", "확인_거래수", "{:,.0f}"),
            "승률": arrow(d, "발견_승률", "확인_승률", "{:.0%}"),
            "거래평균": arrow(d, "발견_거래평균", "확인_거래평균", "{:+.1%}"),
            "계좌 연평균": arrow(d, "발견_연평균", "확인_연평균", "{:+.1%}"),
            "샤프": arrow(d, "발견_샤프", "확인_샤프", "{:.2f}"),
            "최대낙폭": arrow(d, "발견_최대낙폭", "확인_최대낙폭", "{:.0%}"),
            "투자비중": d["투자비중"].map("{:.0%}".format),
        })
        print(f"\n[{pool_name} / 매도 {ex}: {EXIT_NAMES[ex]}]  (발견 2016~22 → 확인 2023~26)")
        print(show.to_string(index=False))

    pshow = perm.copy()
    for col in [c_ for c_ in pshow if c_.endswith("_차이")]:
        pshow[col] = pshow[col].map(lambda v: fmt(v, "{:+.2%}"))
    for col in [c_ for c_ in pshow if c_.endswith("_우연확률")]:
        pshow[col] = pshow[col].map(lambda v: fmt(v, "{:.1%}"))
    print("\n[무작위 비교] 이격 20% 이하 신호 안에서, 조건을 만족한 거래의 평균 수익 - 나머지 평균 수익")
    print(pshow.to_string(index=False))

    ydf = pd.DataFrame(yearly)
    idx = pd.read_parquet(os.path.join(S.DATA_DIR, "index.parquet")).pivot(index="date", columns="index", values="close")
    ydf["코스피"] = idx["KOSPI"].resample("YE").last().pct_change().reindex(
        pd.to_datetime(ydf.index.astype(str) + "-12-31")).to_numpy()
    print(f"\n[연도별 계좌 수익률, {MAIN}, SG 제외] (2026년은 9월까지)")
    print(ydf.map(lambda v: fmt(v, "{:+.1%}")).to_string())
    ydf.to_csv(os.path.join(RESULT_DIR, f"gap_tt_yearly{SUFFIX}.csv"), encoding="utf-8-sig")

    # 차트
    fig, axes = plt.subplots(1, 2, figsize=(17, 6))
    for ax, ex in zip(axes, EXITS):
        for vname, lab in [("기준: 신고가 돌파 전체", f"All {CHART_LABEL}"), ("이격 20% 이하", "Gap<=20%"),
                           ("트렌드 템플릿만", "Trend template"), ("★ 이격 20% 이하 + 트렌드 템플릿", "Gap<=20% + TT"),
                           ("★ + 상승장만", "Gap<=20% + TT + bull")]:
            cv = curves[(MAIN, ex, vname)]
            ax.plot(cv / cv.iloc[0], label=lab, lw=2 if "★" in vname else 1.2)
        k = idx["KOSPI"].reindex(curves[(MAIN, ex, "기준: 신고가 돌파 전체")].index).ffill()
        ax.plot(k / k.iloc[0], label="KOSPI", color="black", ls="--")
        ax.axvline(SPLIT, color="k", alpha=0.3)
        ax.set_yscale("log")
        ax.set_title(f"{CHART_LABEL} breakout, exit {ex}: account (max 10 positions, SG excluded, log)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, f"gap_tt_test{SUFFIX}.png"), dpi=110)


if __name__ == "__main__":
    main()
