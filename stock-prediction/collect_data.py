"""
한국 주식 전 종목(코스피 + 코스닥) 10년치 일봉 데이터를 네이버 금융에서 받아옵니다.

실행: python collect_data.py
결과: data/stock_list.csv (종목 목록), data/prices.parquet (전체 주가)

참고
- 가격은 액면분할 등이 반영된 '수정주가'입니다.
- 현재 상장된 종목만 받을 수 있습니다(상장폐지 종목 제외 → 생존 편향 주의).
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
START_DATE = "20160101"  # 10년치
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_stock_list():
    """코스피·코스닥 전체 종목 목록을 가져옵니다 (ETF, 스팩 제외)."""
    rows = []
    for market in ["KOSPI", "KOSDAQ"]:
        page = 1
        while True:
            url = f"https://m.stock.naver.com/api/stocks/marketValue/{market}?page={page}&pageSize=100"
            data = requests.get(url, headers=HEADERS, timeout=15).json()
            stocks = data["stocks"]
            if not stocks:
                break
            for s in stocks:
                if s["stockEndType"] != "stock":  # ETF 등 제외
                    continue
                if "스팩" in s["stockName"]:  # 기업인수목적회사 제외
                    continue
                rows.append({
                    "code": s["itemCode"],
                    "name": s["stockName"],
                    "market": market,
                    "market_cap_억": int(s["marketValue"].replace(",", "")),
                })
            page += 1
    return pd.DataFrame(rows)


def get_prices(code):
    """한 종목의 일봉(시가, 고가, 저가, 종가, 거래량)을 가져옵니다."""
    url = ("https://fchart.stock.naver.com/sise.nhn"
           f"?symbol={code}&timeframe=day&count=3000&requestType=0")
    for attempt in range(3):
        try:
            text = requests.get(url, headers=HEADERS, timeout=15).text
            break
        except requests.RequestException:
            time.sleep(2 ** attempt)
    else:
        return None

    items = re.findall(r'data="([^"]+)"', text)
    rows = [item.split("|") for item in items]
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df = df[df["date"] >= START_DATE]
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["code"] = code
    return df


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("1) 종목 목록 받는 중...")
    stock_list = get_stock_list()
    stock_list.to_csv(os.path.join(DATA_DIR, "stock_list.csv"), index=False, encoding="utf-8-sig")
    print(f"   종목 수: {len(stock_list)}개")

    print("2) 종목별 주가 받는 중...")
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(get_prices, code): code for code in stock_list["code"]}
        for i, future in enumerate(as_completed(futures), 1):
            df = future.result()
            if df is not None:
                results.append(df)
            if i % 500 == 0:
                print(f"   {i}/{len(futures)} 완료")

    prices = pd.concat(results, ignore_index=True)
    prices.to_parquet(os.path.join(DATA_DIR, "prices.parquet"), index=False)
    print(f"3) 저장 완료: {prices['code'].nunique()}개 종목, {len(prices):,}줄")
    print(f"   기간: {prices['date'].min().date()} ~ {prices['date'].max().date()}")


if __name__ == "__main__":
    main()
