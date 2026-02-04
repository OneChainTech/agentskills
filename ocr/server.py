import os
import shutil
import time
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from utils.pdf_handler import pdf_to_images
from engine.ocr import OCREngine
from retrieval import PDFRetriever

app = FastAPI()

# 核心修复：使用绝对路径挂载，防止显示失败
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

ocr_engine = OCREngine()
retriever = PDFRetriever()

class QueryRequest(BaseModel):
    question: str
    history: List[dict] = []

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(BASE_DIR, "web", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    print(f"[*] Received upload: {file.filename}")
    # 强制清理旧图片，确保显示最新上传的文件
    for filename in os.listdir(IMAGE_DIR):
        file_p = os.path.join(IMAGE_DIR, filename)
        try:
            if os.path.isfile(file_p) or os.path.islink(file_p):
                os.unlink(file_p)
        except Exception as e:
            print(f'Failed to delete {file_p}. Reason: {e}')

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. 转换页面为图片
        print(f"[*] Converting {file.filename} to images...")
        images = []
        if file.filename.lower().endswith('.pdf'):
            images = pdf_to_images(file_path, output_dir=IMAGE_DIR)
        else:
            from PIL import Image
            img = Image.open(file_path).convert('RGB')
            save_path = os.path.join(IMAGE_DIR, "page_1.png")
            img.save(save_path)
            images = [img]
        
        # 2. 调用云端解析
        print(f"[*] Calling VLM for OCR analysis ({len(images)} pages)...")
        ocr_pages = ocr_engine.process_pdf_pages(images)
        
        # 3. 注入混合检索索引
        print(f"[*] Updating vector index...")
        retriever.ingest_pages(ocr_pages)
        
        print(f"[+] Ingestion complete for {file.filename}")
        ts = int(time.time())
        return {
            "filename": file.filename,
            "pages": [
                {
                    "page_num": p["page"],
                    "image_url": f"/images/page_{p['page']}.png?t={ts}",
                    "markdown": p["markdown"],
                    "boxes": p["boxes"]
                } for p in ocr_pages
            ]
        }
    except Exception as e:
        print(f"[-] Upload Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Processing Error: {str(e)}")

@app.post("/query")
async def query_doc(request: QueryRequest):
    print(f"[*] Received query: {request.question}")
    try:
        result = retriever.query(request.question, request.history)
        print(f"[+] Query response generated.")
        return result
    except Exception as e:
        print(f"[-] Query Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
