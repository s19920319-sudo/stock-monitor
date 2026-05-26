import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ============================================================
# 設定區 — 請填入你的資訊
# ============================================================
GMAIL_USER     = "yhaojan@gmail.com"        # 寄件者
GMAIL_PASSWORD = "kninzslsnatgbmrq"        # 應用程式密碼（16碼）
NOTIFY_TO      = "yhaojan@gmail.com"        # 收件者（可以跟寄件者一樣）

RESULT_FILE = os.path.join("data", "result.json")

# ============================================================
# 讀取分析結果
# ============================================================
def load_result():
    if not os.path.exists(RESULT_FILE):
        print("❌ 找不到 result.json，請先執行 analyzer.py")
        return None
    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# 建立 Email 內容（HTML 格式）
# ============================================================
def build_email(data):
    date    = data.get("資料日期", "—")
    updated = data.get("更新時間", "—")

    buy_alerts  = data.get("連三日買超", [])
    sell_alerts = data.get("連三日賣超", [])

    def table_rows(items):
        if not items:
            return "<tr><td colspan='3' style='color:#999;text-align:center'>今日無資料</td></tr>"
        rows = ""
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        for i, r in enumerate(items):
            vol  = r.get("買賣超張數", 0)
            sign = "+" if vol >= 0 else ""
            color = "#1a7a3f" if vol >= 0 else "#c0392b"
            rows += f"""
            <tr>
                <td style='padding:10px 16px'>{medals[i] if i < 5 else i+1}</td>
                <td style='padding:10px 16px'>
                    <b style='color:#b8860b'>{r.get('股票代號','')}</b>
                    {r.get('股票名稱','')}
                </td>
                <td style='padding:10px 16px;color:{color};font-weight:bold'>
                    {sign}{vol:,} 張
                </td>
            </tr>"""
        return rows

    def alert_section():
        all_alerts = buy_alerts + sell_alerts
        if not all_alerts:
            return ""
        tags = "".join([
            f"<span style='background:#fff3cc;border:1px solid #d4a017;color:#b8860b;"
            f"padding:4px 12px;border-radius:20px;margin:4px;display:inline-block;"
            f"font-weight:bold'>🔥 {a['股票代號']} {a['股票名稱']} ({a['類型']})</span>"
            for a in all_alerts
        ])
        return f"""
        <div style='background:#fff8e6;border-left:4px solid #d4a017;
                    border-radius:8px;padding:16px;margin-bottom:24px'>
            <div style='font-weight:bold;color:#b8860b;margin-bottom:10px'>
                🔔 連三日上榜警示
            </div>
            {tags}
        </div>"""

    def card(title, color, rows_html):
        return f"""
        <div style='background:#fff;border:1px solid #ddd;border-radius:10px;
                    margin-bottom:20px;overflow:hidden;border-top:3px solid {color}'>
            <div style='padding:12px 16px;font-weight:bold;color:{color};
                        background:{"#edf7f1" if color=="#1a7a3f" else "#fdf0ee" if color=="#c0392b" else "#eef4ff" if color=="#2563eb" else "#fdf4ff"}'>
                {title}
            </div>
            <table style='width:100%;border-collapse:collapse'>
                <thead>
                    <tr style='background:#faf8f4;font-size:12px;color:#8a7a66'>
                        <th style='padding:8px 16px;text-align:left'>排名</th>
                        <th style='padding:8px 16px;text-align:left'>股票</th>
                        <th style='padding:8px 16px;text-align:left'>張數</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>"""

    html = f"""
    <html><body style='font-family:Arial,sans-serif;background:#f5f0e8;padding:20px'>
    <div style='max-width:600px;margin:0 auto'>

        <!-- Header -->
        <div style='background:#2c2416;padding:20px;border-radius:10px 10px 0 0;
                    border-bottom:3px solid #d4a017;margin-bottom:20px'>
            <h2 style='color:#f5f0e8;margin:0'>📊 台股籌碼監控助理</h2>
            <p style='color:#a89880;margin:6px 0 0'>
                資料日期：{date} ｜ 更新時間：{updated}
            </p>
        </div>

        {alert_section()}

        {card("📈 外資買超前五",     "#1a7a3f", table_rows(data.get("外資買超",[])))}
        {card("📉 外資賣超前五",     "#c0392b", table_rows(data.get("外資賣超",[])))}
        {card("🏦 三大法人買超前五", "#2563eb", table_rows(data.get("三大法人買超",[])))}
        {card("🏦 三大法人賣超前五", "#9333ea", table_rows(data.get("三大法人賣超",[])))}
        {card("📈 投信買超前五",     "#1a7a3f", table_rows(data.get("投信買超",[])))}
        {card("📉 投信賣超前五",     "#c0392b", table_rows(data.get("投信賣超",[])))}

        <p style='text-align:center;color:#8a7a66;font-size:12px;margin-top:20px'>
            資料來源：台灣證券交易所 TWSE<br>
            此為自動發送通知，請勿回覆
        </p>
    </div>
    </body></html>
    """
    return html

# ============================================================
# 發送 Email
# ============================================================
def send_email(data):
    subject = f"【台股籌碼助理】{data.get('資料日期','')} 每日籌碼報告"

    buy_alerts  = data.get("連三日買超", [])
    sell_alerts = data.get("連三日賣超", [])
    if buy_alerts or sell_alerts:
        names = [a["股票名稱"] for a in buy_alerts + sell_alerts]
        subject += f" 🔥 {' / '.join(names)} 連三日上榜！"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_TO
    msg.attach(MIMEText(build_email(data), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_USER, NOTIFY_TO, msg.as_string())
        print(f"✅ Email 已發送至 {NOTIFY_TO}")
        return True
    except Exception as e:
        print(f"❌ 發送失敗：{e}")
        return False

# ============================================================
# 主程式
# ============================================================
if __name__ == "__main__":
    print("📧 準備發送籌碼日報...")
    data = load_result()
    if data:
        send_email(data)