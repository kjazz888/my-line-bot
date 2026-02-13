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

# 環境變數讀取
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN") or os.getenv("LINE_ACCESS_TOKEN")
GOOGLE_URL = os.getenv("GOOGLE_URL")
MY_USER_ID = os.getenv("MY_USER_ID")

@app.get("/")
def home():
    return {"message": "專業弱電工單系統 - 森林綠科技版"}

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        data = await request.json()
        
        # 1. 機器人驗證
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token}
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "驗證失敗"}

        # 2. 整理資料
        customer_name = data.get("customer_name", "未提供")
        phone = data.get("phone", "未提供")
        address = data.get("address", "未提供")
        issue_type = data.get("issue_type", "未提供")
        description = data.get("description", "無詳細內容")

        # 生成地圖與撥號網址
        encoded_address = urllib.parse.quote(address)
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"
        phone_url = f"tel:{phone}" # 撥號連結

        # 3. 同步 Google 表格
        if GOOGLE_URL:
            try:
                requests.post(GOOGLE_URL, json=data, timeout=15)
                print("✅ Google 表格同步完成")
            except:
                print("⚠️ Google 同步超時，略過")

        # 4. 發送專業版 LINE Flex Message (含撥號功能)
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
                                                "decoration": "underline" # 加上底線提示可點擊
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
                                            {"type": "text", "text": f"【{issue_type}
