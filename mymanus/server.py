import json
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import shutil
import os
from agent import ManusAgent

import sandbox_e2b

# Load environment variables
load_dotenv()

# Global Agent Instance
agent_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global agent_instance
    agent_instance = ManusAgent()
    yield
    # Shutdown
    print("Shutting down agent and sandbox...")
    if agent_instance:
        await agent_instance.close()

app = FastAPI(lifespan=lifespan)

# Allow CORS for development convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Download directory (for artifacts retrieved from sandbox)
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class TaskRequest(BaseModel):
    task: Optional[str] = None
    files: Optional[List[str]] = []
    thread_id: Optional[str] = None

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return JSONResponse({"filename": file.filename, "path": file_path})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/run")
async def run_task(request: TaskRequest):
    # Use global agent instance
    agent = agent_instance
    
    # Inject file context if files exist
    prompt = request.task
    if request.files:
        file_context = "\n\n[System Notification] ⚠️ FILE UPLOAD DETECTED\n"
        file_context += "The user has uploaded files to the LOCAL server. You cannot access them directly in the sandbox yet.\n"
        file_context += "FILES AVAILABLE LOCALLY:\n"
        for fpath in request.files:
            file_context += f"- {fpath}\n"
        
        file_context += "\nREQUIRED ACTION STEP (Execute first):\n"
        file_context += "1. Call `upload_local_file(local_path='...', remote_path='filename')` for each file to transfer it to the sandbox.\n"
        file_context += "2. Once uploaded, you can access them in the sandbox using standard Python (e.g., `open('filename')`).\n"
        file_context += "DO NOT try to read the local absolute path directly. It will fail.\n"
        
        if prompt:
            prompt += file_context
        else:
            prompt = file_context

    async def event_generator():
        try:
            # If prompt is None (e.g. resumption), agent.run handles it
            async for event in agent.run(prompt, thread_id=request.thread_id):
                yield json.dumps(event) + "\n"
                # Small delay to ensure UI updates smoothly if events come too fast
                await asyncio.sleep(0.05)
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"Server Error: {str(e)}"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# Serve static files (the web interface)
app.mount("/", StaticFiles(directory="web", html=True), name="static")
app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")

if __name__ == "__main__":
    import uvicorn
    print("Starting Manus Server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
