import os
import urllib.parse
import shutil
import glob
import uuid
import base64
import sys
from datetime import date
from functools import lru_cache
from scraper import scrape_latest_sppu_notice
import subprocess
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import unquote
from pydantic import BaseModel
from huggingface_hub import HfApi, hf_hub_download
from backend import DB_PERSIST_DIRECTORY, retrieve_context_with_sources, generate_llm_response, get_vectorstore
from voice_agent import generate_tutor_audio
from agent import run_agent


# --- SETUP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- DAILY REQUEST LIMITER ----
request_count = {"date": date.today(), "count": 0}
MAX_DAILY_REQUESTS = 200

@app.middleware("http")
async def limit_requests(request, call_next):
    if request.url.path in ["/chat", "/speak"]:
        if request_count["date"] != date.today():
            request_count["date"] = date.today()
            request_count["count"] = 0
        if request_count["count"] >= MAX_DAILY_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Daily limit reached. Try again tomorrow."}
            )
        request_count["count"] += 1
    return await call_next(request)
# ---- END LIMITER ----

# --- VECTOR DB SETUP ---
print("--- LOADING VECTOR DATABASE ---")
vectorstore = get_vectorstore()
print("--- DATABASE LOADED ---")


# --- PDF SOURCE RESOLUTION ---
# The 218 source PDFs live in an HF dataset, not in the container. We resolve
# local data/ first (so Live Sync scraped notices still work), then fall back
# to downloading the single requested PDF from the dataset on demand.
PDF_DATASET = "Yashkute/sppu-pdf-docs"


@lru_cache(maxsize=1)
def _pdf_index():
    """Map basename -> path inside the dataset repo. Built once per container."""
    files = HfApi().list_repo_files(PDF_DATASET, repo_type="dataset")
    return {os.path.basename(f): f for f in files if f.lower().endswith(".pdf")}


def resolve_pdf(decoded_filename: str):
    """Return a local filesystem path for the PDF, or None if it doesn't exist."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    hits = glob.glob(
        os.path.join(BASE_DIR, "data", "**", decoded_filename), recursive=True
    )
    if hits:
        path = os.path.abspath(hits[0])
        print(f"File found locally at: {path}")
        return path

    repo_path = _pdf_index().get(os.path.basename(decoded_filename))
    if not repo_path:
        return None

    print(f"Fetching from HF dataset: {repo_path}")
    return hf_hub_download(PDF_DATASET, repo_path, repo_type="dataset")


@app.get("/health")
def health():
    try:
        count = vectorstore._collection.count()
    except Exception as e:
        return {"chunks_in_db": -1, "error": str(e)}
    return {"chunks_in_db": count, "db_path": DB_PERSIST_DIRECTORY}


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
        print(f"Received Question: {question}")
        is_rag = use_rag.lower() == "true"

        if file:
            os.makedirs("temp", exist_ok=True)
            temp_image_path = f"temp/{uuid.uuid4()}_{file.filename}"
            with open(temp_image_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"Image saved temporarily at {temp_image_path}")

        if is_rag and not temp_image_path:
            print("Running agent...")
            answer, sources = run_agent(question, history)
            mode = "agent"
        else:
            answer = generate_llm_response(question, "", history, temp_image_path, use_rag=is_rag)
            sources = []
            mode = "vision" if temp_image_path else "general"

        return JSONResponse(content={
            "answer": answer,
            "sources": sources,
            "mode": mode,
            "audio_base64": None
        })

    except Exception as e:
        print(f"API Error: {e}")
        return JSONResponse(content={"answer": "Sorry, a server error occurred.", "sources": [], "mode": "error", "audio_base64": None})

    finally:
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)


# --- VOICE ON-DEMAND ENDPOINT ---
class SpeakRequest(BaseModel):
    text: str

@app.post("/speak")
async def speak_endpoint(req: SpeakRequest):
    print("Synthesizing Voice Tutor Audio on demand...")
    try:
        clean_text = req.text.replace("**", "").replace("*", "").replace("#", "")

        if len(clean_text) > 3500:
            clean_text = clean_text[:3500] + "... The rest of the answer has been truncated for audio playback."

        audio_bytes = await generate_tutor_audio(clean_text)

        if audio_bytes:
            return Response(content=audio_bytes, media_type="audio/mpeg")

        raise HTTPException(status_code=500, detail="Audio generation failed")
    except Exception as e:
        print(f"Speak Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- LIVE SYNC ENDPOINT (kept as manual override) ---
@app.post("/sync-notices")
async def sync_sppu_notices():
    try:
        success, message = scrape_latest_sppu_notice()

        if success:
            print("New file detected! Triggering Vector Database Update...")
            backend_dir = os.path.dirname(os.path.abspath(__file__))

            result = subprocess.run(
                [sys.executable, "ingest.py"],
                cwd=backend_dir,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            if result.returncode != 0:
                err_tail = (result.stderr or "").strip()[-2000:]
                out_tail = (result.stdout or "").strip()[-2000:]
                raise RuntimeError(
                    f"ingest.py failed (exit code {result.returncode}).\nSTDERR tail:\n{err_tail}\nSTDOUT tail:\n{out_tail}"
                )

            global vectorstore
            get_vectorstore.cache_clear()
            vectorstore = get_vectorstore()

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
        print(f"Sync API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- PDF VIEW ENDPOINT ---
@app.get("/view/{filename:path}")
async def view_pdf(filename: str):
    decoded_filename = unquote(filename)
    path = resolve_pdf(decoded_filename)

    if not path:
        print(f"File NOT found: {decoded_filename}")
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path, media_type="application/pdf")


# --- PDF DOWNLOAD ENDPOINT ---
@app.get("/download/{filename:path}")
async def download_file(filename: str):
    decoded_filename = urllib.parse.unquote(filename)
    print(f"Download request: {decoded_filename}")

    path = resolve_pdf(decoded_filename)

    if not path:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=path,
        filename=decoded_filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{decoded_filename}"'}
    )


# --- SERVER STARTUP ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)