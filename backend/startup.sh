#!/bin/bash
set -e
cd /app/backend

if [ -d "chroma_db" ] && [ -n "$(ls -A chroma_db 2>/dev/null)" ]; then
  echo "=== CHROMA_DB PRESENT - SKIPPING BUILD ==="
else
  echo "=== NO CHROMA_DB - DOWNLOADING PDFs FROM HF DATASET ==="
  python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Yashkute/sppu-pdf-docs",
    repo_type="dataset",
    local_dir="data",
)
print("PDFs downloaded.")
PY
  echo "=== BUILDING VECTOR DB (slow on CPU, be patient) ==="
  python ingest.py
fi

echo "=== STARTING FASTAPI SERVER ==="
uvicorn api:app --host 0.0.0.0 --port 7860