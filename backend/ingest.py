import os
import sys
import shutil
import urllib.parse
from dotenv import load_dotenv

# --- LIBRARIES ---
import torch
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

sys.stdout.reconfigure(encoding="utf-8")

# 1. Setup
load_dotenv()
DATA_PATH = "./data"
DB_PATH = "./chroma_db"

# Auto-detect hardware: CUDA on your local GTX 1650, CPU on the HF Space.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Public base URL of the PDFs so citations can link straight to the source file
# without shipping 599MB of PDFs into the container.
HF_PDF_BASE = "https://huggingface.co/datasets/Yashkute/sppu-pdf-docs/resolve/main/"


def main():
    print(f"Initializing Embedding Engine on device: {DEVICE}")

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-base-en-v1.5",
        model_kwargs={"device": DEVICE},
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,
        },
    )

    # --- 1. LOAD EXISTING DB & CHECK PROCESSED FILES ---
    processed_files = set()
    db = None

    if os.path.exists(DB_PATH):
        print(f"Loading existing database from '{DB_PATH}'...")
        db = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        existing_data = db.get(include=["metadatas"])
        processed_files = set(
            meta.get("source") for meta in existing_data["metadatas"] if meta and "source" in meta
        )
        print(f"   Found {len(processed_files)} previously processed files in the DB.")
    else:
        print("No existing database found. Creating a new one from scratch.")

    # --- 2. SCAN FOR NEW PDFs ---
    print(f"\nScanning '{DATA_PATH}' for NEW PDFs...")
    documents = []
    new_files_count = 0

    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            if file in processed_files:
                continue

            file_path = os.path.join(root, file)
            print(f"   NEW FILE DETECTED: {file}")

            rel = os.path.relpath(file_path, DATA_PATH).replace(os.sep, "/")
            source_url = HF_PDF_BASE + urllib.parse.quote(rel)

            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = file
                    doc.metadata["source_url"] = source_url
                    if getattr(doc, "page_content", "") and doc.page_content.strip():
                        documents.append(doc)
                new_files_count += 1
            except Exception as e:
                print(f"   Failed to load {file}: {e}")

    # --- 3. EARLY EXIT IF NOTHING NEW ---
    if not documents:
        print("\nNo new PDFs found. Database is already up to date.")
        return

    print(f"\nLoaded {new_files_count} new files ({len(documents)} non-empty pages total).")

    # --- 4. SPLIT TEXT & INJECT METADATA ---
    print("Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = text_splitter.split_documents(documents)

    if not chunks:
        print("\nNo text chunks could be created. Skipping vector DB update.")
        return

    print("Injecting filenames into the text content...")
    for chunk in chunks:
        filename = chunk.metadata.get("source", "Unknown Document")
        chunk.page_content = f"Document Title: {filename}\n\n{chunk.page_content}"

    print(f"   Created and enriched {len(chunks)} text chunks.")

    # --- 5. UPDATE VECTOR DATABASE ---
    print("Embedding new chunks into the database...")
    BATCH_SIZE = 500
    if db is None:
        db = Chroma.from_documents(
            documents=chunks[:BATCH_SIZE],
            embedding=embeddings,
            persist_directory=DB_PATH,
        )
        remaining = chunks[BATCH_SIZE:]
    else:
        remaining = chunks

    total_batches = max(1, (len(remaining) - 1) // BATCH_SIZE + 1) if remaining else 0
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i + BATCH_SIZE]
        db.add_documents(documents=batch)
        print(f"   Batch {i // BATCH_SIZE + 1}/{total_batches} embedded")

    print(f"Success. Database updated at '{DB_PATH}'")


if __name__ == "__main__":
    main()