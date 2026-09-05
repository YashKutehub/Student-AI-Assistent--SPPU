#!/bin/bash
set -e
cd /app/backend

if [ -d "chroma_db" ] && [ -n "$(ls -A chroma_db 2>/dev/null)" ]; then
  echo "=== CHROMA_DB PRESENT - SKIPPING DOWNLOAD ==="
else
  echo "=== DOWNLOADING PREBUILT CHROMA DB FROM HF DATASET ==="
  python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Yashkute/sppu-chroma-db",
    repo_type="dataset",
    local_dir="chroma_db",
)
print("Chroma DB downloaded.")
PY
fi

echo "=== STARTING FASTAPI SERVER ==="
uvicorn api:app --host 0.0.0.0 --port 7860