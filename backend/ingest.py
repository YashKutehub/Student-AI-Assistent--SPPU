import os
import shutil
from dotenv import load_dotenv

# --- LIBRARIES ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Setup
load_dotenv()
DATA_PATH = "./data"
DB_PATH = "./chroma_db"


def main():
    print("🧠 Initializing Embedding Engine...")

    embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-en-v1.5",
    model_kwargs={"device": "cuda"},            # 🔧 use GTX 1650
    encode_kwargs={
        "normalize_embeddings": True,
        "batch_size": 32,                       # 🔧 safe for 4GB VRAM
    },
)

    # --- 1. LOAD EXISTING DB & CHECK PROCESSED FILES ---
    processed_files = set()
    db = None

    if os.path.exists(DB_PATH):
        print(f"📂 Loading existing database from '{DB_PATH}'...")
        db = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)

        existing_data = db.get(include=["metadatas"])

        processed_files = set(
            meta.get("source") for meta in existing_data["metadatas"] if meta and "source" in meta
        )
        print(f"   Found {len(processed_files)} previously processed files in the DB.")
    else:
        print(f"🆕 No existing database found. We will create a new one from scratch.")

    # --- 2. SCAN FOR NEW PDFs ---
    print(f"\n🔍 Scanning '{DATA_PATH}' for NEW PDFs...")
    documents = []
    new_files_count = 0

    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.lower().endswith(".pdf"):

                if file in processed_files:
                    continue

                file_path = os.path.join(root, file)
                print(f"   ✨ NEW FILE DETECTED: {file}")
                try:
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    for doc in docs:
                        # Clean the filename for the metadata
                        doc.metadata["source"] = file

                        # Some PDFs may extract as empty text; skip them so Chroma
                        # doesn't crash on an empty embedding set.
                        if getattr(doc, "page_content", "") and doc.page_content.strip():
                            documents.append(doc)
                    new_files_count += 1
                except Exception as e:
                    print(f"   ❌ Failed to load {file}: {e}")

    # --- 3. EARLY EXIT IF NOTHING NEW ---
    if not documents:
        print("\n✅ No new PDFs found. Your database is already up to date!")
        return

    print(f"\n✅ Loaded {new_files_count} new files ({len(documents)} non-empty pages total).")

    # --- 4. SPLIT TEXT & INJECT METADATA ---
    print("✂️ Splitting text into chunks...")

    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)

    # `split_documents` can return [] if all extracted text is empty.
    if not chunks:
        print("\n⚠️ No text chunks could be created from the downloaded PDFs.")
        print("    Skipping vector DB update to prevent embedding errors.")
        return

    # 🎯 THE PERMANENT RAG FIX: Physical Metadata Injection
    print("💉 Injecting filenames directly into the text content...")
    for chunk in chunks:
        filename = chunk.metadata.get("source", "Unknown Document")
        # Prepend the filename to the actual readable text
        chunk.page_content = f"Document Title: {filename}\n\n{chunk.page_content}"

    print(f"   Created and enriched {len(chunks)} text chunks.")

    # --- 5. UPDATE VECTOR DATABASE ---
    print("🧠 Embedding new chunks into the database...")
    BATCH_SIZE = 500
    if db is None:
        db = Chroma.from_documents(
            documents=chunks[:BATCH_SIZE],
            embedding=embeddings,
            persist_directory=DB_PATH
        )
        remaining = chunks[BATCH_SIZE:]
    else:
        remaining = chunks

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i + BATCH_SIZE]
        db.add_documents(documents=batch)
        print(f"   ✅ Batch {i//BATCH_SIZE + 1}/{(len(remaining)-1)//BATCH_SIZE + 1} embedded")

    print(f"🎉 Success! Database updated with highly-searchable chunks at '{DB_PATH}'")


if __name__ == "__main__":
    main()