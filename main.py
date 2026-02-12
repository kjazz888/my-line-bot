import os
import requests
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN") or os.getenv("LINE_ACCESS_TOKEN")
GOOGLE_URL = os.getenv("GOOGLE_URL")
MY_USER_ID = os.getenv("MY_USER_ID")

@app.get("/")
def home():
    return {"message": "報修系統運行中 - 已強化超時穩定性"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        data = await request.json()
        
        # --- 1. 機器人驗證 ---
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token}
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "機器人驗證失敗"}

        # --- 2. 整理資料 ---
        customer_name = data.get("customer_name", "未提供")
        phone = data.get("phone", "未提供")
        address = data.get("address", "未提供")
        issue_type = data.get("issue_type", "未提供")
        description = data.get("description", "無詳細內容")

        # 生成地圖網址
        encoded_address = urllib.parse.quote(address)
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"

        payload = {
            "customer_name": customer_name,
            "phone": phone,
            "address": address,
            "issue_type": issue_type,
            "description": description
        }

        # --- 3. 同步到 Google 表格 (加上錯誤保護) ---
        if GOOGLE_URL:
            try:
                # 延長等待到 15 秒，避免 Google Script 反應太慢
                g_res = requests.post(GOOGLE_URL, json=payload, timeout=15)
                print(f"✅ Google 表格同步結果: {g_res.status_code}")
            except Exception as e:
                # 即使 Google 掛掉，也只印出錯誤，讓程式繼續跑發送 LINE
                print(f"⚠️ Google 表格暫時無法同步，但不影響 LINE 發送。原因: {e}")

        # --- 4. 發送 LINE 通知 (含導航按鈕) ---
        if LINE_TOKEN and MY_USER_ID:
            line_api_url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}"
            }
            
            message_packet = {
                "to": MY_USER_ID,
                "messages": [
                    {
                        "type": "text",
                        "text": f"🛠️ 新報修單通知\n客戶：{customer_name}\n地址：{address}"
                    },
                    {
                        "type": "flex",
                        "altText": f"新報修單-{customer_name}",
                        "contents": {
                            "type": "bubble",
                            "styles": {"header": {"backgroundColor": "#E63946"}},
                            "header": {
                                "type": "box", "layout": "vertical",
                                "contents": [{"type": "text", "text": "🚨 收到新報修單", "weight": "bold", "color": "#ffffff", "size": "md"}]
                            },
                            "body": {
                                "type": "box", "layout": "vertical", "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": f"客戶姓名：{customer_name}", "weight": "bold", "size": "sm"},
                                    {"type": "text", "text": f"聯絡電話：{phone}", "size": "sm", "color": "#1D3557"},
                                    {"type": "separator", "margin": "md"},
                                    {"type": "text", "text": f"安裝地址：{address}", "wrap": True, "size": "sm"},
                                    {"type": "text", "text": f"報修項目：{issue_type}", "size": "sm", "color": "#E63946", "weight": "bold"},
                                    {"type": "text", "text": f"故障描述：{description}", "wrap": True, "size": "xs", "color": "#666666"}
                                ]
                            },
                            "footer": {
                                "type": "box", "layout": "vertical",
                                "contents": [
                                    {
                                        "type": "button",
                                        "style": "primary",
                                        "color": "#4361EE",
                                        "action": {
                                            "type": "uri",
                                            "label": "📍 開啟導航",
                                            "uri": google_maps_url
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
            line_res = requests.post(line_api_url, headers=headers, json=message_packet)
            print(f">>> LINE 發送結果: {line_res.status_code}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ 嚴重錯誤: {str(e)}")
        return {"status": "error", "message": str(e)}
