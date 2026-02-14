import os
import json
import requests
import urllib.parse
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    FlexSendMessage, PostbackEvent
)

# 初始化 FastAPI 應用
app = FastAPI()

# 跨域資源共享 (CORS) 設定，允許您的 GitHub 網頁呼叫此 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 環境變數設定 (請確保在 Render 的 Environment Variables 已設定) ---
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
LINE_TOKEN = os.getenv("LINE_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_URL = os.getenv("GOOGLE_URL")
MY_USER_ID = os.getenv("MY_USER_ID")  # 管理員(您自己)的 LINE UID

# 初始化 LINE SDK
line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- [自定義] Flex Message 範本庫 (森林綠風格) ---

def get_main_menu():
    """產生故障自檢主選單卡片，提供客戶選擇類別"""
    return {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#081C15",
            "contents": [{"type": "text", "text": "🛠️ 故障自檢中心", "color": "#ffffff", "weight": "bold", "size": "lg"}]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": "請選擇設備類型進行排除：", "size": "sm", "color": "#666666"},
                {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "message", "label": "📹 監視器系統", "text": "監視器自檢"}},
                {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "message", "label": "門禁系統", "text": "門禁自檢"}},
                {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "message", "label": "網路設備", "text": "網路自檢"}}
            ]
        }
    }

def get_device_flex(device_name, steps, image_url):
    """通用型設備排除卡片，將排除步驟動態生成"""
    return {
        "type": "bubble",
        "hero": {"type": "image", "url": image_url, "size": "full", "aspectRatio": "20:13", "aspectMode": "cover"},
        "body": {
            "type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": f"{device_name}排除建議", "weight": "bold", "size": "xl"},
                {"type": "box", "layout": "vertical", "margin": "lg", "spacing": "sm", "contents": [
                    # 修正：將步驟文字 (s) 正確映射到 Text 組件
                    {"type": "text", "text": s, "size": "sm", "color": "#444444", "wrap": True} for s in steps
                ]}
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "uri", "label": "🚨 還是不行，我要報修", "uri": "https://kjazz888.github.io/my-line-bot/"}},
                {"type": "button", "style": "link", "action": {"type": "message", "label": "返回主選單", "text": "故障自檢"}}
            ]
        }
    }

# --- [Endpoint] 1. LINE Webhook 處理器 ---

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    """接收 LINE 傳來的訊息並驗證簽名"""
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """根據客戶傳送的文字回覆對應的自檢卡片"""
    user_msg = event.message.text.strip()
    
    if user_msg == "故障自檢":
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="自檢中心", contents=get_main_menu()))
    
    elif "監視器" in user_msg:
        steps = ["1. 檢查主機後方風扇有無轉動 (確認電源)", "2. 確認電視是否切換至正確訊號源 (HDMI/VGA)", "3. 檢查變壓器插頭是否鬆脫"]
        img = "https://images.unsplash.com/photo-1557597774-9d2739f85a76?w=600"
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="監視器排除", contents=get_device_flex("監視器", steps, img)))

    elif "門禁" in user_msg:
        steps = ["1. 檢查感應主機電源燈是否亮起", "2. 確認電磁鎖有無異音或過熱現象", "3. 測試感應卡是否失效 (換一張試試)"]
        img = "https://images.unsplash.com/photo-1558002038-1055907df827?w=600"
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="門禁排除", contents=get_device_flex("門禁", steps, img)))

    elif "網路" in user_msg:
        steps = ["1. 將小烏龜或路由器電源撥掉，等10秒再重插", "2. 確認網路線插頭兩端綠燈是否有閃爍", "3. 檢查是否有欠費導致斷網"]
        img = "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=600"
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="網路排除", contents=get_device_flex("網路", steps, img)))

# --- [Endpoint] 2. 接收前端網頁表單提交 ---

@app.post("/submit_repair")
async def handle_repair(request: Request):
    """處理從 GitHub 網頁傳來的工單，並推播給管理員"""
    try:
        data = await request.json()
        
        # 1. Google reCAPTCHA 驗證 (防止惡意灌單)
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token},
            timeout=10
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "機器人驗證失敗"}

        # 2. 資料收集與格式化
        customer = str(data.get("customer_name", "客戶"))
        phone = str(data.get("phone", "無"))
        address = str(data.get("address", "無"))
        issue = str(data.get("issue_type", "維修"))
        desc = str(data.get("description", "-"))

        # 產生導航連結與電話連結
        encoded_address = urllib.parse.quote(address)
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        phone_url = f"tel:{''.join(filter(str.isdigit, phone))}"

        # 3. 同步到 Google Sheet (如果有設定 Google Apps Script)
        if GOOGLE_URL:
            try: requests.post(GOOGLE_URL, json=data, timeout=5)
            except: pass

        # 4. 推播(Push Message)給老闆您自己
        if LINE_TOKEN and MY_USER_ID:
            headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
            admin_flex = {
                "to": MY_USER_ID,
                "messages": [{
                    "type": "flex",
                    "altText": f"🆕 新報修單: {customer}",
                    "contents": {
                        "type": "bubble",
                        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#0B251F", "contents": [{"type": "text", "text": "🚨 收到新維修派工", "color": "#ffffff", "weight": "bold"}]},
                        "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                            {"type": "text", "text": f"👤 客戶: {customer}", "weight": "bold", "size": "md"},
                            {"type": "text", "text": f"📞 電話: {phone}", "action": {"type": "uri", "uri": phone_url}, "color": "#2D6A4F", "weight": "bold", "decoration": "underline"},
                            {"type": "separator"},
                            {"type": "text", "text": f"📍 地址: {address}", "wrap": True, "size": "sm", "color": "#111111"},
                            {"type": "text", "text": f"🔧 項目: {issue}", "weight": "bold", "color": "#1B4332"},
                            {"type": "text", "text": f"📝 描述: {desc}", "wrap": True, "size": "xs", "color": "#666666"}
                        ]},
                        "footer": {"type": "box", "layout": "vertical", "contents": [
                            {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "uri", "label": "🚗 開始導航", "uri": google_maps_url}}
                        ]}
                    }
                }]
            }
            requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=admin_flex)

        return {"status": "success"}

    except Exception as e:
        print(f"Server Error: {e}")
        return {"status": "error", "message": f"伺服器錯誤: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
