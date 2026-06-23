#!/bin/bash

echo "=== STARTING SPPU AI BACKEND ==="

# Step 1 - Download PDFs from Google Drive
echo "=== DOWNLOADING PDFS FROM GOOGLE DRIVE ==="
mkdir -p /app/backend/data
gdown --folder "https://drive.google.com/drive/folders/13mTDfcuZmDTWa7ROrCnjZ2UadHHIHXYV" \
      --output /app/backend/data \
      --quiet

echo "=== PDF DOWNLOAD COMPLETE ==="

# Step 2 - Run ingestion to build ChromaDB
echo "=== BUILDING CHROMADB ==="
cd /app/backend
python ingest.py

echo "=== CHROMADB READY ==="

# Step 3 - Start FastAPI server
echo "=== STARTING FASTAPI SERVER ==="
uvicorn api:app --host 0.0.0.0 --port 7860