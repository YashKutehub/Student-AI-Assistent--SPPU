#!/bin/bash
echo "=== STARTING SPPU AI BACKEND ==="
echo "=== USING PRE-BUILT CHROMADB ==="
echo "=== STARTING FASTAPI SERVER ==="
cd /app/backend
uvicorn api:app --host 0.0.0.0 --port 7860