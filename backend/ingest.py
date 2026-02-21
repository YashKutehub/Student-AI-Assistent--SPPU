import os
import shutil
from dotenv import load_dotenv

# --- LIBRARIES ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# 1. Setup
load_dotenv()
DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def main():
    # --- 1. CLEAN UP OLD DB (Optional but recommended) ---
    if os.path.exists(DB_PATH):
        print(f"🗑️  Removing old database at {DB_PATH}...")
        shutil.rmtree(DB_PATH)

    # --- 2. LOAD DOCUMENTS (DEEP SEARCH) ---
    print(f"🔍 Scanning '{DATA_PATH}' for PDFs...")
    
    documents = []
    
    # Walk through all folders (SPPU -> REFERENCE BOOKS -> etc.)
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.lower().endswith(".pdf"):
                file_path = os.path.join(root, file)
                print(f"   📄 Loading: {file_path}")
                try:
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    # Add metadata so we know exactly which file it came from
                    for doc in docs:
                        doc.metadata["source"] = file_path
                    documents.extend(docs)
                except Exception as e:
                    print(f"   ❌ Failed to load {file}: {e}")

    if not documents:
        print("❌ No PDFs found! Check your data folder.")
        return

    print(f"\n✅ Loaded {len(documents)} pages total.")

    # --- 3. SPLIT TEXT ---
    print("✂️  Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   Created {len(chunks)} text chunks.")

    # --- 4. CREATE VECTOR DATABASE ---
    print("🧠 Creating Embeddings (This takes time)...")
    
    # We use a standard, free embedding model (runs locally)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    db = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory=DB_PATH
    )

    print(f"🎉 Success! Database saved to '{DB_PATH}'")

if __name__ == "__main__":
    main()