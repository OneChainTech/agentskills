import os
import shutil
import time
import uuid
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from utils.pdf_handler import pdf_to_images
from engine.ocr import OCREngine
from retrieval import PDFRetriever

app = FastAPI()

# 核心修复：使用绝对路径挂载，防止显示失败
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
HISTORY_DIR = os.path.join(BASE_DIR, "data", "history")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

ocr_engine = OCREngine()
retriever = PDFRetriever()
UPLOAD_STATUS = {}
UPLOAD_EVENTS = {}
UPLOAD_CACHE_TTL_SEC = 600
MAX_UPLOAD_CACHE_ITEMS = 200

class QueryRequest(BaseModel):
    question: str
    history: List[dict] = Field(default_factory=list)
    filters: Optional[dict] = None

class LoadHistoryRequest(BaseModel):
    upload_id: str

def _prune_upload_cache():
    now_ms = int(time.time() * 1000)
    stale_ids = []
    for upload_id, status in UPLOAD_STATUS.items():
        stage = status.get("stage")
        updated_at = int(status.get("updated_at", now_ms))
        age_sec = (now_ms - updated_at) / 1000.0
        if stage in ("done", "error") and age_sec > UPLOAD_CACHE_TTL_SEC:
            stale_ids.append(upload_id)

    for upload_id in stale_ids:
        UPLOAD_STATUS.pop(upload_id, None)
        UPLOAD_EVENTS.pop(upload_id, None)

    if len(UPLOAD_STATUS) > MAX_UPLOAD_CACHE_ITEMS:
        ordered = sorted(
            UPLOAD_STATUS.items(),
            key=lambda kv: int(kv[1].get("updated_at", 0))
        )
        remove_count = len(UPLOAD_STATUS) - MAX_UPLOAD_CACHE_ITEMS
        for upload_id, _ in ordered[:remove_count]:
            UPLOAD_STATUS.pop(upload_id, None)
            UPLOAD_EVENTS.pop(upload_id, None)

