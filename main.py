import os
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 初始化 FastAPI 應用程式
app = FastAPI()

# 設定跨網域 (CORS)，讓您的 GitHub Pages 網頁可以順利連線到 Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 從環境變數讀取敏感資訊 (請確保 Render 後台已設定這些 Key)
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN")
GOOGLE_URL = os.getenv("GOOGLE_URL")

@app.get("/")
def home():
    """首頁測試用，瀏覽器打開網址看到這行代表後端活著"""
    return {"message": "報修系統後端運行中 - 弱電工程專用"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        # 接收前端傳來的 JSON 資料
        data = await request.json()
        
        # --- 步驟 1: Google reCAPTCHA 機器人驗證 ---
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                'secret': RECAPTCHA_SECRET,
                'response': captcha_token
            }
        ).json()

        if not verify_res.get("success"):
            print("❌ 機器人驗證失敗")
            return {"status": "fail", "message": "機器人驗證失敗"}

        # --- 步驟 2: 整理資料變數 ---
        customer_name = data.get("customer_name", "未提供")
        phone = data.get("phone", "未提供")
        address = data.get("address", "未提供")
        issue_type = data.get("issue_type", "未提供")
        description = data.get("description", "無詳細內容")

        payload = {
            "customer_name": customer_name,
            "phone": phone,
            "address": address,
            "issue_type": issue_type,
            "description": description
        }

        # --- 步驟 3: 同步資料到 Google 表格 ---
        if GOOGLE_URL:
            try:
                g_res = requests.post(GOOGLE_URL, json=payload, timeout=5)
                print(f"✅ Google 表格同步結果: {g_res.status_code}")
            except Exception as e:
                print(f"❌ Google 表格寫入出錯: {e}")

        # --- 步驟 4: 發送 LINE 通知 ---
        if LINE_TOKEN:
            line_api_url = "https://api.line.me/v2/bot/message/broadcast"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}"
            }
            
            # 組合訊息包 (包含文字與 Flex 卡片)
            message_packet = {
                "messages": [
                    {
                        "type": "text",
                        "text": f"🛠️ 新報修單通知\n客戶：{customer_name}\n電話：{phone}\n項目：{issue_type}"
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
                            }
                        }
                    }
                ]
            }
            
            # 執行發送
            line_res = requests.post(line_api_url, headers=headers, json=message_packet)
            
            # --- 重要：在 Render Logs 印出 LINE 的真實反應 ---
            print(f">>> LINE 回應狀態碼: {line_res.status_code}")
            print(f">>> LINE 回應詳細內容: {line_res.text}")

        return {"status": "success", "message": "報修單已成功處理"}

    except Exception as e:
        print(f"❌ 程式發生意外錯誤: {str(e)}")
        return {"status": "error", "message": str(e)}
