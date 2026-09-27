"""
마크 미너비니 VCP(변동성 수축 패턴)가 신고가 돌파 성과를 개선하는지 검증

VCP 정의 (결과를 보기 전에 미너비니 책 기준으로 미리 정함)
- 베이스: 직전 고점(돌파하는 그 고점)부터 돌파 전날까지. 길이 15~325거래일(3~65주),
          베이스 안 최대 조정 폭 50% 이하
- 수축 판별 (두 가지 방법)
  1) 파동 방식(주): 첫 수축 = 직전 고점 → 베이스 최저점, 다음 수축 = 그 이후 최고점 → 그 뒤 최저점 … 반복.
     (이렇게 세면 저점은 계속 높아지고 고점은 계속 낮아짐)
     3% 이상 수축이 2번 이상, 각 수축이 직전 수축의 3/4 이하, 마지막 수축 10% 이하
  2) 단순 방식: 베이스를 기간으로 3등분 → 구간 변동폭 점점 감소, 구간 저점 점점 상승, 마지막 구간 10% 이하
- 거래량: 마지막 수축 구간 평균 거래량 < 첫 수축 구간 평균 거래량 (거래량 마름),
          돌파일 거래량 >= 50일 평균의 1.5배
- 트렌드 템플릿(2단계 상승 추세): 종가 > 50일선 > 150일선 > 200일선, 200일선 1개월 상승,
          52주 저가 대비 +30% 이상, 52주 고가의 75% 이상, 상대강도(RS) 70 이상

비교
- 매수 신호: 역사적 신고가 돌파(주), 52주 신고가 돌파(표본을 늘려 재확인)
- 매도: A) 손절 -7% / 25일선 이탈 50% / 60일선 이탈 50%   B) +15% 익절 / 20일째 청산
- SG증권발 주가조작 사태 8종목은 처음부터 제외
- 무작위 비교(순열 검정): 같은 신호 묶음에서 무작위로 같은 수를 뽑았을 때
  VCP만큼 평균 수익이 높게 나올 확률

실행: python vcp_test.py   (collect_data.py를 먼저 실행해야 함)
"""
import os

import matplotlib
import numpy as np
import pandas as pd

import best_strategies as B
import strategies as S
from ath_low_gap import SG_STOCKS

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULT_DIR = S.RESULT_DIR
SPLIT = pd.Timestamp(S.SPLIT_DATE)
B.H = 250                        # 이평선 매도를 기다릴 수 있도록 최대 보유 1년
MIN_BASE, MAX_BASE = 15, 325     # 베이스 기간 3주 ~ 65주
MAX_BASE_DEPTH = 0.50            # 베이스 안 최대 조정 폭
TIGHT = 0.10                     # 마지막 수축(구간) 변동폭 상한
MIN_T = 0.03                     # 이보다 작은 흔들림은 수축으로 세지 않음
RATIO = 0.75                     # 각 수축은 직전 수축의 3/4 이하여야 함
BREAKOUT_VOL = 1.5               # 돌파일 거래량 / 50일 평균 거래량
N_PERM = 5000                    # 무작위 비교 반복 횟수
EXITS = {
    "A": [(0.5, dict(ma="ma25", sl=-0.07)), (0.5, dict(ma="ma60", sl=-0.07))],
    "B": [(1, dict(tp=0.15, time=20))],
}
EXIT_NAMES = {"A": "손절-7% / 25일선 50% / 60일선 50%", "B": "+15% 익절 / 20일 청산"}


def add_minervini(p, P):
    """미너비니 트렌드 템플릿에 필요한 지표."""
    c = p["close"]
    for n in [50, 150, 200]:
        p[f"ma{n}"] = P.roll(c, n)
    p["ma200_20ago"] = P.shift(p["ma200"], 20)
    p["ll250"] = P.roll(p["low"], 250, "min")
    p["hh250_incl"] = P.roll(p["high"], 250, "max")
    p["vma50"] = P.shift(P.roll(p["volume"], 50), 1)
    # 상대강도(RS): 최근 3·6·9·12개월 수익률 가중합의 전 종목 순위 (IBD 방식 근사, 0~100)
    roc = lambda n: c / P.shift(c, n) - 1
    raw = 0.4 * roc(63) + 0.2 * roc(126) + 0.2 * roc(189) + 0.2 * roc(252)
    p["rs"] = raw.groupby(p["date"]).rank(pct=True) * 100
    p["trend_template"] = (
        (c > p["ma50"]) & (p["ma50"] > p["ma150"]) & (p["ma150"] > p["ma200"])
        & (p["ma200"] > p["ma200_20ago"]) & (c >= p["ll250"] * 1.3)
        & (c >= p["hh250_incl"] * 0.75) & (p["rs"] >= 70)
    )
    return p


