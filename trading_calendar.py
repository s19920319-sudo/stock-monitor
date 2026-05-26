import requests
import json
import os
from datetime import datetime, timedelta

SAVE_DIR      = "data"
CALENDAR_FILE = os.path.join(SAVE_DIR, "trading_days.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.twse.com.tw/"
}

# ============================================================
# 從 TWSE 抓取當月交易日曆
# ============================================================
def fetch_trading_days(year=None, month=None):
    now   = datetime.today()
    year  = year  or now.year
    month = month or now.month

    # 民國年
    roc_year = year - 1911
    url = f"https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&year={roc_year}"
    try:
        r  = requests.get(url, headers=HEADERS, timeout=10)
        js = r.json()

        if js.get("stat") != "OK":
            return []

        # 抓休市日，反推交易日
        holidays = set()
        for row in js.get("data", []):
            try:
                parts = row[0].strip().split("/")
                y = int(parts[0]) + 1911
                m = int(parts[1])
                d = int(parts[2])
                holidays.add(f"{y}{m:02d}{d:02d}")
            except:
                continue

        # 產生當月所有工作日，排除假日
        trading_days = []
        d = datetime(year, month, 1)
        while d.month == month:
            ds = d.strftime("%Y%m%d")
            if d.weekday() < 5 and ds not in holidays:
                trading_days.append(ds)
            d += timedelta(days=1)

        print(f"[交易日曆] {year}/{month:02d} 取得 {len(trading_days)} 個交易日")
        return trading_days

    except Exception as e:
        print(f"[交易日曆] 抓取失敗：{e}")
        return []

# ============================================================
# 更新並儲存交易日曆（當月 + 下個月）
# ============================================================
def update_calendar():
    now   = datetime.today()
    days  = set()

    # 抓當月和上個月
    for delta in [0, -1]:
        m = now.month + delta
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        result = fetch_trading_days(y, m)
        days.update(result)
        print(f"[交易日曆] {y}/{m:02d} 取得 {len(result)} 個交易日")

    if days:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(days), f, ensure_ascii=False)
        print(f"[交易日曆] ✅ 已儲存 {len(days)} 個交易日")

    return sorted(days)

# ============================================================
# 取得最近一個交易日
# ============================================================
def get_last_trading_day():
    today = datetime.today()
    today_str = today.strftime("%Y%m%d")

    # 讀取本地交易日曆
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            trading_days = json.load(f)
        past = [d for d in trading_days if d <= today_str]
        if past:
            return max(past)

    # 備用：週末判斷 + 收盤時間判斷
    print("[交易日曆] ⚠️  找不到交易日曆，使用週末判斷")
    d = today
    # 跳過週末
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # 如果今天是交易日但還沒收盤（15:00前），抓前一個交易日
    if d.date() == today.date() and today.hour < 15:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime("%Y%m%d")

# ============================================================
# 判斷今天是否為交易日
# ============================================================
def is_trading_day(date_str=None):
    date_str = date_str or datetime.today().strftime("%Y%m%d")
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            trading_days = json.load(f)
        return date_str in trading_days
    # 備用：只排除週末
    d = datetime.strptime(date_str, "%Y%m%d")
    return d.weekday() < 5

# ============================================================
if __name__ == "__main__":
    print("更新交易日曆...")
    update_calendar()
    print(f"\n最近交易日：{get_last_trading_day()}")
    print(f"今天是交易日：{is_trading_day()}")