import requests
import pandas as pd
import json
import os
import time

SAVE_DIR = "data"
os.makedirs(SAVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ============================================================
# 抓取上市股票清單（TWSE）
# ============================================================
def fetch_twse_stocks():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        print("[上市] 抓取股票清單...")
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data)
        # 只保留一般股票（代號為4碼數字）
        df = df[df["Code"].str.match(r"^\d{4}$")]
        df = df[["Code", "Name"]].rename(columns={"Code": "代號", "Name": "名稱"})
        df["市場"] = "上市"
        print(f"[上市] ✅ 取得 {len(df)} 支股票")
        return df
    except Exception as e:
        print(f"[上市] ❌ 失敗：{e}")
        return pd.DataFrame()

# ============================================================
# 抓取上櫃股票清單（OTC）
# ============================================================
def fetch_otc_stocks():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    try:
        print("[上櫃] 抓取股票清單...")
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data)
        # 只保留一般股票（代號為4碼數字）
        df = df[df["SecuritiesCompanyCode"].str.match(r"^\d{4}$")]
        df = df[["SecuritiesCompanyCode", "CompanyName"]].rename(
            columns={"SecuritiesCompanyCode": "代號", "CompanyName": "名稱"}
        )
        df["市場"] = "上櫃"
        print(f"[上櫃] ✅ 取得 {len(df)} 支股票")
        return df
    except Exception as e:
        print(f"[上櫃] ❌ 失敗：{e}")
        return pd.DataFrame()

# ============================================================
# 主程式：合併並儲存
# ============================================================
def fetch_all_stocks():
    print("\n" + "="*50)
    print("  抓取全市場股票清單")
    print("="*50)

    df_twse = fetch_twse_stocks()
    time.sleep(2)
    df_otc  = fetch_otc_stocks()

    frames = [df for df in [df_twse, df_otc] if not df.empty]
    if not frames:
        print("❌ 無法取得股票清單")
        return None

    df_all = pd.concat(frames, ignore_index=True).drop_duplicates(subset="代號")
    df_all = df_all.sort_values("代號").reset_index(drop=True)

    # 存成 JSON 和 CSV 兩種格式
    csv_path  = os.path.join(SAVE_DIR, "stock_list.csv")
    json_path = os.path.join(SAVE_DIR, "stock_list.json")

    df_all.to_csv(csv_path, index=False, encoding="utf-8-sig")

    stock_dict = df_all.set_index("代號")[["名稱","市場"]].to_dict(orient="index")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(stock_dict, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 共 {len(df_all)} 支股票（上市 {len(df_twse)} + 上櫃 {len(df_otc)}）")
    print(f"   已儲存至：{csv_path}")

    # 預覽前5筆
    print("\n前5筆預覽：")
    print(df_all.head().to_string(index=False))

    return df_all

if __name__ == "__main__":
    fetch_all_stocks()