def wave_contractions(h, lo):
    """베이스의 고가·저가 배열에서 수축 목록 [(고점 위치, 저점 위치, 하락률)]을 계산.
    첫 수축 = 베이스 최고점 → 이후 최저점, 다음 수축 = 그 저점 이후 최고점 → 그 뒤 최저점 … 반복."""
    out, s = [], 0
    while s < len(h):
        hi = s + int(np.argmax(h[s:]))
        if hi >= len(h) - 1:
            break
        lw = hi + 1 + int(np.argmin(lo[hi + 1:]))
        out.append((hi, lw, 1 - lo[lw] / h[hi]))
        s = lw + 1
    return out


def base_features(p, P, rows, lookback):
    """각 신호의 베이스(직전 고점 ~ 돌파 전날)에서 수축 특징 계산."""
    high, low, vol = p["high"].to_numpy(), p["low"].to_numpy(), p["volume"].to_numpy()
    starts = rows - P.pos[rows]
    records, waves = [], []
    for i, s0 in zip(rows, starts):
        s = s0 if lookback is None else max(s0, i - lookback)
        j = s + int(np.argmax(high[s:i]))            # 돌파하는 직전 고점이 생긴 날
        length = i - j
        f = {"base_start": j, "base_len": length, "base_depth": 1 - low[j:i].min() / high[j]}
        w = []
        if length >= MIN_BASE:
            # 단순 방식: 기간 3등분
            edges = np.linspace(j, i, 4).round().astype(int)
            for k in range(3):
                a, b = edges[k], edges[k + 1]
                f[f"d3_{k + 1}"] = 1 - low[a:b].min() / high[a:b].max()
                f[f"l3_{k + 1}"] = low[a:b].min()
                f[f"v3_{k + 1}"] = vol[a:b].mean()
            # 파동 방식
            w = [(j + a, j + b, d) for a, b, d in wave_contractions(high[j:i], low[j:i]) if d >= MIN_T]
            if w:
                f["t_count"] = len(w)
                f["t_first"] = w[0][2]
                f["t_last"] = w[-1][2]
                f["t_max_ratio"] = max((w[k][2] / w[k - 1][2] for k in range(1, len(w))), default=np.nan)
                f["t_vol_first"] = vol[w[0][0]:w[0][1] + 1].mean()
                f["t_vol_last"] = vol[w[-1][0]:i].mean()
        records.append(f)
        waves.append(w)
    return pd.DataFrame(records), waves


def vcp_simple(f, tight=TIGHT):
    """단순 방식: 기간 3등분 → 변동폭 감소, 저점 상승, 마지막 구간 타이트."""
    d = f[[f"d3_{k}" for k in (1, 2, 3)]].to_numpy()
    lo = f[[f"l3_{k}" for k in (1, 2, 3)]].to_numpy()
    ok = (f["base_len"].between(MIN_BASE, MAX_BASE) & (f["base_depth"] <= MAX_BASE_DEPTH)).to_numpy()
    ok &= np.all(np.diff(d, axis=1) < 0, axis=1) & np.all(np.diff(lo, axis=1) > 0, axis=1)
    return ok & (d[:, -1] <= tight)


def vcp_wave(f, tight=TIGHT, ratio=RATIO, min_count=2):
    """파동 방식: 수축 min_count번 이상, 각 수축이 직전의 ratio배 이하, 마지막 수축 tight 이하."""
    ok = (f["base_len"].between(MIN_BASE, MAX_BASE) & (f["base_depth"] <= MAX_BASE_DEPTH)).to_numpy()
    ok &= (f["t_count"] >= min_count).to_numpy()
    ok &= (f["t_max_ratio"] <= ratio).to_numpy()
    return ok & (f["t_last"] <= tight).to_numpy()


