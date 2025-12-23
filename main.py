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
from google.genai import types
from PIL import Image
import io
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import Response

app = FastAPI()

# --- Cloudflare R2 / S3 Setup ---
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")

# Initialize S3 Client only if credentials exist (fallback to local if not set, or error out)
s3_client = None
if R2_ENDPOINT_URL and R2_ACCESS_KEY_ID:
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY
        )
        print("S3 Client initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize S3 client: {e}")

# Mount static files
# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# If R2 is used, we serve /tree-assets via a custom endpoint that fetches from R2.
# If R2 is NOT used (s3_client is None), we fallback to local providing backward compatibility logic locally if needed,
# BUT for this migration we assume R2 is the goal.
# However, to avoid breaking local dev without creds immediately, let's keep local mount if s3_client is None.

if s3_client is None:
    # Fallback to local
    os.makedirs("assets", exist_ok=True)
    os.makedirs("assets/history", exist_ok=True)
    app.mount("/tree-assets", StaticFiles(directory="assets"), name="tree-assets")
else:
    # R2 Mode: Define a route to proxy/stream images
    @app.get("/tree-assets/{filename}")
    async def get_tree_asset(filename: str):
        try:
            # Determine if it's history or current
            # Our HistoryManager stores everything in root or history/ ?
            # Let's adjust HistoryManager to simple paths in R2.
            # "assets/current_tree.png" -> "current_tree.png" in bucket
            # "assets/history/tree_..." -> "history/tree_..." in bucket
            
            key = ""
            if filename == "current_tree.png":
                key = "current_tree.png"
            elif filename == "HEAD":
                key = "HEAD"
            else:
                key = f"history/{filename}"

            response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
            return Response(
                content=response['Body'].read(),
                media_type="image/png" if filename.endswith(".png") else "text/plain"
            )
        except ClientError as e:
            raise HTTPException(status_code=404, detail="File not found in storage")
        except Exception as e:
            print(f"R2 Fetch Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
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
        """Returns the filename currently pointed to by HEAD via R2."""
        if not s3_client:
             # LOCAL FALLBACK (Old Logic)
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

        # R2 LOGIC
        try:
            response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key="HEAD")
            return response['Body'].read().decode('utf-8').strip()
        except ClientError:
            # HEAD not found, try to find latest history
            history = cls.get_history_list()
            if history:
                return history[0]
            return None

    @classmethod
    def update_head(cls, filename: str):
        """Updates HEAD to point to the given filename."""
        if not s3_client:
            with open(cls.HEAD_FILE, "w") as f:
                f.write(filename)
            return

        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key="HEAD",
            Body=filename.encode('utf-8'),
            ContentType="text/plain"
        )

    @classmethod
    def save_to_history(cls, image_data: bytes) -> str:
        """Saves image data to history directory with timestamp. Returns filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"tree_{timestamp}.png"
        
        if not s3_client:
            path = os.path.join(cls.HISTORY_DIR, filename)
            with open(path, "wb") as f:
                f.write(image_data)
            return filename

        # R2 Upload
        key = f"history/{filename}"
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=image_data,
            ContentType="image/png"
        )
        return filename

    @classmethod
    def set_active_image(cls, history_filename: str):
        """Copies a history file to the current tree location and updates HEAD."""
        if not s3_client:
            source = os.path.join(cls.HISTORY_DIR, history_filename)
            if not os.path.exists(source):
                raise FileNotFoundError(f"History file {history_filename} not found")
            shutil.copy2(source, cls.CURRENT_TREE_PATH)
            cls.update_head(history_filename)
            return

        # R2 Copy
        try:
            copy_source = {'Bucket': R2_BUCKET_NAME, 'Key': f"history/{history_filename}"}
            s3_client.copy(copy_source, R2_BUCKET_NAME, "current_tree.png")
            cls.update_head(history_filename)
        except ClientError as e:
            print(f"R2 Copy Error: {e}")
            raise HTTPException(status_code=404, detail="Source image not found in storage")

    @classmethod
    def get_history_list(cls):
        """Returns list of history files sorted by newest first."""
        if not s3_client:
            files = glob.glob(os.path.join(cls.HISTORY_DIR, "tree_*.png"))
            files.sort(reverse=True)
            return [os.path.basename(f) for f in files]

        # R2 List
        try:
            response = s3_client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix="history/tree_")
            if 'Contents' not in response:
                return []
            
            # Extract filenames
            # Key is like "history/tree_2025...png", we want "tree_2025...png"
            files = []
            for obj in response['Contents']:
                files.append(os.path.basename(obj['Key']))
            
            # Sort descending (names contain timestamp)
            files.sort(reverse=True)
            return files
        except Exception as e:
            print(f"R2 List Error: {e}")
            return []

    @classmethod
    def rollback(cls, steps: int):
        """Rollbacks 'steps' relative to current HEAD."""
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
    head_file = HistoryManager.get_head()
    
    # Logic to fetch base image data depending on mode
    if s3_client:
        # R2 Mode: Fetch from R2
        try:
            if head_file:
                # If we have a head, use it. But wait, HistoryManager.CURRENT_TREE_PATH is local convention.
                # In R2, we maintain "current_tree.png" at root.
                print(f"Fetching base image from R2: current_tree.png (based on {head_file})")
                obj = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key="current_tree.png")
                base_image_data = obj['Body'].read()
                parts.append(types.Part.from_bytes(data=base_image_data, mime_type="image/png"))
            else:
                # No HEAD. Is there a current?
                try:
                    obj = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key="current_tree.png")
                    base_image_data = obj['Body'].read()
                    print("Fetching base image from R2: current_tree.png")
                    parts.append(types.Part.from_bytes(data=base_image_data, mime_type="image/png"))
                except ClientError:
                    print("No current_tree.png found in R2. Creating fresh start if possible or skipping base.")
        except Exception as e:
            print(f"Error fetching base from R2: {e}")

    else:
        # LOCAL FALLBACK
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
        with open("prompt.txt", "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
    except Exception as e:
        print(f"Error loading prompt.txt: {e}")
        prompt_text = "Synthesize these images. Place the provided decoration object (the second image) onto the Christmas Tree (the first image) in a decorative and festive way. Return ONLY the composited image."

    parts.append(types.Part.from_text(text=prompt_text))

    contents = [types.Content(role="user", parts=parts)]

    generate_content_config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(image_size="2K"),
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
    # Initial setup: Restore from HEAD if exists, else init HEAD
    # In R2 mode, this check might just be printing status, as state is persistent in the bucket.
    if not s3_client:
        # Local logic
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
