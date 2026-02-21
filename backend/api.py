import os
import urllib.parse
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext

# Import your AI logic
from backend import ask_gemini_multimodal, DB_PERSIST_DIRECTORY
from langchain_community.vectorstores import Chroma
# UPDATED: Using Google Embeddings to match ingest.py
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- SETUP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup (SQLite for User Auth)
SQLALCHEMY_DATABASE_URL = "sqlite:///./student_assistant.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- VECTOR DB SETUP ---
# This matches the model and task type used in ingest.py for consistency
print("--- LOADING VECTOR DATABASE (GOOGLE EMBEDDINGS) ---")
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query"
)
vectorstore = Chroma(persist_directory=DB_PERSIST_DIRECTORY, embedding_function=embeddings)
print("--- DATABASE LOADED ---")

# --- MODELS ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

Base.metadata.create_all(bind=engine)

class UserRegister(BaseModel):
    username: str
    password: str

# --- ROUTES ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = pwd_context.hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/token")
def login(form_data: UserRegister, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user.username, "token_type": "bearer"}

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(
    question: str = Form(...),
    history: str = Form(""),
    use_rag: str = Form("true"), 
    file: UploadFile = File(None)
):
    image_path = None
    if file:
        image_path = f"temp_{uuid.uuid4()}.jpg"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    rag_enabled = str(use_rag).lower() not in ("false", "0", "null", "none", "")

    # Execute AI Logic
    answer, sources, mode = ask_gemini_multimodal(question, history, image_path, vectorstore, rag_enabled)
    
    if image_path:
        os.remove(image_path)
        
    return {"answer": answer, "sources": sources, "mode": mode}

# --- PDF DOWNLOAD ENDPOINT ---
@app.get("/download/{filename:path}")
async def download_file(filename: str):
    decoded_filename = urllib.parse.unquote(filename)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(BASE_DIR, "data") 
    
    print(f"\n--- DOWNLOAD REQUEST ---")
    print(f"📥 Searching for: '{decoded_filename}'...")
    
    found_file_path = None
    for root, dirs, files in os.walk(data_folder):
        if decoded_filename in files:
            found_file_path = os.path.join(root, decoded_filename)
            break
            
    if not found_file_path:
        print("❌ ERROR: File not found!")
        raise HTTPException(status_code=404, detail="File not found")

    print(f"✅ File found! Sending to browser...")
    return FileResponse(
        path=found_file_path, 
        filename=decoded_filename, 
        media_type='application/pdf',
        headers={"Content-Disposition": f'attachment; filename="{decoded_filename}"'}
    )

# --- SERVER STARTUP ---
if __name__ == "__main__":
    import uvicorn
    # Render dynamic port binding
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting SPPU Assistant on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)