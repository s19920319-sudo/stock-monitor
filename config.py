import os

# ============================================================
# 路徑設定
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH  = os.path.join(DATA_DIR, "stock.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================================
# Email 設定（請填入你的資訊）
# ============================================================
GMAIL_USER     = "yhaojan@gmail.com"
GMAIL_PASSWORD = "kninzslsnatgbmrq"
NOTIFY_TO      = "yhaojan@gmail.com"

# ============================================================
# 分析參數
# ============================================================
TOP_N          = 5     # 榜單前幾名
CONSEC_DAYS    = 3     # 連幾日上榜觸發警示
TDCC_WEEKS     = 2     # 集保連幾週減少觸發警示
INST_RATIO_THR = 12.0  # 投信持股比率警示門檻（%）

# ============================================================
# HTTP Headers
# ============================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/"
}