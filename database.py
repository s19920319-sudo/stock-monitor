import sqlite3
import pandas as pd
import os
from config import DB_PATH

# ============================================================
# 建立資料庫與所有資料表
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ── 每日主資料表 ──────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_report (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        date                  TEXT NOT NULL,
        stock_id              TEXT NOT NULL,
        stock_name            TEXT,

        -- 三大法人
        foreign_net           REAL DEFAULT 0,
        trust_net             REAL DEFAULT 0,
        dealer_net            REAL DEFAULT 0,
        inst_total            REAL DEFAULT 0,
        trust_ratio_pct       REAL DEFAULT 0,
        trust_ratio_alert     INTEGER DEFAULT 0,  -- 1=超過12%

        -- 集保結構
        tdcc_holders          INTEGER DEFAULT 0,
        tdcc_week_change      INTEGER DEFAULT 0,
        tdcc_big_small_ratio  REAL DEFAULT 0,     -- 大戶%－散戶%變動

        -- 融資融券
        margin_buy            REAL DEFAULT 0,
        margin_sell           REAL DEFAULT 0,
        short_ratio_pct       REAL DEFAULT 0,     -- 券資比%

        -- 股價（T-1/T-2/T-3）
        t1_open   REAL, t1_close REAL,
        t2_open   REAL, t2_close REAL,
        t3_open   REAL, t3_close REAL,

        -- Top5 狀態（JSON字串）
        top5_status           TEXT DEFAULT '[]',

        -- 時間戳
        created_at            TEXT DEFAULT (datetime('now','localtime')),

        UNIQUE(date, stock_id)
    )""")

    # ── 集保歷史表 ────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS tdcc_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        stock_id    TEXT NOT NULL,
        holders     INTEGER DEFAULT 0,
        big_pct     REAL DEFAULT 0,   -- 1000張以上大戶持股%
        small_pct   REAL DEFAULT 0,   -- 10張以下散戶持股%
        UNIQUE(date, stock_id)
    )""")

    # ── 榜單歷史表（連N日判斷用）────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS ranking_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        stock_id    TEXT NOT NULL,
        stock_name  TEXT,
        rank_type   TEXT NOT NULL,   -- 'inst_buy','inst_sell','foreign_buy'...
        rank_no     INTEGER,
        net_vol     REAL,
        UNIQUE(date, stock_id, rank_type)
    )""")

    conn.commit()
    conn.close()
    print("✅ 資料庫初始化完成")

# ============================================================
# 寫入每日主資料（Upsert）
# ============================================================
def upsert_daily(df: pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    rows = df.to_dict(orient="records")
    c    = conn.cursor()

    for r in rows:
        cols = ", ".join(r.keys())
        vals = ", ".join(["?" for _ in r])
        upd  = ", ".join([f"{k}=excluded.{k}" for k in r.keys()])
        sql  = f"""
        INSERT INTO daily_report ({cols}) VALUES ({vals})
        ON CONFLICT(date, stock_id) DO UPDATE SET {upd}
        """
        c.execute(sql, list(r.values()))

    conn.commit()
    conn.close()
    print(f"✅ 寫入 daily_report：{len(rows)} 筆")

# ============================================================
# 寫入榜單歷史
# ============================================================
def upsert_ranking(date_str, rank_type, df_rank):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    for _, r in df_rank.iterrows():
        c.execute("""
        INSERT INTO ranking_history (date, stock_id, stock_name, rank_type, rank_no, net_vol)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(date, stock_id, rank_type) DO UPDATE SET
            rank_no=excluded.rank_no, net_vol=excluded.net_vol
        """, (date_str, r.get("股票代號",""), r.get("股票名稱",""),
              rank_type, int(r.get("排名",0)), float(r.get("買賣超張數",0))))

    conn.commit()
    conn.close()

# ============================================================
# 寫入集保歷史
# ============================================================
def upsert_tdcc(date_str, rows):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    for r in rows:
        c.execute("""
        INSERT INTO tdcc_history (date, stock_id, holders, big_pct, small_pct)
        VALUES (?,?,?,?,?)
        ON CONFLICT(date, stock_id) DO UPDATE SET
            holders=excluded.holders,
            big_pct=excluded.big_pct,
            small_pct=excluded.small_pct
        """, (date_str, r["stock_id"], r["holders"], r["big_pct"], r["small_pct"]))

    conn.commit()
    conn.close()

# ============================================================
# 查詢：取得某股票最近N天的歷史資料
# ============================================================
def query_stock_history(stock_id, days=30):
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql("""
        SELECT * FROM daily_report
        WHERE stock_id = ?
        ORDER BY date DESC LIMIT ?
    """, conn, params=(stock_id, days))
    conn.close()
    return df

# ============================================================
# 查詢：取得某日所有股票資料
# ============================================================
def query_daily(date_str):
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql("""
        SELECT * FROM daily_report WHERE date = ?
        ORDER BY inst_total DESC
    """, conn, params=(date_str,))
    conn.close()
    return df

# ============================================================
# 查詢：連N日上榜判斷
# ============================================================
def query_consecutive(rank_type, days=3):
    conn   = sqlite3.connect(DB_PATH)
    # 取最近 days 個不重複交易日
    dates  = pd.read_sql("""
        SELECT DISTINCT date FROM ranking_history
        WHERE rank_type=? ORDER BY date DESC LIMIT ?
    """, conn, params=(rank_type, days))

    if len(dates) < days:
        conn.close()
        return []

    target_dates = tuple(dates["date"].tolist())
    placeholder  = ",".join(["?" for _ in target_dates])

    df = pd.read_sql(f"""
        SELECT stock_id, stock_name, COUNT(DISTINCT date) as cnt
        FROM ranking_history
        WHERE rank_type=? AND date IN ({placeholder})
        GROUP BY stock_id
        HAVING cnt >= ?
    """, conn, params=(rank_type, *target_dates, days))

    conn.close()
    return df.to_dict(orient="records")

# ============================================================
if __name__ == "__main__":
    init_db()