def build_variants(p, rows, f):
    c = p["close"].to_numpy()[rows]
    gap = c / p["ma20"].to_numpy()[rows] - 1
    tt = p["trend_template"].to_numpy()[rows]
    breakout_vol = p["volume"].to_numpy()[rows] >= BREAKOUT_VOL * p["vma50"].to_numpy()[rows]
    vol_ok = (f["t_vol_last"] < f["t_vol_first"]).to_numpy() & breakout_vol
    wave = vcp_wave(f)
    return gap, {
        "기준: 신고가 돌파 전체": np.ones(len(rows), dtype=bool),
        "20일선 이격 20% 이하 (6부)": gap <= 0.20,
        "트렌드 템플릿만": tt,
        "VCP 단순 (기간 3등분)": vcp_simple(f),
        "VCP 파동": wave,
        "VCP 파동 + 거래량 (마름 → 돌파일 급증)": wave & vol_ok,
        "VCP 파동 + 거래량 + 트렌드 템플릿 (풀세트)": wave & vol_ok & tt,
        "[민감도] 마지막 수축 7% 이하": vcp_wave(f, tight=0.07),
        "[민감도] 마지막 수축 15% 이하": vcp_wave(f, tight=0.15),
        "[민감도] 수축 비율 1/2 이하": vcp_wave(f, ratio=0.5),
        "[민감도] 수축 비율 조건 없음": vcp_wave(f, ratio=1.0),
        "[민감도] 수축 3번 이상": vcp_wave(f, min_count=3),
    }


def perm_test(ret, mask, rng):
    """mask 거래의 평균 수익 - 나머지 평균 수익이, 무작위로 뽑았을 때 이만큼 이상 나올 확률."""
    ret, mask = np.asarray(ret), np.asarray(mask, dtype=bool)
    k, n = mask.sum(), len(ret)
    if k < 10 or k == n:
        return np.nan, np.nan
    obs = ret[mask].mean() - ret[~mask].mean()
    total = ret.sum()
    hits = 0
    for _ in range(N_PERM):
        s = ret[rng.choice(n, k, replace=False)].sum()
        hits += (s / k - (total - s) / (n - k)) >= obs
    return obs, (hits + 1) / (N_PERM + 1)


def avg_exposure(t, n_dates, slots=10):
    """평균 투자 비중(추정): 날마다 보유 중인 신호 수(최대 slots) / slots"""
    busy = np.zeros(n_dates + 300)
    for e, h in zip(t["entry_idx"], t["hold"]):
        busy[e:e + int(h)] += 1
    first = int(t["entry_idx"].min())
    return np.minimum(busy[first:n_dates], slots).mean() / slots


