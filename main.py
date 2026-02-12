import os
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 初始化 FastAPI
app = FastAPI()

# 允許跨網域請求 (讓 GitHub Pages 可以呼叫 Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 從環境變數讀取配置 (請在 Render 後台設定)
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN")
GOOGLE_URL = os.getenv("GOOGLE_URL")

@app.get("/")
def home():
    return {"message": "報修系統後端運行中"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        data = await request.json()
        
        # --- Step 1: Google reCAPTCHA 驗證 ---
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                'secret': RECAPTCHA_SECRET,
                'response': captcha_token
            }
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "機器人驗證失敗"}

        # --- Step 2: 整理報修資料 ---
        customer_name = data.get("customer_name")
        phone = data.get("phone")
        address = data.get("address")
        issue_type = data.get("issue_type")
        description = data.get("description", "無詳細描述")

        payload = {
            "customer_name": customer_name,
            "phone": phone,
            "address": address,
            "issue_type": issue_type,
            "description": description
        }

        # --- Step 3: 同步寫入 Google Sheets ---
        if GOOGLE_URL:
            try:
                requests.post(GOOGLE_URL, json=payload, timeout=5)
            except Exception as e:
                print(f"Google Sheets 寫入失敗: {e}")

        # --- Step 4: 發送 LINE Flex Message 通知 (專業紅色卡片) ---
        if LINE_TOKEN:
            line_api_url = "https://api.line.me/v2/bot/message/broadcast"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}"
            }
            
            flex_message = {
                "messages": [{
                    "type": "flex",
                    "altText": f"🛠️ 新報修單: {customer_name}",
                    "contents": {
                        "type": "bubble",
                        "styles": {"header": {"backgroundColor": "#E63946"}},
                        "header": {
                            "type": "box", "layout": "vertical",
                            "contents": [{"type": "text", "text": "🚨 收到新報修單", "weight": "bold", "color": "#ffffff", "size": "lg"}]
                        },
                        "body": {
                            "type": "box", "layout": "vertical", "spacing": "md",
                            "contents": [
                                {"type": "text", "text": f"客戶：{customer_name}", "weight": "bold", "size": "md"},
                                {"type": "text", "text": f"電話：{phone}", "size": "sm", "color": "#1D3557"},
                                {"type": "separator"},
                                {"type": "text", "text": f"地址：{address}", "wrap": True, "size": "sm"},
                                {"type": "text", "text": f"項目：{issue_type}", "size": "sm", "color": "#E63946", "weight": "bold"},
                                {"type": "text", "text": f"狀況：{description}", "wrap": True, "size": "xs", "color": "#666666"}
                            ]
                        }
                    }
                }]
            }
            requests.post(line_api_url, headers=headers, json=flex_message)

        return {"status": "success", "message": "報修已送出"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

