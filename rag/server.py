from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from typing import List
from langchain_core.documents import Document

from rag_engine import rag_engine

app = FastAPI(title="RAG Service API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for frontend
# Get the absolute path to the web directory
web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
os.makedirs(web_dir, exist_ok=True)
app.mount("/web", StaticFiles(directory=web_dir), name="web")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text_content = content.decode("utf-8")
        
        # Simple document creation - in real app use proper loaders
        doc = Document(page_content=text_content, metadata={"source": file.filename})
        
        rag_engine.ingest_documents([doc])
        
        return {"message": f"Successfully ingested {file.filename}", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        answer = rag_engine.query(request.query)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "RAG Service is running. Go to /web/index.html to use the UI."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
