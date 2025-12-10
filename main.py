import os
import shutil
import mimetypes
import asyncio
from dotenv import load_dotenv

load_dotenv() # Load env vars

from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google import genai
from google.genai import types
from PIL import Image
import io

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# CORS
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manager for active websocket connections
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

# Ensure assets directory exists
os.makedirs("assets", exist_ok=True)
TREE_PATH = "assets/current_tree.png"

# GenAI Client
def get_genai_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)

async def generate_decoration(decoration_bytes: bytes, decoration_type: str):
    client = get_genai_client()
    model = "gemini-3-pro-image-preview"

    # Prepare contents
    # User pattern uses types.Content with parts
    parts = []
    
    # 1. Base Tree (if exists)
    if os.path.exists(TREE_PATH):
        with open(TREE_PATH, "rb") as f:
            # Note: The user's snippet uses 'INSERT_INPUT_HERE'. 
            # We assume for image-to-image we pass the image + prompt.
            # But the user's snippet was text-to-image. 
            # We will follow the logic of "Nano Banana" for composition:
            # We pass the tree and the mofumofu and ask it to composite.
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    
    # 2. Decoration
    parts.append(types.Part.from_bytes(data=decoration_bytes, mime_type=decoration_type))
    
    # 3. Instruction
    # The user's prompt was "INSERT_INPUT_HERE". We need to be specific for the app purpose.
    parts.append(types.Part.from_text(text="Synthesize these images. Place the provided decoration object (the second image) onto the Christmas Tree (the first image) in a decorative and festive way. Return ONLY the composited image."))

    contents = [types.Content(role="user", parts=parts)]

    generate_content_config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(image_size="1K"),
    )

    try:
        print(f"Calling GenAI ({model})...")
        # User used generate_content_stream, so we will too.
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
                    with open(TREE_PATH, "wb") as f:
                        f.write(img_data)
                    print("Tree updated successfully via stream!")
                    return True
                if part.text:
                    print(f"GenAI Text Output: {part.text}")
                    
        print("GenAI response did not contain image data.")
    except Exception as e:
        print(f"GenAI Error: {e}")
    
    return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    print(f"Received upload: {file.filename}")
    try:
        content = await file.read()
        
        # Trigger generation
        print(f"Triggering generation for {file.content_type}, size: {len(content)}")
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

@app.get("/")
async def get():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    # Verify API Key
    key = os.environ.get("GEMINI_API_KEY")
    print(f"API Key present: {bool(key)}")
    uvicorn.run(app, host="0.0.0.0", port=8002)