def _set_upload_status(upload_id: str, stage: str, progress: int, message: str, extra: dict = None):
    _prune_upload_cache()
    payload = {
        "upload_id": upload_id,
        "stage": stage,
        "progress": max(0, min(100, int(progress))),
        "message": message,
        "updated_at": int(time.time() * 1000),
    }
    if extra:
        payload.update(extra)
    UPLOAD_STATUS[upload_id] = payload
    events = UPLOAD_EVENTS.setdefault(upload_id, [])
    event = dict(payload)
    event["event_id"] = len(events) + 1
    events.append(event)

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(BASE_DIR, "web", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/history")
def list_history():
    files = []
    if os.path.exists(HISTORY_DIR):
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith(".json"):
                path = os.path.join(HISTORY_DIR, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        files.append({
                            "upload_id": data.get("upload_id"),
                            "filename": data.get("filename"),
                            "timestamp": data.get("timestamp"),
                            "pages_count": len(data.get("pages", []))
                        })
                except:
                    continue
    # Sort by timestamp desc
    files.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return files

@app.delete("/history/{upload_id}")
def delete_history(upload_id: str):
    history_path = os.path.join(HISTORY_DIR, f"{upload_id}.json")
    image_dir = os.path.join(IMAGE_DIR, upload_id)
    
    deleted = False
    if os.path.exists(history_path):
        os.remove(history_path)
        deleted = True
    
    if os.path.exists(image_dir):
        shutil.rmtree(image_dir)
        deleted = True
        
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "ok"}

@app.post("/history/load")
def load_history(request: LoadHistoryRequest):
    path = os.path.join(HISTORY_DIR, f"{request.upload_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="History not found")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Re-ingest
        ocr_pages = []
        for p in data["pages"]:
            ocr_pages.append({
                "page": p["page_num"],
                "markdown": p["markdown"],
                "boxes": p["boxes"],
                "grounded_markdown": p.get("grounded_markdown", p["markdown"])
            })
        
        retriever.current_upload_id = request.upload_id
        retriever.ingest_pages(ocr_pages)
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    upload_id: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    max_chunks_per_page: Optional[int] = Form(None),
    max_total_chunks: Optional[int] = Form(None),
):
    if not upload_id:
        upload_id = f"up_{uuid.uuid4().hex}"
    UPLOAD_EVENTS[upload_id] = []
    print(f"[*] Received upload: {file.filename} (ID: {upload_id})")
    _set_upload_status(upload_id, "received", 5, "已接收文件，准备处理")
    upload_start = time.perf_counter()
    
    # 核心修改：使用 session 子目录
    session_image_dir = os.path.join(IMAGE_DIR, upload_id)
    os.makedirs(session_image_dir, exist_ok=True)

    file_path = os.path.join(UPLOAD_DIR, f"{upload_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. 转换页面为图片
        print(f"[*] Converting {file.filename} to images...")
        _set_upload_status(upload_id, "rendering", 25, "正在进行页面渲染")
        convert_start = time.perf_counter()
        images = []
        if file.filename.lower().endswith('.pdf'):
            images = pdf_to_images(file_path, output_dir=session_image_dir)
        else:
            from PIL import Image
            img = Image.open(file_path).convert('RGB')
            save_path = os.path.join(session_image_dir, "page_1.png")
            img.save(save_path)
            images = [img]
        convert_ms = round((time.perf_counter() - convert_start) * 1000, 2)
        
        # 2. 调用云端解析
        print(f"[*] Calling VLM for OCR analysis ({len(images)} pages)...")
        _set_upload_status(upload_id, "ocr", 50, f"正在进行OCR识别（0/{len(images)}页）")
        
        def ocr_progress_callback(finished, total):
            if total <= 0:
                return
            progress = 50 + int((finished / total) * 20) # 50% to 70% range
            _set_upload_status(upload_id, "ocr", progress, f"正在进行OCR识别（{finished}/{total}页）")

        ocr_start = time.perf_counter()
        ocr_pages = ocr_engine.process_pdf_pages(images, callback=ocr_progress_callback)
        ocr_ms = round((time.perf_counter() - ocr_start) * 1000, 2)
        
        # 3. 注入混合检索索引
        print(f"[*] Updating vector index...")
        _set_upload_status(upload_id, "indexing", 75, "正在切分并构建检索索引")
        ingest_start = time.perf_counter()
        chunk_config = {}
        if chunk_size is not None:
            chunk_config["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            chunk_config["chunk_overlap"] = chunk_overlap
        if max_chunks_per_page is not None:
            chunk_config["max_chunks_per_page"] = max_chunks_per_page
        if max_total_chunks is not None:
            chunk_config["max_total_chunks"] = max_total_chunks
        
        retriever.current_upload_id = upload_id
        ingest_result = retriever.ingest_pages(ocr_pages, chunk_config=chunk_config or None)
        ingest_call_ms = round((time.perf_counter() - ingest_start) * 1000, 2)
        
        # 4. 保存历史记录
        ts = int(time.time())
        history_data = {
            "upload_id": upload_id,
            "filename": file.filename,
            "timestamp": ts,
            "pages": [
                {
                    "page_num": p["page"],
                    "image_url": f"/images/{upload_id}/page_{p['page']}.png?t={ts}",
                    "markdown": p["markdown"],
                    "boxes": p["boxes"],
                    "grounded_markdown": p.get("grounded_markdown", p["markdown"])
                } for p in ocr_pages
            ]
        }
        history_path = os.path.join(HISTORY_DIR, f"{upload_id}.json")
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        if isinstance(ingest_result, dict):
            ingest_stats = ingest_result
        else:
            ingest_stats = {
                "doc_count": int(ingest_result or 0),
                "pages": len(ocr_pages),
                "chunks_before_limit": int(ingest_result or 0),
                "chunks_after_limit": int(ingest_result or 0),
                "chunk_build_ms": None,
                "index_ms": None,
                "total_ms": ingest_call_ms,
            }
        upload_total_ms = round((time.perf_counter() - upload_start) * 1000, 2)
        timings = {
            "convert_ms": convert_ms,
            "ocr_ms": ocr_ms,
            "ingest_ms": ingest_stats.get("total_ms", ingest_call_ms),
            "upload_total_ms": upload_total_ms,
            "ingest_detail": ingest_stats,
        }
        print(
            f"[+] Upload timing: convert={convert_ms}ms, ocr={ocr_ms}ms, "
            f"ingest={timings['ingest_ms']}ms, total={upload_total_ms}ms"
        )
        _set_upload_status(upload_id, "done", 100, "处理完成", {"timings": timings})
        
        print(f"[+] Ingestion complete for {file.filename}")
        return {
            **history_data,
            "timings": timings,
            "chunk_config": ingest_stats.get("chunk_config", {}),
        }
    except Exception as e:
        _set_upload_status(upload_id, "error", 100, f"处理失败: {str(e)}")
        print(f"[-] Upload Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Processing Error: {str(e)}")

@app.get("/upload_status/{upload_id}")
def upload_status(upload_id: str):
    _prune_upload_cache()
    return UPLOAD_STATUS.get(upload_id, {
        "upload_id": upload_id,
        "stage": "pending",
        "progress": 0,
        "message": "任务排队中",
        "updated_at": int(time.time() * 1000),
    })

@app.get("/upload_events/{upload_id}")
async def upload_events(upload_id: str):
    _prune_upload_cache()
    async def event_generator():
        sent_idx = 0
        keep_alive_tick = 0
        while True:
            events = UPLOAD_EVENTS.get(upload_id, [])
            while sent_idx < len(events):
                evt = events[sent_idx]
                sent_idx += 1
                yield f"id: {evt['event_id']}\ndata: {json.dumps(evt, ensure_ascii=False)}\n\n"
                if evt.get("stage") in ("done", "error"):
                    return

            await asyncio.sleep(0.4)
            keep_alive_tick += 1
            if keep_alive_tick % 25 == 0:
                yield ": keep-alive\n\n"

            status = UPLOAD_STATUS.get(upload_id)
            if status and status.get("stage") in ("done", "error") and sent_idx >= len(events):
                return

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@app.post("/query")
async def query_doc(request: QueryRequest):
    print(f"[*] Received query: {request.question}")
    try:
        result = retriever.query(request.question, request.history, request.filters)
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
