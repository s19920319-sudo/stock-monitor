import pandas as pd
import json
import os
from datetime import datetime, timedelta
from config import DATA_DIR, TOP_N, CONSEC_DAYS, INST_RATIO_THR
from database import init_db, upsert_daily, upsert_ranking, upsert_tdcc, query_consecutive

RESULT_FILE = os.path.join(DATA_DIR, "result.json")

# ============================================================
# 載入各來源 CSV
# ============================================================
def load_csv(prefix, date_str):
    path = os.path.join(DATA_DIR, f"{prefix}_{date_str}.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, dtype={"股票代號": str})

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# 產生榜單（前N名）
# ============================================================
def make_top(df, col, top_n=TOP_N, ascending=False):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    ranked = df.nlargest(top_n, col) if not ascending else df.nsmallest(top_n, col)
    ranked = ranked.reset_index(drop=True)
    ranked["排名"] = ranked.index + 1
    ranked["買賣超張數"] = (ranked[col] / 1000).round(0).astype(int)
    return ranked

# ============================================================
# 連N日上榜判斷（從 ranking_history）
# ============================================================
def get_consecutive_alerts(date_str):
    buy_alerts, sell_alerts = [], []
    for rtype in ["三大法人買超", "外資買超", "投信買超"]:
        results = query_consecutive(rtype, CONSEC_DAYS)
        for r in results:
            buy_alerts.append({
                "股票代號": r["stock_id"],
                "股票名稱": r["stock_name"],
                "類型": "買超", "法人別": rtype
            })
    for rtype in ["三大法人賣超", "外資賣超", "投信賣超"]:
        results = query_consecutive(rtype, CONSEC_DAYS)
        for r in results:
            sell_alerts.append({
                "股票代號": r["stock_id"],
                "股票名稱": r["stock_name"],
                "類型": "賣超", "法人別": rtype
            })
    return buy_alerts, sell_alerts

# ============================================================
# 集保：大戶散戶比值計算
# ============================================================
def calc_tdcc_metrics(tdcc_df, date_str):
    if tdcc_df is None or tdcc_df.empty:
        return {}

    tdcc_df = tdcc_df.copy()
    tdcc_df["人數"] = pd.to_numeric(tdcc_df["人數"], errors="coerce").fillna(0)
    tdcc_df["占比"] = pd.to_numeric(tdcc_df["占比"], errors="coerce").fillna(0)
    tdcc_df["持股分級"] = pd.to_numeric(tdcc_df["持股分級"], errors="coerce").fillna(0).astype(int)

    metrics = {}
    tdcc_rows = []

    for sid, grp in tdcc_df.groupby("證券代號"):
        sid = str(sid).strip()
        total_holders = int(grp["人數"].sum())

        # 大戶：分級15（1000張以上）
        big = grp[grp["持股分級"] == 15]["占比"].sum()
        # 散戶：分級1-3（10張以下）
        small = grp[grp["持股分級"].isin([1, 2, 3])]["占比"].sum()

        metrics[sid] = {
            "holders":   total_holders,
            "big_pct":   round(float(big), 2),
            "small_pct": round(float(small), 2),
            "big_small_ratio": round(float(big) - float(small), 2),
        }
        tdcc_rows.append({
            "stock_id":  sid,
            "holders":   total_holders,
            "big_pct":   round(float(big), 2),
            "small_pct": round(float(small), 2),
        })

    # 寫入集保歷史
    if tdcc_rows:
        upsert_tdcc(date_str, tdcc_rows)

    return metrics

# ============================================================
# 計算集保戶數週變動
# ============================================================
def calc_tdcc_week_change(tdcc_metrics):
    tdcc_history = load_json("tdcc_history.json")
    changes = {}
    for sid, m in tdcc_metrics.items():
        if sid in tdcc_history:
            records = sorted(tdcc_history[sid].get("records", []),
                           key=lambda x: x["date"], reverse=True)
            if len(records) >= 2:
                changes[sid] = m["holders"] - records[1]["holders"]
            else:
                changes[sid] = 0
        else:
            changes[sid] = 0
    return changes

# ============================================================
# Top5 綜合狀態欄位
# ============================================================
def build_top5_status(sid, rankings):
    status = []
    for label, df in rankings.items():
        if df is not None and not df.empty and sid in df["股票代號"].values:
            rank = df[df["股票代號"] == sid]["排名"].iloc[0]
            status.append(f"{label}Top{rank}")
    return status

# ============================================================
# 整合每日主資料表
# ============================================================
def build_daily_table(date_str, df_inst, df_foreign, df_trust,
                      df_margin, prices, tdcc_metrics, tdcc_changes,
                      rankings):
    # 合併所有出現的股票代號
    all_ids = set()
    for df in [df_inst, df_foreign, df_trust, df_margin]:
        if df is not None and not df.empty:
            all_ids.update(df["股票代號"].tolist())

    rows = []
    for sid in all_ids:
        row = {"date": date_str, "stock_id": sid, "stock_name": ""}

        # 三大法人
        if df_inst is not None and not df_inst.empty:
            r = df_inst[df_inst["股票代號"] == sid]
            if not r.empty:
                row["stock_name"]  = r.iloc[0].get("股票名稱", "")
                row["foreign_net"] = float(r.iloc[0].get("外資買賣超", 0)) / 1000
                row["trust_net"]   = float(r.iloc[0].get("投信買賣超", 0)) / 1000
                row["dealer_net"]  = float(r.iloc[0].get("自營商買賣超", 0)) / 1000
                row["inst_total"]  = float(r.iloc[0].get("三大合計", 0)) / 1000

        # 融資融券
        if df_margin is not None and not df_margin.empty:
            r = df_margin[df_margin["股票代號"] == sid]
            if not r.empty:
                row["margin_buy"]      = float(r.iloc[0].get("融資增減", 0))
                row["margin_sell"]     = float(r.iloc[0].get("融券增減", 0))
                row["short_ratio_pct"] = float(r.iloc[0].get("券資比%", 0))

        # 集保
        if sid in tdcc_metrics:
            m = tdcc_metrics[sid]
            row["tdcc_holders"]         = m["holders"]
            row["tdcc_big_small_ratio"] = m["big_small_ratio"]
        row["tdcc_week_change"] = tdcc_changes.get(sid, 0)

        # 股價 T-1/T-2/T-3
        p = prices.get(sid, {})
        for i in range(1, 4):
            row[f"t{i}_open"]  = p.get(f"t{i}_open")
            row[f"t{i}_close"] = p.get(f"t{i}_close")

        # Top5 狀態
        row["top5_status"] = json.dumps(
            build_top5_status(sid, rankings), ensure_ascii=False
        )

        rows.append(row)

    return pd.DataFrame(rows)

# ============================================================
# 主程式
# ============================================================
def run_analyze(date_str=None):
    init_db()

    if date_str is None:
        files = [f for f in os.listdir(DATA_DIR) if f.startswith("institutional_")]
        if not files:
            print("❌ 找不到資料，請先執行 fetch_data.py")
            return
        date_str = sorted(files)[-1].replace("institutional_","").replace(".csv","")

    print(f"\n{'='*50}")
    print(f"  分析日期：{date_str}")
    print(f"{'='*50}\n")

    # 載入所有資料
    df_inst    = load_csv("institutional", date_str)
    df_foreign = load_csv("foreign",       date_str)
    df_trust   = load_csv("trust",         date_str)
    df_margin  = load_csv("margin",        date_str)
    prices     = load_json("prices.json")

    # 載入集保
    tdcc_path = os.path.join(DATA_DIR, "tdcc_history.json")
    tdcc_df   = None
    if os.path.exists(tdcc_path):
        from fetch_tdcc import fetch_tdcc
        import urllib3; urllib3.disable_warnings()
        tdcc_df, tdcc_date = fetch_tdcc()

    tdcc_metrics = calc_tdcc_metrics(tdcc_df, date_str) if tdcc_df is not None else {}
    tdcc_changes = calc_tdcc_week_change(tdcc_metrics)

    if df_inst is None:
        print("❌ 找不到三大法人資料")
        return

    # 產生六個榜單
    inst_buy     = make_top(df_inst,    "三大合計",   TOP_N, ascending=False)
    inst_sell    = make_top(df_inst,    "三大合計",   TOP_N, ascending=True)
    foreign_buy  = make_top(df_foreign, "買賣超股數", TOP_N, ascending=False)
    foreign_sell = make_top(df_foreign, "買賣超股數", TOP_N, ascending=True)
    trust_buy    = make_top(df_trust,   "買賣超股數", TOP_N, ascending=False)
    trust_sell   = make_top(df_trust,   "買賣超股數", TOP_N, ascending=True)

    rankings = {
        "三大法人買超": inst_buy,   "三大法人賣超": inst_sell,
        "外資買超":    foreign_buy, "外資賣超":    foreign_sell,
        "投信買超":    trust_buy,   "投信賣超":    trust_sell,
    }

    # 寫入榜單歷史
    for rtype, df_r in rankings.items():
        if not df_r.empty:
            upsert_ranking(date_str, rtype, df_r)

    # 連三日警示
    buy_alerts, sell_alerts = get_consecutive_alerts(date_str)

    # 整合每日主資料表
    daily_df = build_daily_table(
        date_str, df_inst, df_foreign, df_trust,
        df_margin, prices, tdcc_metrics, tdcc_changes, rankings
    )
    upsert_daily(daily_df)

    # 集保綜合訊號
    combined_signals = []
    decreasing_ids   = {sid for sid, chg in tdcc_changes.items() if chg < 0}
    buy_ids          = set()
    for df_r in [inst_buy, foreign_buy, trust_buy]:
        if not df_r.empty:
            buy_ids.update(df_r["股票代號"].tolist())

    for sid in buy_ids & decreasing_ids:
        name    = daily_df[daily_df["stock_id"] == sid]["stock_name"].iloc[0] if sid in daily_df["stock_id"].values else ""
        appears = build_top5_status(sid, rankings)
        tdcc_m  = tdcc_metrics.get(sid, {})
        combined_signals.append({
            "股票代號": sid, "股票名稱": name,
            "出現榜單": appears,
            "最新戶數": tdcc_m.get("holders", 0),
            "戶數變化": tdcc_changes.get(sid, 0),
        })

    # 印出榜單
    def print_top(label, df):
        print(f"\n{label}：")
        if df is None or df.empty:
            print("  無資料"); return
        for _, r in df.iterrows():
            vol  = r["買賣超張數"]
            sign = "+" if vol >= 0 else ""
            print(f"  {r['排名']}. {r['股票代號']} {r['股票名稱']}  {sign}{vol:,} 張")

    for label, df_r in rankings.items():
        print_top(label, df_r)

    if buy_alerts:
        print(f"\n🚨 連三日買超：{[a['股票名稱'] for a in buy_alerts]}")
    if sell_alerts:
        print(f"\n🚨 連三日賣超：{[a['股票名稱'] for a in sell_alerts]}")
    if combined_signals:
        print(f"\n⚡ 綜合訊號（兩燈亮）：{[s['股票名稱'] for s in combined_signals]}")

    # 存 result.json
    def df_to_list(df):
        if df is None or df.empty: return []
        return df[["排名","股票代號","股票名稱","買賣超張數"]].to_dict(orient="records")

    result = {
        "更新時間":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "資料日期":    date_str,
        "三大法人買超": df_to_list(inst_buy),
        "三大法人賣超": df_to_list(inst_sell),
        "外資買超":    df_to_list(foreign_buy),
        "外資賣超":    df_to_list(foreign_sell),
        "投信買超":    df_to_list(trust_buy),
        "投信賣超":    df_to_list(trust_sell),
        "連三日買超":  buy_alerts,
        "連三日賣超":  sell_alerts,
        "綜合訊號":    combined_signals,
    }

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 抓股價
    try:
        from fetch_price import fetch_prices_from_result
        fetch_prices_from_result()
    except Exception as e:
        print(f"⚠️  股價抓取失敗：{e}")

    print(f"\n✅ 分析完成，結果已存至 {RESULT_FILE}")
    return result

if __name__ == "__main__":
    run_analyze()