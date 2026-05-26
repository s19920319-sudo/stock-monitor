import requests
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta

SAVE_DIR = "data"
os.makedirs(SAVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.twse.com.tw/"
}

# ============================================================
# 工具：取得最近交易日（整合交易日曆）
# ============================================================
def get_last_trading_day():
    try:
        from trading_calendar import get_last_trading_day as _get
        return _get()
    except Exception:
        # 備用：純週末判斷
        d = datetime.today()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d.strftime("%Y%m%d")

# ============================================================
# 共用：呼叫 TWSE API
# ============================================================
def fetch_twse(url, name):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        js = r.json()
        if js.get("stat") != "OK" or not js.get("data"):
            print(f"[{name}] ⚠️  無資料")
            return None, []
        print(f"[{name}] ✅ {len(js['data'])} 筆")
        return js.get("fields", []), js["data"]
    except Exception as e:
        print(f"[{name}] ❌ 失敗：{e}")
        return None, []

# ============================================================
# 抓外資買賣超
# ============================================================
def fetch_foreign(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?date={date_str}&response=json"
    fields, data = fetch_twse(url, "外資")
    if not data:
        return pd.DataFrame()
    rows = []
    for d in data:
        if len(d) < 5:
            continue
        try:
            rows.append({
                "股票代號": str(d[1]).strip(),
                "股票名稱": str(d[2]).strip(),
                "買進股數": int(str(d[3]).replace(",","")),
                "賣出股數": int(str(d[4]).replace(",","")),
                "買賣超股數": int(str(d[5]).replace(",","").replace("+","")),
                "法人別": "外資"
            })
        except:
            continue
    return pd.DataFrame(rows)

# ============================================================
# 抓投信買賣超
# ============================================================
def fetch_trust(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT44U?date={date_str}&response=json"
    fields, data = fetch_twse(url, "投信")
    if not data:
        return pd.DataFrame()
    rows = []
    for d in data:
        if len(d) < 5:
            continue
        try:
            rows.append({
                "股票代號": str(d[1]).strip(),
                "股票名稱": str(d[2]).strip(),
                "買進股數": int(str(d[3]).replace(",","")),
                "賣出股數": int(str(d[4]).replace(",","")),
                "買賣超股數": int(str(d[5]).replace(",","").replace("+","")),
                "法人別": "投信"
            })
        except:
            continue
    return pd.DataFrame(rows)

# ============================================================
# 抓三大法人合計買賣超
# ============================================================
def fetch_institutional(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    fields, data = fetch_twse(url, "三大法人")
    if not data:
        return pd.DataFrame()
    rows = []
    for d in data:
        if len(d) < 19:
            continue
        try:
            rows.append({
                "股票代號": str(d[0]).strip(),
                "股票名稱": str(d[1]).strip(),
                "外資買賣超": int(str(d[4]).replace(",","").replace("+","")),
                "投信買賣超": int(str(d[10]).replace(",","").replace("+","")),
                "自營商買賣超": int(str(d[11]).replace(",","").replace("+","")),
                "三大合計": int(str(d[18]).replace(",","").replace("+","")),
            })
        except:
            continue
    return pd.DataFrame(rows)

# ============================================================
# 主程式
# ============================================================
def fetch_all(date_str=None):
    if date_str is None:
        date_str = get_last_trading_day()

    print(f"\n{'='*50}")
    print(f"  抓取三大法人資料：{date_str}")
    print(f"{'='*50}\n")

    df_foreign = fetch_foreign(date_str)
    time.sleep(1)
    df_trust   = fetch_trust(date_str)
    time.sleep(1)
    df_inst    = fetch_institutional(date_str)

    # 存檔
    if not df_inst.empty:
        df_inst.to_csv(os.path.join(SAVE_DIR, f"institutional_{date_str}.csv"),
                       index=False, encoding="utf-8-sig")
    if not df_foreign.empty:
        df_foreign.to_csv(os.path.join(SAVE_DIR, f"foreign_{date_str}.csv"),
                          index=False, encoding="utf-8-sig")
    if not df_trust.empty:
        df_trust.to_csv(os.path.join(SAVE_DIR, f"trust_{date_str}.csv"),
                        index=False, encoding="utf-8-sig")

    print(f"\n✅ 資料下載完成，請執行 analyzer.py")
    return df_inst, df_foreign, df_trust

if __name__ == "__main__":
    import sys
    date_str = None
    if len(sys.argv) > 1 and sys.argv[1] == "--date" and len(sys.argv) > 2:
        date_str = sys.argv[2]
        print(f"[指定日期] {date_str}")
    fetch_all(date_str)