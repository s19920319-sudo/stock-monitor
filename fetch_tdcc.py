import requests
import pandas as pd
import json
import os
from io import StringIO
from datetime import datetime
import urllib3
urllib3.disable_warnings()

SAVE_DIR     = "data"
TDCC_HISTORY = os.path.join(SAVE_DIR, "tdcc_history.json")
os.makedirs(SAVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/39.0.2171.95 Safari/537.36"
}

# ============================================================
# 下載集保全市場股權分散表
# ============================================================
def fetch_tdcc():
    url = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
    print("[集保] 下載股權分散表...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df = df.astype(str)

        # 統一欄位名稱
        df.columns = ["資料日期","證券代號","持股分級","人數","股數","占比"]

        # 移除公債（代號開頭Y）和分級16（差異調整）
        df = df[~df["證券代號"].str.startswith("Y")]
        df = df[df["持股分級"].str.strip() != "16"]

        df["人數"] = pd.to_numeric(df["人數"], errors="coerce").fillna(0)
        df["股數"] = pd.to_numeric(df["股數"], errors="coerce").fillna(0)

        # 取得資料日期
        date_str = df["資料日期"].iloc[0].strip()
        print(f"[集保] ✅ 資料日期：{date_str}，共 {df['證券代號'].nunique()} 支股票")

        return df, date_str

    except Exception as e:
        print(f"[集保] ❌ 失敗：{e}")
        return None, None

# ============================================================
# 計算每支股票的總戶數
# ============================================================
def calc_total_holders(df):
    grp = df.groupby("證券代號")["人數"].sum().reset_index()
    grp.columns = ["證券代號", "總戶數"]
    return grp

# ============================================================
# 載入 / 儲存歷史戶數紀錄
# ============================================================
def load_tdcc_history():
    if not os.path.exists(TDCC_HISTORY):
        return {}
    with open(TDCC_HISTORY, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tdcc_history(h):
    with open(TDCC_HISTORY, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def update_tdcc_history(history, date_str, holders_df):
    """
    history 結構：
    {
      "2330": {
        "records": [
          {"date": "20260515", "holders": 2633834},
          {"date": "20260508", "holders": 2640000},
          ...
        ]
      }
    }
    """
    for _, row in holders_df.iterrows():
        sid     = str(row["證券代號"]).strip()
        holders = int(row["總戶數"])

        if sid not in history:
            history[sid] = {"records": []}

        records = history[sid]["records"]
        # 避免重複寫入同一週
        if not any(r["date"] == date_str for r in records):
            records.append({"date": date_str, "holders": holders})
        # 只保留最近 4 週
        history[sid]["records"] = sorted(records, key=lambda x: x["date"])[-4:]

    return history

# ============================================================
# 分析：找出戶數連續減少的股票
# ============================================================
def find_decreasing(history, weeks=2):
    """
    找出最近 N 週戶數持續減少的股票
    """
    results = []
    for sid, info in history.items():
        records = sorted(info["records"], key=lambda x: x["date"], reverse=True)
        if len(records) < weeks:
            continue

        recent = records[:weeks]
        holders_seq = [r["holders"] for r in recent]

        # 檢查是否單調遞減（最新 < 前一週 < 前兩週...）
        is_decreasing = all(
            holders_seq[i] < holders_seq[i+1]
            for i in range(len(holders_seq)-1)
        )

        if is_decreasing:
            change = holders_seq[0] - holders_seq[-1]
            pct    = change / holders_seq[-1] * 100 if holders_seq[-1] > 0 else 0
            results.append({
                "證券代號":   sid,
                "最新戶數":   holders_seq[0],
                "四週前戶數": holders_seq[-1],
                "戶數變化":   change,
                "變化比例%":  round(pct, 2),
                "連減週數":   weeks,
            })

    return sorted(results, key=lambda x: x["變化比例%"])

# ============================================================
# 主程式
# ============================================================
def run_tdcc():
    print(f"\n{'='*50}")
    print(f"  集保戶數追蹤")
    print(f"{'='*50}\n")

    df, date_str = fetch_tdcc()
    if df is None:
        return

    holders_df = calc_total_holders(df)
    history    = load_tdcc_history()
    history    = update_tdcc_history(history, date_str, holders_df)
    save_tdcc_history(history)
    print(f"[集保] 歷史紀錄已更新（{TDCC_HISTORY}）")

    # 找出連兩週戶數減少
    decreasing = find_decreasing(history, weeks=2)

    if not decreasing:
        print("\n本週無股票連續四週戶數減少")
    else:
        print(f"\n📉 連四週戶數減少（籌碼集中）：{len(decreasing)} 支")
        print("-" * 60)
        for r in decreasing[:20]:  # 只顯示前20
            print(f"  {r['證券代號']}  "
                  f"戶數 {r['四週前戶數']:,} → {r['最新戶數']:,}  "
                  f"減少 {abs(r['戶數變化']):,} 戶  "
                  f"({r['變化比例%']}%)")

    # 存入 result.json 供網頁顯示
    result_path = os.path.join(SAVE_DIR, "result.json")
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)
        result["集保戶數減少"] = decreasing[:10]
        result["集保更新日期"] = date_str
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已更新至 result.json")

    return decreasing

if __name__ == "__main__":
    run_tdcc()