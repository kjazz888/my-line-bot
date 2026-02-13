import os
import requests
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 設定跨網域 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 從環境變數讀取敏感資訊
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN") or os.getenv("LINE_ACCESS_TOKEN")
GOOGLE_URL = os.getenv("GOOGLE_URL")
MY_USER_ID = os.getenv("MY_USER_ID")

@app.get("/")
def home():
    """首頁測試用"""
    return {"message": "專業弱電工單系統 - 森林綠科技版運行中"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        # 接收前端 JSON
        data = await request.json()
        
        # --- 步驟 1: Google reCAPTCHA 驗證 ---
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token},
            timeout=5
        ).json()

        if not verify_res.get("success"):
            print("❌ 機器人驗證失敗")
            return {"status": "fail", "message": "機器人驗證失敗"}

        # --- 步驟 2: 整理資料 ---
        customer_name = data.get("customer_name", "未提供")
        phone = data.get("phone", "未提供")
        address = data.get("address", "未提供")
        issue_type = data.get("issue_type", "未提供")
        description = data.get("description", "無詳細內容")

        # 生成地圖與撥號網址
        encoded_address = urllib.parse.quote(address)
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"
        phone_url = f"tel:{phone}"

        # --- 步驟 3: 同步到 Google 表格 (超時保護) ---
        if GOOGLE_URL:
            try:
                requests.post(GOOGLE_URL, json=data, timeout=15)
                print("✅ Google 表格同步完成")
            except Exception as e:
                print(f"⚠️ Google 同步異常: {e}")

        # --- 步驟 4: 發送 LINE 專業版 Flex Message ---
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
                        "type": "flex",
                        "altText": f"🛠️ 新進工單：{customer_name}",
                        "contents": {
                            "type": "bubble",
                            "styles": {
                                "header": {"backgroundColor": "#081C15"},
                                "footer": {"separator": True, "backgroundColor": "#F8F9FA"}
                            },
                            "header": {
                                "type": "box", "layout": "vertical",
                                "contents": [
                                    {"type": "text", "text": "數位弱電工程服務", "color": "#95D5B2", "size": "xs", "weight": "bold", "letterSpacing": "2px"},
                                    {"type": "text", "text": "派遣工單：待處理", "weight": "bold", "color": "#ffffff", "size": "lg", "margin": "sm"}
                                ]
                            },
                            "body": {
                                "type": "box", "layout": "vertical", "spacing": "lg",
                                "contents": [
                                    {
                                        "type": "box", "layout": "horizontal",
                                        "contents": [
                                            {"type": "text", "text": "👤 客戶姓名", "color": "#888888", "size": "sm", "flex": 2},
                                            {"type": "text", "text": customer_name, "weight": "bold", "size": "sm", "color": "#1B4332", "flex": 5}
                                        ]
                                    },
                                    {
                                        "type": "box", "layout": "horizontal", "verticalAlign": "center",
                                        "contents": [
                                            {"type": "text", "text": "📞 聯絡電話", "color": "#888888", "size": "sm", "flex": 2},
                                            {
                                                "type": "text", 
                                                "text": phone, 
                                                "weight": "bold", 
                                                "size": "sm", 
                                                "color": "#2D6A4F", 
                                                "flex": 5,
                                                "action": {
                                                    "type": "uri",
                                                    "label": "撥打電話",
                                                    "uri": phone_url
                                                },
                                                "decoration": "underline"
                                            }
                                        ]
                                    },
                                    {"type": "separator"},
                                    {
                                        "type": "box", "layout": "vertical", "spacing": "xs",
                                        "contents": [
                                            {"type": "text", "text": "📍 現場地址", "color": "#888888", "size": "xs", "weight": "bold"},
                                            {"type": "text", "text": address, "wrap": True, "size": "sm", "color": "#333333"}
                                        ]
                                    },
                                    {
                                        "type": "box", "layout": "vertical", "spacing": "xs",
                                        "contents": [
                                            {"type": "text", "text": "🔧 報修項目", "color": "#888888", "size": "xs", "weight": "bold"},
                                            {"type": "text", "text": f"【{issue_type}】", "size": "sm", "color": "#081C15", "weight": "bold"},
                                            {"type": "text", "text": description, "wrap": True, "size": "xs", "color": "#666666", "margin": "xs"}
                                        ]
                                    }
                                ]
                            },
                            "footer": {
                                "type": "box", "layout": "vertical",
                                "contents": [
                                    {
                                        "type": "button",
                                        "style": "primary",
                                        "color": "#1B4332",
                                        "action": {
                                            "type": "uri",
                                            "label": "🌐 開啟衛星導航",
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
