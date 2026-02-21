import os
import shutil
import time
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from google.api_core import exceptions

load_dotenv()
DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def main():
    if os.path.exists(DB_PATH):
        print(f"🗑️  Cleaning old database...")
        shutil.rmtree(DB_PATH)

    print(f"🔍 Scanning PDFs...")
    documents = []
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.lower().endswith(".pdf"):
                file_path = os.path.join(root, file)
                try:
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    for doc in docs:
                        doc.metadata["source"] = file 
                    documents.extend(docs)
                except Exception as e:
                    print(f"   ❌ Error loading {file}: {e}")

    print(f"✅ Loaded {len(documents)} pages.")

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)
    print(f"✂️  Created {len(chunks)} chunks.")

    # --- HIGH-SPEED BATCH INGESTION ---
    print("🧠 Initializing High-Speed Ingestion...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_document"
    )

    batch_size = 95  # Bundling 95 chunks into 1 single API request
    db = None

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        print(f"🚀 Sending Batch {i//batch_size + 1} (Chunks {i} to {i+len(batch)})")
        
        # Retry logic with exponential backoff
        for attempt in range(5): 
            try:
                if db is None:
                    db = Chroma.from_documents(batch, embeddings, persist_directory=DB_PATH)
                else:
                    db.add_documents(batch)
                break # Success! Move to next batch
            except exceptions.ResourceExhausted:
                wait_time = (attempt + 1) * 10
                print(f"⚠️  Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                break

    print(f"🎉 Success! Database built at '{DB_PATH}'")

if __name__ == "__main__":
    main()