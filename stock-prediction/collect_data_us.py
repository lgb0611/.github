"""
미국 주식 전 종목(나스닥 + NYSE + NYSE American) 10년치 일봉을 Yahoo Finance에서 받아옵니다.

실행: python collect_data_us.py
결과: data_us/stock_list.csv, data_us/prices.parquet, data_us/index.parquet
      (한국 데이터와 같은 형식이라 MARKET=us 로 기존 분석 스크립트를 그대로 돌릴 수 있음)

참고
- 가격은 액면분할이 반영된 가격입니다(배당은 반영 안 함, 한국 데이터와 동일).
- 보통주만: ETF, 워런트, 권리, 유닛, 우선주, ADR, 스팩(Acquisition Corp)은 제외
  폐쇄형 펀드도 제외 (한국에서 ETF·스팩을 뺀 것과 같은 취지)
- 현재 상장된 종목만 받을 수 있습니다(상장폐지 종목 제외 → 생존 편향 주의).
"""
import io
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_us")
START = pd.Timestamp("2016-01-01")
HEADERS = {"User-Agent": "Mozilla/5.0"}
INDEXES = {"NASDAQ": "^IXIC", "NYSE": "^NYA"}   # 상승장 필터용 거래소 종합지수
KEEP = re.compile(r"Common Stock|Ordinary Share|Common Share|Class [ABC]", re.I)
DROP = re.compile(r"Warrant|Right|Unit|Preferred|Depositary|Acquisition|Notes|Debenture|%|Fund|Beneficial Interest",
                  re.I)


def get_stock_list():
    base = "https://www.nasdaqtrader.com/dynamic/SymDir/"
    read = lambda f: pd.read_csv(io.StringIO(requests.get(base + f, headers=HEADERS, timeout=30).text),
                                 sep="|")[:-1]   # 마지막 줄은 파일 생성 시각
    nq = read("nasdaqlisted.txt").rename(columns={"Symbol": "sym"})
    nq["market"] = "NASDAQ"
    ot = read("otherlisted.txt").rename(columns={"ACT Symbol": "sym"})
    ot = ot[ot["Exchange"].isin(["N", "A"])]            # NYSE, NYSE American
    ot["market"] = "NYSE"
    df = pd.concat([nq, ot], ignore_index=True)
    df = df[(df["ETF"] == "N") & (df["Test Issue"] == "N")]
    name = df["Security Name"].fillna("")
    df = df[name.str.contains(KEEP) & ~name.str.contains(DROP)]
    df = df[~df["sym"].astype(str).str.contains(r"[\$\^]")]
    df["code"] = df["sym"].astype(str).str.replace(".", "-", regex=False)   # BRK.B → BRK-B (Yahoo 표기)
    return df[["code", "Security Name", "market"]].rename(columns={"Security Name": "name"}).drop_duplicates("code")


def get_prices(symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?period1={int(START.timestamp())}&period2={int(time.time())}&interval=1d")
    for attempt in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 429:                     # 요청이 너무 많음 → 잠시 쉬었다가 다시
                time.sleep(5 * (attempt + 1))
                continue
            result = r.json()["chart"]["result"]
            break
        except (requests.RequestException, ValueError, KeyError, TypeError):
            time.sleep(2 ** attempt)
    else:
        return None
    if not result or "timestamp" not in result[0]:
        return None
    q = result[0]["indicators"]["quote"][0]
    df = pd.DataFrame({"date": pd.to_datetime(result[0]["timestamp"], unit="s").normalize(),
                       **{k: q.get(k) for k in ["open", "high", "low", "close", "volume"]}})
    df = df.dropna(subset=["close"]).drop_duplicates("date", keep="last")
    df[["open", "high", "low"]] = df[["open", "high", "low"]].fillna(0)
    df["volume"] = df["volume"].fillna(0)
    df["code"] = symbol
    return df if len(df) else None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("1) 종목 목록 받는 중...")
    stock_list = get_stock_list()
    print(f"   보통주 {len(stock_list):,}개 (나스닥 {sum(stock_list.market == 'NASDAQ'):,}, "
          f"NYSE {sum(stock_list.market == 'NYSE'):,})")

    print("2) 지수 받는 중...")
    idx = []
    for market, sym in INDEXES.items():
        d = get_prices(sym)
        idx.append(d.assign(index=market)[["index", "date", "close"]])
    pd.concat(idx).to_parquet(os.path.join(DATA_DIR, "index.parquet"), index=False)

    print("3) 종목별 주가 받는 중...")
    results, failed = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(get_prices, code): code for code in stock_list["code"]}
        for i, future in enumerate(as_completed(futures), 1):
            df = future.result()
            (results.append(df) if df is not None else failed.append(futures[future]))
            if i % 500 == 0:
                print(f"   {i:,}/{len(futures):,} 완료 (실패 {len(failed)})")

    prices = pd.concat(results, ignore_index=True)
    prices.to_parquet(os.path.join(DATA_DIR, "prices.parquet"), index=False)
    stock_list = stock_list[stock_list["code"].isin(prices["code"].unique())]
    stock_list.to_csv(os.path.join(DATA_DIR, "stock_list.csv"), index=False, encoding="utf-8-sig")
    print(f"4) 저장 완료: {prices['code'].nunique():,}개 종목, {len(prices):,}줄, 실패 {len(failed)}개")
    print(f"   기간: {prices['date'].min().date()} ~ {prices['date'].max().date()}")


if __name__ == "__main__":
    main()
