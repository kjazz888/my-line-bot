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
    return {"message": "專業弱電工單系統 - 格式修正版"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        data = await request.json()
        
        # 1. 驗證
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token},
            timeout=5
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "驗證失敗"}

        # 2. 整理資料 (確保無 None 值)
        customer_name = str(data.get("customer_name", "客戶"))
        phone = str(data.get("phone", "無電話"))
        address = str(data.get("address", "無地址"))
        issue_type = str(data.get("issue_type", "維修"))
        description = str(data.get("description", "-"))

        # --- 強化的網址處理 ---
        # 導航改用 Google Maps 官方推薦的 Universal Link
        clean_address = address.replace("\n", " ").strip()
        encoded_address = urllib.parse.quote(clean_address)
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        
        # 電話號碼只保留數字，避免 tel: 連結出錯
        clean_phone = "".join(filter(str.isdigit, phone))
        phone_url = f"tel:{clean_phone}" if clean_phone else "tel:000"

        # 3. 同步 Google (非同步概念，不擋後續動作)
        if GOOGLE_URL:
            try:
                requests.post(GOOGLE_URL, json=data, timeout=5)
            except:
                pass

        # 4. 發送 LINE (結構優化)
        if LINE_TOKEN and MY_USER_ID:
            line_api_url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}"
            }
            
            # 使用更穩定的 Flex 結構，移除可能衝突的 decoration
            message_packet = {
                "to": MY_USER_ID,
                "messages": [
                    {
                        "type": "flex",
                        "altText": f"新工單-{customer_name}",
                        "contents": {
                            "type": "bubble",
                            "styles": {
                                "header": {"backgroundColor": "#0B251F"},
                                "footer": {"backgroundColor": "#F0F0F0"}
                            },
                            "header": {
                                "type": "box", "layout": "vertical",
                                "contents": [
                                    {"type": "text", "text": "數位弱電工程服務", "color": "#95D5B2", "size": "xs", "weight": "bold"},
                                    {"type": "text", "text": "派遣工單：待處理", "weight": "bold", "color": "#ffffff", "size": "lg", "margin": "sm"}
                                ]
                            },
                            "body": {
                                "type": "box", "layout": "vertical", "spacing": "md",
                                "contents": [
                                    {
                                        "type": "box", "layout": "horizontal",
                                        "contents": [
                                            {"type": "text", "text": "👤 客戶", "color": "#888888", "size": "sm", "flex": 2},
                                            {"type": "text", "text": customer_name, "weight": "bold", "size": "sm", "color": "#1B4332", "flex": 5}
                                        ]
                                    },
                                    {
                                        "type": "box", "layout": "horizontal",
                                        "contents": [
                                            {"type": "text", "text": "📞 電話", "color": "#888888", "size": "sm", "flex": 2},
                                            {"type": "text", "text": phone, "weight": "bold", "size": "sm", "color": "#2D6A4F", "flex": 5, "action": {"type": "uri", "label": "Call", "uri": phone_url}}
                                        ]
                                    },
                                    {"type": "separator"},
                                    {
                                        "type": "box", "layout": "vertical", "contents": [
                                            {"type": "text", "text": "📍 現場地址", "color": "#888888", "size": "xs", "weight": "bold"},
                                            {"type": "text", "text": address, "wrap": True, "size": "sm", "color": "#333333"}
                                        ]
                                    },
                                    {
                                        "type": "box", "layout": "vertical", "contents": [
                                            {"type": "text", "text": "🔧 報修項目", "color": "#888888", "size": "xs", "weight": "bold"},
                                            {"type": "text", "text": f"【{issue_type}】", "size": "sm", "color": "#081C15", "weight": "bold"},
                                            {"type": "text", "text": description, "wrap": True, "size": "xs", "color": "#666666"}
                                        ]
                                    }
                                ]
                            },
                            "footer": {
                                "type": "box", "layout": "vertical",
                                "contents": [
                                    {
                                        "type": "button", "style": "primary", "color": "#1B4332",
                                        "action": {
                                            "type": "uri", "label": "🌐 開啟衛星導航", "uri": google_maps_url
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
            res = requests.post(line_api_url, headers=headers, json=message_packet)
            print(f">>> LINE 發送結果: {res.status_code}")
            if res.status_code != 200:
                print(f">>> LINE 報錯內容: {res.text}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return {"status": "error"}
