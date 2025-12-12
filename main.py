import os
import shutil
import mimetypes
import asyncio
from datetime import datetime
import glob
import json
from dotenv import load_dotenv

load_dotenv() # Load env vars

from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image
import io

app = FastAPI()

# Make sure directories exist
os.makedirs("assets", exist_ok=True)
os.makedirs("assets/history", exist_ok=True)

# Mount static files
# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/tree-assets", StaticFiles(directory="assets"), name="tree-assets")
# Mount frontend assets if they exist (for production)
if os.path.exists("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="frontend-assets")

# CORS
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- History Manager ---
class HistoryManager:
    HISTORY_DIR = "assets/history"
    CURRENT_TREE_PATH = "assets/current_tree.png"
    HEAD_FILE = "assets/HEAD"

    @classmethod
    def get_head(cls) -> Optional[str]:
        """Returns the filename currently pointed to by HEAD."""
        if os.path.exists(cls.HEAD_FILE):
            try:
                with open(cls.HEAD_FILE, "r") as f:
                    return f.read().strip()
            except:
                pass
        
        # Fallback: return the latest history file if exists
        history = cls.get_history_list()
        if history:
            return history[0]
        return None

    @classmethod
    def update_head(cls, filename: str):
        """Updates HEAD to point to the given filename."""
        with open(cls.HEAD_FILE, "w") as f:
            f.write(filename)

    @classmethod
    def save_to_history(cls, image_data: bytes) -> str:
        """Saves image data to history directory with timestamp. Returns filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"tree_{timestamp}.png"
        path = os.path.join(cls.HISTORY_DIR, filename)
        
        with open(path, "wb") as f:
            f.write(image_data)
        
        return filename

    @classmethod
    def set_active_image(cls, history_filename: str):
        """Copies a history file to the current tree location and updates HEAD."""
        source = os.path.join(cls.HISTORY_DIR, history_filename)
        if not os.path.exists(source):
            raise FileNotFoundError(f"History file {history_filename} not found")
        
        shutil.copy2(source, cls.CURRENT_TREE_PATH)
        cls.update_head(history_filename)

    @classmethod
    def get_history_list(cls):
        """Returns list of history files sorted by newest first."""
        files = glob.glob(os.path.join(cls.HISTORY_DIR, "tree_*.png"))
        # Sort by name (which has timestamp) descending
        files.sort(reverse=True)
        return [os.path.basename(f) for f in files]

    @classmethod
    def rollback(cls, steps: int):
        """Rollbacks 'steps' relative to current HEAD.
        steps=1 means go to the previous version from HEAD.
        """
        history = cls.get_history_list()
        if not history:
            raise HTTPException(status_code=400, detail="No history available")
        
        current_head = cls.get_head()
        current_index = 0
        
        if current_head in history:
            current_index = history.index(current_head)
        
        # Calculate target index
        target_index = current_index + steps
        
        # Clamp to bounds
        if target_index >= len(history):
            target_index = len(history) - 1
        if target_index < 0:
            target_index = 0
            
        target_file = history[target_index]
        cls.set_active_image(target_file)
        return target_file

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# --- GenAI ---
def get_genai_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)

async def generate_decoration(decoration_bytes: bytes, decoration_type: str):
    client = get_genai_client()
    # CRITICAL: User requires this specific model. DO NOT CHANGE.
    model = "gemini-3-pro-image-preview" 

    parts = []
    
    # 1. Base Tree (if exists)
    # Use HEAD if available to ensure we build from the known state
    head_file = HistoryManager.get_head()
    base_image_path = HistoryManager.CURRENT_TREE_PATH
    
    if head_file:
        full_head_path = os.path.join(HistoryManager.HISTORY_DIR, head_file)
        if os.path.exists(full_head_path):
            base_image_path = full_head_path
            print(f"Generating based on HEAD: {head_file}")
            
    if os.path.exists(base_image_path):
        with open(base_image_path, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    
    # 2. Decoration
    parts.append(types.Part.from_bytes(data=decoration_bytes, mime_type=decoration_type))
    
    # 3. Instruction
    # Load prompt from prompt.json
    try:
        with open("prompt.json", "r", encoding="utf-8") as f:
            prompt_data = json.load(f)
            prompt_text = prompt_data.get("decoration_prompt", "Synthesize these images.")
    except Exception as e:
        print(f"Error loading prompt.json: {e}")
        prompt_text = "Synthesize these images. Place the provided decoration object (the second image) onto the Christmas Tree (the first image) in a decorative and festive way. Return ONLY the composited image."

    parts.append(types.Part.from_text(text=prompt_text))

    contents = [types.Content(role="user", parts=parts)]

    generate_content_config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(image_size="1K", aspect_ratio="9:16"),
    )

    try:
        print(f"Calling GenAI ({model})...")
        # Revert to stream if that was the magic 
        # But wait, the previous code I WROTE used generate_content (non-stream). 
        # The ORIGINAL code (Step 6) used generate_content_stream.
        # Maybe "gemini-3-pro-image-preview" ONLY works with stream?
        # I should probably revert to generate_content_stream to be safe and match the original successful state (if it ever worked).
        # Actually, let's look at the original code in Step 6.
        # It used: response_stream = client.models.generate_content_stream(...)
        # I will revert structure to match Step 6 but keep my HistoryManager addition.
        
        response_stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        )

        for chunk in response_stream:
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    img_data = part.inline_data.data
                    
                    # SAVE TO HISTORY AND UPDATE CURRENT
                    filename = HistoryManager.save_to_history(img_data)
                    HistoryManager.set_active_image(filename)
                    
                    print(f"Tree updated via stream! Saved to {filename}")
                    return True
                if part.text:
                    print(f"GenAI Text Output: {part.text}")
                    
        print("GenAI response did not contain image data.")

    except Exception as e:
        print(f"GenAI Exception: {e}")
        import traceback
        traceback.print_exc()
    
    return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    print(f"Received upload: {file.filename}")
    try:
        content = await file.read()
        success = await generate_decoration(content, file.content_type)
        if success:
            await manager.broadcast("update_tree")
            return {"status": "success"}
        else:
            return {"status": "failed", "message": "Generation failed"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# --- Admin Endpoints ---

class RollbackRequest(BaseModel):
    steps: int

class RestoreRequest(BaseModel):
    filename: str

@app.get("/admin/history")
async def get_history():
    return {"history": HistoryManager.get_history_list()}

@app.post("/admin/rollback")
async def rollback_tree(req: RollbackRequest):
    try:
        filename = HistoryManager.rollback(req.steps)
        await manager.broadcast("update_tree")
        return {"status": "success", "current": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/restore")
async def restore_tree(req: RestoreRequest):
    try:
        HistoryManager.set_active_image(req.filename)
        await manager.broadcast("update_tree")
        return {"status": "success", "current": req.filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def get():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    import uvicorn
    # Initial setup: Restore from HEAD if exists, else init HEAD
    head = HistoryManager.get_head()
    if head:
        print(f"Restoring state from HEAD: {head}")
        try:
            HistoryManager.set_active_image(head)
        except Exception as e:
            print(f"Failed to restore HEAD: {e}")
    elif os.path.exists("assets/current_tree.png") and not glob.glob("assets/history/tree_*.png"):
         with open("assets/current_tree.png", "rb") as f:
             HistoryManager.save_to_history(f.read())
             # This will set HEAD too via save_to_history? No, save_to_history just returns filename.
             # We should set initialization.
             # Actually save_to_history doesn't update HEAD. set_active_image does.
             # Let's just let the user's first action set it, or...
             pass
             
    uvicorn.run(app, host="0.0.0.0", port=8002)
