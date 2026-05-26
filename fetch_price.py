import yfinance as yf
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta
from config import DATA_DIR

# ============================================================
# 取得最近N個交易日日期
# ============================================================
def get_recent_trading_days(n=4):
    days = []
    d    = datetime.today()
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    return days  # [今天或最近, T-1, T-2, T-3]

# ============================================================
# 抓單支股票近3日開收盤價
# ============================================================
def fetch_stock_ohlc(stock_id, trading_days):
    for suffix in [".TW", ".TWO"]:
        try:
            ticker = yf.Ticker(stock_id + suffix)
            hist   = ticker.history(period="5d", interval="1d")
            if hist.empty:
                continue

            hist.index = hist.index.strftime("%Y-%m-%d")
            result = {}
            for i, day in enumerate(trading_days[:4], 0):
                if day in hist.index:
                    result[f"t{i}_open"]  = round(float(hist.loc[day, "Open"]),  2)
                    result[f"t{i}_close"] = round(float(hist.loc[day, "Close"]), 2)

            # 當日走勢（5分K）
            intraday = ticker.history(period="1d", interval="5m")
            if not intraday.empty:
                closes = intraday["Close"].tolist()
                step   = max(1, len(closes) // 20)
                result["trend"]    = [round(c, 2) for c in closes[::step]]
                result["chg"]      = round(float(intraday["Close"].iloc[-1]) - float(intraday["Open"].iloc[0]), 2)
                result["chg_pct"]  = round(result["chg"] / float(intraday["Open"].iloc[0]) * 100, 2) if intraday["Open"].iloc[0] else 0

            return result
        except Exception:
            continue
    return {}

# ============================================================
# 批次抓取
# ============================================================
def fetch_prices(stock_ids):
    trading_days = get_recent_trading_days(4)
    prices       = {}
    total        = len(stock_ids)
    print(f"[股價] 抓取 {total} 支，基準日：{trading_days[0]}")

    for i, sid in enumerate(stock_ids, 1):
        result = fetch_stock_ohlc(sid, trading_days)
        if result:
            prices[sid] = result
        if i % 10 == 0 or i == total:
            print(f"[股價] 進度：{i}/{total}")
        time.sleep(0.3)

    path = os.path.join(DATA_DIR, "prices.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
    print(f"[股價] ✅ {len(prices)} 支有資料")
    return prices

# ============================================================
# 從 result.json 取股票清單
# ============================================================
def fetch_prices_from_result():
    result_path = os.path.join(DATA_DIR, "result.json")
    if not os.path.exists(result_path):
        print("❌ 找不到 result.json")
        return {}

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    stock_ids = set()
    for key in ["外資買超","外資賣超","三大法人買超","三大法人賣超","投信買超","投信賣超"]:
        for item in result.get(key, []):
            stock_ids.add(item["股票代號"])

    return fetch_prices(list(stock_ids))

if __name__ == "__main__":
    fetch_prices_from_result()