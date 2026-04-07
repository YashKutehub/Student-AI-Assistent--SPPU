import os
import urllib.parse
import shutil
import glob
import uuid
import base64
import sys
from scraper import scrape_latest_sppu_notice
import subprocess
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import unquote
from pydantic import BaseModel
# Import your AI logic (Updated to match the new backend.py)
from backend import DB_PERSIST_DIRECTORY, retrieve_context_with_sources, generate_llm_response 
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from voice_agent import generate_tutor_audio

# --- SETUP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VECTOR DB SETUP ---
print("--- LOADING VECTOR DATABASE ---")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=DB_PERSIST_DIRECTORY, embedding_function=embeddings)
print("--- DATABASE LOADED ---")


# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(
    question: str = Form(...),
    history: str = Form(""),
    use_rag: str = Form("true"),
    file: UploadFile = File(None)
):
    temp_image_path = None
    try:
        print(f"🎙️ Received Question: {question}")
        is_rag = use_rag.lower() == "true"
        
        # 1. Image Processing (Save temporarily for backend.py to read)
        if file:
            os.makedirs("temp", exist_ok=True)
            temp_image_path = f"temp/{uuid.uuid4()}_{file.filename}"
            with open(temp_image_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"📸 Image saved temporarily at {temp_image_path}")
            
        # 2. The Two-Stage Reranking Retrieval
        context = ""
        sources = []
        if is_rag:
            print("🔍 Running Two-Stage Cross-Encoder Search...")
            context, sources = retrieve_context_with_sources(question, vectorstore)

        # 3. Generate the Text Answer (Groq/Llama)
        print("🧠 Generating AI Response...")
        answer = generate_llm_response(question, context, history, temp_image_path, use_rag=is_rag)

        # 4. Send the Payload back to React
        # Note: audio_base64 is set to None because audio is now fetched on-demand via /speak
        return JSONResponse(content={
            "answer": answer,
            "sources": sources,
            "mode": "rag" if is_rag else "general",
            "audio_base64": None  
        })

    except Exception as e:
        print(f"❌ API Error: {e}")
        return JSONResponse(content={"answer": "Sorry, a server error occurred.", "sources": [], "mode": "error", "audio_base64": None})
        
    finally:
        # 5. Cleanup the temporary image so your hard drive doesn't fill up
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)

# --- VOICE ON-DEMAND ENDPOINT ---
class SpeakRequest(BaseModel):
    text: str

@app.post("/speak")
async def speak_endpoint(req: SpeakRequest):
    print("🔊 Synthesizing Voice Tutor Audio on demand...")
    try:
        clean_text = req.text.replace("**", "").replace("*", "").replace("#", "")
        
        # 🎯 THE FIX 1: Safety Truncation
        # ElevenLabs limits single requests. If the AI writes an essay, 
        # we only read the first 3500 characters out loud to prevent a crash.
        if len(clean_text) > 3500:
            clean_text = clean_text[:3500] + "... The rest of the answer has been truncated for audio playback."
            
        audio_bytes = await generate_tutor_audio(clean_text)
        
        if audio_bytes:
            # 🎯 THE FIX 2: Return pure binary audio bytes, NOT a giant Base64 string
            return Response(content=audio_bytes, media_type="audio/mpeg")
            
        raise HTTPException(status_code=500, detail="Audio generation failed")
    except Exception as e:
        print(f"❌ Speak Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- LIVE SYNC ENDPOINT ---
@app.post("/sync-notices")
async def sync_sppu_notices():
    try:
        # 1. Run the Web Scraper
        success, message = scrape_latest_sppu_notice()
        
        if success:
            print("🔄 New file detected! Triggering Vector Database Update...")
            # 2. Automatically run your ingest.py script to vectorize the new PDF
            # This uses the exact same script we updated earlier with the Title Injection!
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            result = subprocess.run(
                [sys.executable, "ingest.py"],
                cwd=backend_dir,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Return useful logs rather than a generic 500.
                err_tail = (result.stderr or "").strip()[-2000:]
                out_tail = (result.stdout or "").strip()[-2000:]
                raise RuntimeError(
                    f"ingest.py failed (exit code {result.returncode}).\nSTDERR tail:\n{err_tail}\nSTDOUT tail:\n{out_tail}"
                )
            # Important: reload the in-memory vectorstore so /chat uses newly-added embeddings.
            # (Otherwise the server may keep searching the pre-sync collection.)
            global vectorstore
            vectorstore = Chroma(
                persist_directory=DB_PERSIST_DIRECTORY,
                embedding_function=embeddings
            )
            # Show whether ingest actually created chunks (often 0 for scanned PDFs).
            ingest_tail = ""
            combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            if combined:
                ingest_tail = combined[-900:]
            if ingest_tail:
                message += f" and injected into AI Memory (ingest completed). Ingest log tail: {ingest_tail}"
            else:
                message += " and injected into AI Memory (ingest completed)."
            
        return {"status": "success" if success else "warning", "message": message}
        
    except Exception as e:
        print(f"❌ Sync API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- PDF VIEW ENDPOINT ---
@app.get("/view/{filename:path}")
async def view_pdf(filename: str):
    decoded_filename = unquote(filename)
    
    search_pattern = os.path.join("data", "**", decoded_filename)
    files = glob.glob(search_pattern, recursive=True)
    
    if files:
        file_path = os.path.abspath(files[0])
        print(f"✅ File found at: {file_path}")
        return FileResponse(file_path, media_type='application/pdf')
    
    print(f"❌ File NOT found: {decoded_filename}")
    raise HTTPException(status_code=404, detail="File not found in any subfolders")

# --- PDF DOWNLOAD ENDPOINT ---
@app.get("/download/{filename:path}")
async def download_file(filename: str):
    decoded_filename = urllib.parse.unquote(filename)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(BASE_DIR, "data") 
    
    print(f"\n--- DOWNLOAD REQUEST ---")
    
    found_file_path = None
    for root, dirs, files in os.walk(data_folder):
        if decoded_filename in files:
            found_file_path = os.path.join(root, decoded_filename)
            break 
            
    if not found_file_path:
        raise HTTPException(status_code=404, detail="File not found")

    print(f"✅ File found at: {found_file_path}")
    return FileResponse(
        path=found_file_path, 
        filename=decoded_filename, 
        media_type='application/pdf',
        headers={"Content-Disposition": f'attachment; filename="{decoded_filename}"'}
    )

# --- SERVER STARTUP ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)