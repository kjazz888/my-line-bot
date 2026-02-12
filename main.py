import os
import requests
import urllib.parse
import csv
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- 1. 環境變數讀取 ---
# 在 Render 後台設定 LINE_ACCESS_TOKEN 與 MY_USER_ID
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN", "MISSING_TOKEN")
MY_USER_ID = os.getenv("MY_USER_ID", "MISSING_ID")

app = FastAPI(title="弱電維修雲端系統")

# --- 2. 跨網域設定 (讓網頁能連線) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RepairOrder(BaseModel):
    customer_name: str
    phone: str
    address: str
    issue_type: str
    description: str

def save_to_csv(order: RepairOrder):
    """
    在雲端環境儲存 CSV (注意：Render 免費版重啟後檔案會消失)
    """
    csv_file = "orders.csv"
    file_exists = os.path.isfile(csv_file)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["報修時間", "客戶姓名", "電話", "地址", "報修項目", "故障描述"])
        writer.writerow([now, order.customer_name, order.phone, order.address, order.issue_type, order.description])

@app.get("/")
def home():
    return {"status": "running", "token_check": "OK" if LINE_ACCESS_TOKEN != "MISSING_TOKEN" else "Missing Token"}

# 在 main.py 的配置區 (或是 handle_repair 函式裡面) 加入
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycby6TckctibsC6Y3YzvW6xqi1iIWhHn5Y_Hhh7FlZ3-SESLXJw22p4aFGz3vGYvJ6_uV/exec"

@app.post("/submit_repair")
async def handle_repair(order: RepairOrder):
    # --- 1. 原有的 CSV 存檔 (選擇性保留) ---
    save_to_csv(order)
    
    # --- 2. 核心：將資料傳送到 Google Sheets ---
    try:
        # 將 Pydantic 模型轉為字典，傳送給 Google
        gs_response = requests.post(
            GOOGLE_SCRIPT_URL, 
            json=order.dict(), 
            timeout=10
        )
        if gs_response.status_code == 200:
            print("✅ 成功同步至 Google 表格")
        else:
            print(f"⚠️ Google 表格回應異常: {gs_response.status_code}")
    except Exception as e:
        print(f"❌ 無法連線至 Google 表格: {e}")

    # --- 3. 發送 LINE 訊息 ---
    # ... (原本發送 LINE 的程式碼)
    
    # 格式化資料
    clean_phone = order.phone.replace("-", "").replace(" ", "").strip()
    encoded_address = urllib.parse.quote(order.address)
    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"

    # LINE Flex Message 結構
    flex_contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": "🚨 雲端派工單", "weight": "bold", "size": "lg", "color": "#ffffff"}],
            "backgroundColor": "#E63946"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"👤 客戶：{order.customer_name}", "weight": "bold", "size": "md"},
                {"type": "text", "text": f"🔧 項目：{order.issue_type}", "color": "#1D3557", "size": "sm", "margin": "md"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": f"📍 地址：{order.address}", "wrap": True, "size": "sm", "margin": "md"},
                {"type": "text", "text": f"📝 詳情：{order.description}", "wrap": True, "size": "sm", "margin": "md"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#457B9D", "action": {"type": "uri", "label": "📞 撥打電話", "uri": f"tel:{clean_phone}"}},
                {"type": "button", "style": "secondary", "action": {"type": "uri", "label": "📍 開啟導航", "uri": google_maps_url}}
            ]
        }
    }

    payload = {
        "to": MY_USER_ID,
        "messages": [{"type": "flex", "altText": "🚨 您有新的維修派工單", "contents": flex_contents}]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }

    response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
    
    return {"status": "success", "line_code": response.status_code}


