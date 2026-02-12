from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import urllib.parse
import csv  # 👈 新增：用於處理 CSV 檔案
import os   # 👈 新增：用於檢查檔案是否存在
from datetime import datetime  # 👈 新增：用於記錄報修時間

app = FastAPI(title="弱電行報修系統 - 帶紀錄功能版")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 您的配置區 ---
LINE_ACCESS_TOKEN = "YHnxnfj1RtaU0gMVM2Lg+Qfddk2OP6a8+QxR1OEtnRDCSurtLI7YsKJwUYCuN3QrNTaBjFNEWbpqBCRZhng8L1eFasx6lLD0WyCWaWa33rK3itFapAL0LlYo/tZ5oiPrB/R9vaL60Y3TvkpjO7OSYgdB04t89/1O/w1cDnyilFU="
MY_USER_ID = "U880f67efbce127d75ef85bd3d4a621a5"
CSV_FILE = "orders.csv"  # 👈 定義紀錄檔名稱

class RepairOrder(BaseModel):
    customer_name: str
    phone: str
    address: str
    issue_type: str
    description: str

def save_to_csv(order: RepairOrder):
    """
    將報修資料存入 CSV 檔案。
    """
    file_exists = os.path.isfile(CSV_FILE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # 取得目前時間
    
    # 使用 utf-8-sig 編碼，確保 Excel 打開不會亂碼
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        # 如果是新檔案，先寫入標題列
        if not file_exists:
            writer.writerow(["報修時間", "客戶姓名", "電話", "地址", "報修項目", "故障描述"])
        
        # 寫入資料列
        writer.writerow([
            now, 
            order.customer_name, 
            order.phone, 
            order.address, 
            order.issue_type, 
            order.description
        ])

@app.post("/submit_repair")
async def handle_repair(order: RepairOrder):
    # 1. 先將資料存入 CSV 紀錄檔
    try:
        save_to_csv(order)
        print(f"📁 已將 {order.customer_name} 的工單存入 {CSV_FILE}")
    except Exception as e:
        print(f"❌ 存檔失敗: {e}")

    # 2. 處理 LINE 訊息 (與之前相同)
    push_url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN.strip()}"
    }

    clean_phone = order.phone.replace("-", "").replace(" ", "").strip()
    encoded_address = urllib.parse.quote(order.address)
    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"

    flex_contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": "🚨 弱電維修派工單", "weight": "bold", "size": "lg", "color": "#ffffff"}],
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
        "messages": [{"type": "flex", "altText": "🚨 新工單紀錄中", "contents": flex_contents}]
    }

    response = requests.post(push_url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"✅ LINE 訊息與 CSV 紀錄皆完成")
    else:
        print(f"❌ LINE 失敗但 CSV 已儲存: {response.text}")
    
    return {"status": "success", "saved": True}