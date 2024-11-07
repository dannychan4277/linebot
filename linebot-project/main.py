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

# 全域變數儲存向量資料庫
global_db = None

def init_pdf_processing():
    """初始化 PDF 處理"""
    global global_db
    pdf_folder = "pdfs"
    
    try:
        # 檢查資料夾是否存在
        if not os.path.exists(pdf_folder):
            logger.warning(f"PDF folder {pdf_folder} does not exist")
            return
        
        # 載入所有 PDF
        documents = []
        for filename in os.listdir(pdf_folder):
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(pdf_folder, filename)
                loader = PyPDFLoader(pdf_path)
                documents.extend(loader.load())
        
        if not documents:
            logger.warning("No PDF documents found")
            return
            
        # 分割文本
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(documents)
        
        # 創建向量資料庫
        embeddings = OpenAIEmbeddings()
        global_db = Chroma.from_documents(texts, embeddings)
        logger.info("PDF processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error in PDF processing: {str(e)}")
        raise

@app.on_event("startup")
async def startup_event():
    """應用啟動時初始化"""
    init_pdf_processing()

@app.get("/")
async def root():
    """根路由"""
    return {"message": "LineBot is running!"}

@app.post("/callback")
async def callback(request: Request):
    """處理 Line Webhook"""
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
        
        if global_db is None:
            response = "系統尚未完成初始化，請稍後再試。"
        else:
            # 創建問答鏈
            qa = RetrievalQA.from_chain_type(
                llm=OpenAI(temperature=0.7),
                chain_type="stuff",
                retriever=global_db.as_retriever()
            )
            
            # 獲取回應
            response = qa.run(user_message)
        
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