def seg_stats(curve, before):
    seg = curve[curve.index < SPLIT] if before else curve[curve.index >= SPLIT]
    if len(seg) < 60:
        return {"연평균수익률": np.nan, "샤프지수": np.nan, "최대낙폭": np.nan}
    return B.curve_stats(seg)


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    print("1) 데이터·지표 준비 중...")
    p, P, out, universe, dates = B.load_all()
    p = add_minervini(p, P)
    names = pd.read_csv(os.path.join(S.DATA_DIR, "stock_list.csv"), dtype={"code": str})
    sg_codes = set(names.loc[names["name"].isin(SG_STOCKS), "code"])
    base_ok = universe & ~p["code"].isin(sg_codes).to_numpy()
    success = out["success"].to_numpy()
    c = p["close"]

    def cooled(sig):
        sig = sig.fillna(False)
        recent = P.shift(P.roll(sig.astype(float), S.COOLDOWN, "sum"), 1).fillna(0)
        return (sig & (recent == 0)).to_numpy() & base_ok

    pools = {
        "역사적 신고가 돌파": (np.where(cooled((c > p["hh_all"]) & (P.pos >= 500)))[0], None),
        "52주 신고가 돌파": (np.where(cooled(c > p["hh250"]))[0], 250),
    }

    rng = np.random.default_rng(0)
    table, perm_rows, saved = [], [], {}
    for pool_name, (rows, lookback) in pools.items():
        print(f"\n2) [{pool_name}] 신호 {len(rows):,}건의 베이스 분석 중...")
        f, waves = base_features(p, P, rows, lookback)
        gap, variants = build_variants(p, rows, f)
        is_early = p["date"].to_numpy()[rows] < np.datetime64(SPLIT)
        results = {}
        for ex, legs in EXITS.items():
            m = B.path_matrix(p, P, rows)
            ret, hold, value = B.run_exit(m, legs)
            full = pd.DataFrame({"date": p["date"].to_numpy()[rows], "ret": ret, "hold": hold,
                                 "success": success[rows], "entry_idx": m["date_idx"][:, 0],
                                 "tv20": p["tv20"].to_numpy()[rows]})
            results[ex] = (full, value)
            del m
        saved[pool_name] = (rows, f, waves, variants, results)

        for vname, vm in variants.items():
            row = {"신호": pool_name, "변형": vname,
                   "발견_거래수": int((vm & is_early).sum()), "확인_거래수": int((vm & ~is_early).sum()),
                   "이격 중간값": np.median(gap[vm]) if vm.any() else np.nan}
            for ex, (full, value) in results.items():
                sub = full[vm].copy()
                if len(sub) < 5:
                    continue
                sub["row_key"] = np.arange(len(sub))
                curve = B.portfolio(sub, dates, [value[k] for k in np.where(vm)[0]])
                for label, before in [("발견", True), ("확인", False)]:
                    part = sub[sub["date"] < SPLIT] if before else sub[sub["date"] >= SPLIT]
                    cs = seg_stats(curve, before)
                    row[f"{label}_승률"] = part["success"].mean()
                    row[f"{ex}_{label}_거래평균"] = part["ret"].mean()
                    row[f"{ex}_{label}_수익비율"] = (part["ret"] > 0).mean()
                    row[f"{ex}_{label}_연평균"] = cs["연평균수익률"]
                    row[f"{ex}_{label}_샤프"] = cs["샤프지수"]
                    row[f"{ex}_{label}_최대낙폭"] = cs["최대낙폭"]
                row[f"{ex}_투자비중"] = avg_exposure(sub, len(dates))
            table.append(row)

        # 무작위 비교: (1) 전체 신호 중 VCP vs 나머지  (2) 이격 20% 이하 신호 중 VCP vs 나머지
        for ex, (full, _) in results.items():
            ret = full["ret"].to_numpy()
            for vname in ["트렌드 템플릿만", "VCP 단순 (기간 3등분)", "VCP 파동",
                          "VCP 파동 + 거래량 (마름 → 돌파일 급증)", "VCP 파동 + 거래량 + 트렌드 템플릿 (풀세트)"]:
                diff, pv = perm_test(ret, variants[vname], rng)
                sub_mask = gap <= 0.20
                diff2, pv2 = perm_test(ret[sub_mask], variants[vname][sub_mask], rng)
                perm_rows.append({"신호": pool_name, "매도": ex, "변형": vname,
                                  "전체 대비 평균 차이": diff, "우연일 확률(전체)": pv,
                                  "이격20%이하 안에서 차이": diff2, "우연일 확률(이격20%이하)": pv2})

    res = pd.DataFrame(table)
    res.to_csv(os.path.join(RESULT_DIR, "vcp_test.csv"), index=False, encoding="utf-8-sig")
    perm = pd.DataFrame(perm_rows)
    perm.to_csv(os.path.join(RESULT_DIR, "vcp_permutation.csv"), index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 320)
    pd.set_option("display.unicode.east_asian_width", True)
    arrow = lambda a, b, f: (res[a].map(lambda v: f.format(v) if pd.notna(v) else "-") + " → "
                             + res[b].map(lambda v: f.format(v) if pd.notna(v) else "-"))
    for pool_name in pools:
        mask = res["신호"] == pool_name
        for ex in EXITS:
            show = pd.DataFrame({
                "변형": res["변형"],
                "거래수": arrow("발견_거래수", "확인_거래수", "{:,.0f}"),
                "이격": res["이격 중간값"].map("{:.0%}".format),
                "승률": arrow("발견_승률", "확인_승률", "{:.0%}"),
                "거래평균": arrow(f"{ex}_발견_거래평균", f"{ex}_확인_거래평균", "{:+.1%}"),
                "수익비율": arrow(f"{ex}_발견_수익비율", f"{ex}_확인_수익비율", "{:.0%}"),
                "계좌 연평균": arrow(f"{ex}_발견_연평균", f"{ex}_확인_연평균", "{:+.1%}"),
                "샤프": arrow(f"{ex}_발견_샤프", f"{ex}_확인_샤프", "{:.2f}"),
                "최대낙폭": arrow(f"{ex}_발견_최대낙폭", f"{ex}_확인_최대낙폭", "{:.0%}"),
                "투자비중": res[f"{ex}_투자비중"].map(lambda v: f"{v:.0%}" if pd.notna(v) else "-"),
            })[mask]
            print(f"\n[{pool_name} / 매도 {ex}: {EXIT_NAMES[ex]}]  (SG 8종목 제외, 표기: 발견 2016~22 → 확인 2023~26)")
            print(show.to_string(index=False))

    pshow = perm.copy()
    for col in ["전체 대비 평균 차이", "이격20%이하 안에서 차이"]:
        pshow[col] = pshow[col].map(lambda v: f"{v:+.2%}" if pd.notna(v) else "-")
    for col in ["우연일 확률(전체)", "우연일 확률(이격20%이하)"]:
        pshow[col] = pshow[col].map(lambda v: f"{v:.1%}" if pd.notna(v) else "-")
    print(f"\n[무작위 비교] 거래당 평균 수익이 나머지보다 얼마나 높은지, 그리고 무작위로 뽑아도 그만큼 나올 확률"
          f" ({N_PERM:,}회, 5% 미만이면 우연이 아닐 가능성이 높음)")
    print(pshow.to_string(index=False))

    # ---- 차트 1: 결과 요약 ----
    ath = res[res["신호"] == "역사적 신고가 돌파"].reset_index(drop=True)
    fig, axes = plt.subplots(1, 2, figsize=(18, 6.5))
    labels = ["All ATH", "Gap<=20%", "Trend tmpl", "VCP simple", "VCP wave", "VCP+Vol", "Full set",
              "last<=7%", "last<=15%", "ratio<=1/2", "no ratio", "3+ T"]
    x = np.arange(len(ath))
    for k, (ex, off) in enumerate([("A", -0.3), ("B", -0.1)]):
        axes[0].bar(x + off, ath[f"{ex}_발견_거래평균"] * 100, 0.2, label=f"Exit {ex} 2016-22", color=f"C{k}", alpha=0.45)
        axes[0].bar(x + off + 0.2, ath[f"{ex}_확인_거래평균"] * 100, 0.2, label=f"Exit {ex} 2023-26", color=f"C{k}")
    axes[0].set_xticks(x, labels[:len(ath)], rotation=35)
    axes[0].axhline(0, color="k", lw=0.8)
    axes[0].set_title("All-time-high breakout: avg return per trade (%), SG stocks excluded")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3, axis="y")
    rows, f, waves, variants, results = saved["역사적 신고가 돌파"]
    full, value = results["A"]
    for vname, lab in [("기준: 신고가 돌파 전체", "All ATH"), ("20일선 이격 20% 이하 (6부)", "Gap<=20%"),
                       ("VCP 파동", "VCP wave"), ("VCP 파동 + 거래량 (마름 → 돌파일 급증)", "VCP+Vol"),
                       ("VCP 파동 + 거래량 + 트렌드 템플릿 (풀세트)", "Full set")]:
        vm = variants[vname]
        if vm.sum() < 5:
            continue
        sub = full[vm].copy()
        sub["row_key"] = np.arange(len(sub))
        cv = B.portfolio(sub, dates, [value[k] for k in np.where(vm)[0]])
        axes[1].plot(cv / cv.iloc[0], label=lab)
    axes[1].axvline(SPLIT, color="k", alpha=0.3)
    axes[1].set_yscale("log")
    axes[1].set_title("Exit A account (max 10 positions, log scale)")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "vcp_test.png"), dpi=110)

    # ---- 차트 2: VCP로 판별된 실제 사례 (판별이 제대로 되는지 눈으로 확인) ----
    vm = variants["VCP 파동 + 거래량 (마름 → 돌파일 급증)"]
    picks = np.where(vm)[0]
    picks = picks[np.linspace(0, len(picks) - 1, 9).round().astype(int)] if len(picks) >= 9 else picks
    name_of = names.set_index("code")["name"]
    fig, axes = plt.subplots(3, 3, figsize=(18, 12))
    for ax, k in zip(axes.flat, picks):
        i = rows[k]
        j = int(f.loc[k, "base_start"])
        a, b = max(j - 20, i - P.pos[i]), min(i + 25, i + P.left[i])
        d = p.iloc[a:b + 1]
        ax.plot(d["date"], d["close"], color="k", lw=1)
        ax.fill_between(d["date"], d["low"], d["high"], color="gray", alpha=0.3)
        for n_t, (hi, lw, dep) in enumerate(waves[k]):
            ax.plot([p["date"].iloc[hi], p["date"].iloc[lw]], [p["high"].iloc[hi], p["low"].iloc[lw]],
                    color=f"C{n_t}", lw=2)
            ax.annotate(f"T{n_t + 1} {dep:.0%}", (p["date"].iloc[lw], p["low"].iloc[lw]), fontsize=8,
                        color=f"C{n_t}", xytext=(0, -12), textcoords="offset points")
        ax.axhline(p["hh_all"].iloc[i], color="r", ls="--", lw=0.8)
        ax.axvline(p["date"].iloc[i], color="r", lw=0.8)
        ax.set_title(f"{p['code'].iloc[i]} breakout {p['date'].iloc[i].date()}", fontsize=9)
        ax.tick_params(axis="x", labelsize=7)
    plt.suptitle("Detected VCP examples (colored lines = contractions T1, T2..., red dashed = prior high, red line = breakout)")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "vcp_examples.png"), dpi=90)
    print("\n예시 차트 종목: " + ", ".join(
        f"{p['code'].iloc[rows[k]]} {name_of.get(p['code'].iloc[rows[k]], '')} {p['date'].iloc[rows[k]].date()}"
        for k in picks))

if __name__ == "__main__":
    main()
