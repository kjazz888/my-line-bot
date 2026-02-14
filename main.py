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

# --- [自定義] Flex Message 範本庫 (百科全書級森林綠風格) ---

def get_main_menu():
    """產生故障自檢主選單卡片，提供詳細分類按鈕"""
    return {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#081C15",
            "contents": [
                {"type": "text", "text": "數位弱電工程", "color": "#2D6A4F", "size": "xs", "weight": "bold"},
                {"type": "text", "text": "🛠️ 智能故障自檢手冊", "color": "#ffffff", "weight": "bold", "size": "lg", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": "請選擇您的設備類型或問題：", "size": "sm", "color": "#666666"},
                # 監視器大類
                {"type": "text", "text": "📹 監視器系統", "weight": "bold", "size": "md", "color": "#1B4332", "margin": "md"},
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "沒畫面", "text": "監視器沒畫面自檢"}},
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "有斜紋", "text": "監視器畫面異常自檢"}}
                ]},
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "看回放", "text": "無法回放自檢"}},
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "遠端看", "text": "遠端連線自檢"}}
                ]},
                {"type": "separator", "margin": "lg"},
                # 網路/門禁/電話大類
                {"type": "text", "text": "🌐 網路 / 🔑 門禁 / ☎️ 電話", "weight": "bold", "size": "md", "color": "#1B4332", "margin": "md"},
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "網路斷線", "text": "網路自檢"}},
                    {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "門鎖不開", "text": "門禁自檢"}}
                ]},
                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "電話故障", "text": "電話自檢"}}
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "contents": [
                {"type": "button", "style": "primary", "color": "#1B4332", "action": {"type": "uri", "label": "🚨 還是不行，我要報修", "uri": "https://liff.line.me/2009131881-t8EctqkW"}}
            ]
        }
    }

# --- [Endpoint] 1. LINE Webhook 處理器 ---

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """根據客戶點擊的按鈕內容，回覆對應的排查教學"""
    user_msg = event.message.text.strip()
    
    if user_msg == "故障自檢":
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="自檢中心", contents=get_main_menu()))
    
    # --- 監視器系列 ---
    elif user_msg == "監視器沒畫面自檢":
        msg = ("【📹 監視器沒畫面排查】\n\n"
               "1. 檢查主機電源：確認錄影機(DVR)前方指示燈有無亮起？\n"
               "2. 檢查螢幕：確認螢幕電源已開啟，且訊號源(HDMI/VGA)切換正確。\n"
               "3. 變壓器檢查：單支沒畫面通常是攝影機變壓器損壞，請看攝影機晚上紅外線有無亮燈。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    elif user_msg == "監視器畫面異常自檢":
        msg = ("【🎨 畫面有斜紋/閃爍排查】\n\n"
               "1. 電源干擾：變壓器老化常導致斜紋，請嘗試更換變壓器。\n"
               "2. 線路檢查：檢查主機後方 BNC 接頭有無氧化鬆脫。\n"
               "3. 強電避開：攝影機線路不可與強電(220V)並行。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    elif user_msg == "無法回放自檢":
        msg = ("【💾 無法回放錄影排查】\n\n"
               "1. 硬碟狀態：進入主機選單檢查『硬碟管理』，確認狀態為『正常』。\n"
               "2. 異常警報：主機若持續『嗶嗶』聲，通常是硬碟損毀。\n"
               "3. 時間誤差：檢查右下角時間，若跳回 2000 年會找不到錄影檔。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    elif user_msg == "遠端連線自檢":
        msg = ("【📱 手機看不了排查】\n\n"
               "1. 網路檢查：確認現場 WiFi 數據機是否亮紅燈？\n"
               "2. LAN接頭：錄影機後方網口綠燈有無閃爍？\n"
               "3. 設備重啟：將數據機與錄影機斷電 10 秒後重啟。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    # --- 網路/門禁/電話系列 ---
    elif user_msg == "網路自檢":
        msg = ("【🌐 網路/WiFi 異常排查】\n\n"
               "1. 觀察數據機：小烏龜是否亮紅燈(ALARM)？\n"
               "2. 重啟大法：將 WiFi 分享器電源拔掉重插。\n"
               "3. 若亮紅燈：請電洽電信商(如中華電信)確認外線狀態。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    elif user_msg == "門禁自檢":
        msg = ("【🔑 門禁與對講排查】\n\n"
               "1. 讀卡機檢查：感應主機指示燈有無亮起？刷卡有無嗶聲？\n"
               "2. 電源排查：檢查弱電箱內的門禁變壓器是否損壞。\n"
               "3. 出門開關：嘗試按壓開關，確認是否為開關接觸不良。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    elif user_msg == "電話自檢":
        msg = ("【☎️ 電話總機排查】\n\n"
               "1. 檢查話機：螢幕是否有文字？線路有無鬆脫？\n"
               "2. 撥『0』測試：聽聽看有無外線撥通音。\n"
               "3. 總機重啟：若所有話機都斷線，請檢查總機箱電源。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

# --- [Endpoint] 2. 接收前端網頁表單提交 ---

@app.post("/submit_repair")
async def handle_repair(request: Request):
    try:
        data = await request.json()
        
        # 1. Google reCAPTCHA 驗證
        captcha_token = data.get("captcha")
        verify_res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={'secret': RECAPTCHA_SECRET, 'response': captcha_token},
            timeout=10
        ).json()

        if not verify_res.get("success"):
            return {"status": "fail", "message": "機器人驗證失敗"}

        # 2. 資料收集
        customer = str(data.get("customer_name", "客戶"))
        phone = str(data.get("phone", "無"))
        address = str(data.get("address", "無"))
        issue = str(data.get("issue_type", "維修"))
        desc = str(data.get("description", "-"))

        # 產生連結
        encoded_address = urllib.parse.quote(address)
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        phone_url = f"tel:{''.join(filter(str.isdigit, phone))}"

        # 3. 同步到 Google Sheet (選填)
        if GOOGLE_URL:
            try: requests.post(GOOGLE_URL, json=data, timeout=5)
            except: pass

        # 4. 推播給管理員 (老闆您自己)
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
