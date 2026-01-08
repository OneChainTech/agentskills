import json
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from agent import ManusAgent

# Load environment variables
load_dotenv()

app = FastAPI()

# Allow CORS for development convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    task: str

@app.post("/api/run")
async def run_task(request: TaskRequest):
    agent = ManusAgent()
    
    async def event_generator():
        try:
            async for event in agent.run(request.task):
                yield json.dumps(event) + "\n"
                # Small delay to ensure UI updates smoothly if events come too fast
                await asyncio.sleep(0.05)
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"Server Error: {str(e)}"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# Serve static files (the web interface)
app.mount("/", StaticFiles(directory="web", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting Manus Server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)