import requests
import pandas as pd
import os
import time
import urllib3
urllib3.disable_warnings()
from config import HEADERS, DATA_DIR

# ============================================================
# 抓取上市融資融券（OpenAPI）
# ============================================================
def fetch_margin_twse(date_str):
    url = "https://openapi.twse.com.tw/v1/marginTrading/MI_MARGN"
    try:
        print(f"[融資券-上市] 抓取：{date_str}")
        r  = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()

        if not data:
            print(f"[融資券-上市] ⚠️  無資料")
            return pd.DataFrame()

        rows = []
        for d in data:
            try:
                def n(v): return float(str(v).replace(",","").strip() or 0)
                margin_buy  = n(d.get("融資買進", 0))
                margin_sell = n(d.get("融資賣出", 0))
                margin_bal  = n(d.get("融資今日餘額", 0))
                short_buy   = n(d.get("融券買進", 0))
                short_sell  = n(d.get("融券賣出", 0))
                short_bal   = n(d.get("融券今日餘額", 0))

                rows.append({
                    "股票代號": str(d.get("股票代號","")).strip(),
                    "股票名稱": str(d.get("股票名稱","")).strip(),
                    "融資增減": margin_buy - margin_sell,
                    "融券增減": short_sell - short_buy,
                    "融資餘額": margin_bal,
                    "融券餘額": short_bal,
                    "券資比%":  round(short_bal / margin_bal * 100, 2) if margin_bal else 0,
                    "市場": "上市",
                })
            except:
                continue

        df = pd.DataFrame(rows)
        df = df[df["股票代號"].str.match(r"^\d{4}$")]  # 只保留一般股票
        print(f"[融資券-上市] ✅ {len(df)} 筆")
        return df

    except Exception as e:
        print(f"[融資券-上市] ❌ 失敗：{e}")
        return pd.DataFrame()

# ============================================================
# 抓取上櫃融資融券（OTC）
# ============================================================
def fetch_margin_otc(date_str):
    y = int(date_str[:4]) - 1911
    otc_date = f"{y}/{date_str[4:6]}/{date_str[6:8]}"
    url = (
        f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/"
        f"margin_bal_result.php?l=zh-tw&d={otc_date}&s=0,asc&o=json"
    )
    try:
        print(f"[融資券-上櫃] 抓取：{date_str}")
        r  = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        js = r.json()
        aa = js.get("aaData", [])
        if not aa:
            print(f"[融資券-上櫃] ⚠️  無資料")
            return pd.DataFrame()

        rows = []
        for row in aa:
            if len(row) < 12:
                continue
            try:
                def n(v): return float(str(v).replace(",","") or 0)
                rows.append({
                    "股票代號": str(row[0]).strip(),
                    "股票名稱": str(row[1]).strip(),
                    "融資增減": n(row[2]) - n(row[3]),
                    "融券增減": n(row[7]) - n(row[8]),
                    "融資餘額": n(row[5]),
                    "融券餘額": n(row[10]),
                    "券資比%":  round(n(row[10]) / n(row[5]) * 100, 2) if n(row[5]) else 0,
                    "市場": "上櫃",
                })
            except:
                continue

        df = pd.DataFrame(rows)
        print(f"[融資券-上櫃] ✅ {len(df)} 筆")
        return df

    except Exception as e:
        print(f"[融資券-上櫃] ❌ 失敗：{e}")
        return pd.DataFrame()

# ============================================================
# 主程式
# ============================================================
def fetch_all_margin(date_str):
    print(f"\n[融資融券] 抓取：{date_str}")
    df_twse = fetch_margin_twse(date_str)
    time.sleep(1)
    df_otc  = fetch_margin_otc(date_str)

    frames = [df for df in [df_twse, df_otc] if not df.empty]
    if not frames:
        print("[融資融券] ❌ 無任何資料")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    path = os.path.join(DATA_DIR, f"margin_{date_str}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[融資融券] ✅ 共 {len(df)} 筆，已存至 {path}")
    return df

if __name__ == "__main__":
    import sys
    date_str = None
    if len(sys.argv) > 1 and sys.argv[1] == "--date" and len(sys.argv) > 2:
        date_str = sys.argv[2]
        print(f"[指定日期] {date_str}")
    else:
        from trading_calendar import get_last_trading_day
        date_str = get_last_trading_day()
    fetch_all_margin(date_str)