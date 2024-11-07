import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from langchain_openai import OpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

# 創建 FastAPI 應用
app = FastAPI()

# 設定 Line Bot API
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 設定 OpenAI API
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')

# 新增一個簡單的根路由
@app.get("/")
async def root():
    return {"message": "LineBot is running!"}

# 新增一個測試路由
@app.get("/test")
async def test():
    return {"message": "Test endpoint is working!"}

@app.post("/callback")
async def callback(request: Request):
    # 獲取 X-Line-Signature header 值
    signature = request.headers['X-Line-Signature']
    
    # 獲取請求體內容
    body = await request.body()
    body = body.decode('utf-8')
    
    try:
        # 處理 webhook body
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature error")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理用戶訊息"""
    try:
        user_message = event.message.text
        response = f"您說了：{user_message}"
        
        # 發送回應
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
        
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        # 發送錯誤訊息給用戶
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="抱歉，系統發生錯誤，請稍後再試。")
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
