---
title: Student AI SPPU
emoji: 🎓
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🎓 SPPU Student AI Assistant

**[▶ Live Demo](https://student-ai-assistent-sppu.vercel.app)** · Agentic RAG · LangGraph · ChromaDB · FastAPI · React

![Python](https://img.shields.io/badge/Python-3.10-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct_Agent-orange)
![React](https://img.shields.io/badge/React-Vite-61DAFB)
![License](https://img.shields.io/badge/License-MIT-green)

An **agentic RAG** study assistant for Savitribai Phule Pune University (SPPU) engineering students. It decides for itself when to search the syllabus corpus, retrieves with a two-stage vector-search + cross-encoder pipeline, and returns answers with a clickable link to the exact source PDF and page number.

Built as a final-year engineering Major Project. Includes neural text-to-speech, a React chat interface, and a live scraper that pulls the newest university circulars into the knowledge base on demand.

---

## 🧠 How It Works

The core is a **LangGraph ReAct agent** (`backend/agent.py`) that autonomously routes each question to one of two tools:

| Tool | When the agent picks it |
|---|---|
| `search_syllabus_notes` | Any syllabus, concept, definition, or lab-procedure question |
| `check_latest_sppu_notices` | Time-sensitive queries — exam dates, new circulars, announcements |

Retrieval runs in two stages:

1. **Recall** — `BAAI/bge-base-en-v1.5` embeddings pull the top 20 candidate chunks from ChromaDB.
2. **Precision** — a `BAAI/bge-reranker-base` cross-encoder rescores all 20 and keeps the best 4.

The reranked chunks carry their filename and page number as metadata, which is what powers the per-answer source citations. Generation runs on Groq's `openai/gpt-oss-120b`, with `qwen/qwen3.6-27b` handling image questions (diagrams, question papers).

**Why an agent instead of a fixed RAG chain:** a fixed chain retrieves on every single query, including "hi". The agent skips retrieval for small talk and triggers the live scraper on its own when a question is about dates — no manual button needed.

---

## ✨ Features

* **Cited answers.** Every RAG answer renders source chips underneath linking to the exact PDF and page, so nothing has to be taken on trust.
* **Two-stage retrieval.** Bi-encoder recall plus cross-encoder reranking, with filename injection into chunk text to survive the lexical-keyword blindspot.
* **Autonomous tool routing.** LangGraph ReAct loop chooses retrieval, live scraping, or a direct reply per query.
* **On-demand audio tutor.** Microsoft Azure Neural voices via Edge-TTS, streamed as lazy-loaded binary blobs to avoid browser memory pressure.
* **Live circular sync.** BeautifulSoup scraper fetches the newest SPPU notices, tags them temporally (`LATEST_NOTICE_`), and re-indexes them into the vector store.
* **Vision mode.** Upload a diagram or past question paper and ask about it directly.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (ReAct), LangChain |
| LLM inference | Groq — `openai/gpt-oss-120b`, `qwen/qwen3.6-27b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (cross-encoder) |
| Vector store | ChromaDB |
| Backend | FastAPI, Uvicorn |
| Frontend | React, Vite, Tailwind CSS, Framer Motion |
| TTS | Edge-TTS (Azure Neural voices) |
| Deployment | Hugging Face Spaces (Docker) + Vercel |

---

## 🚀 Local Setup

### Prerequisites
1. Python 3.10 — [download](https://www.python.org/downloads/)
2. Node.js v18+ and npm — [download](https://nodejs.org/)
3. A free Groq API key — [console.groq.com](https://console.groq.com)

### Step 1 — Clone

```bash
git clone https://github.com/YashKutehub/Student-AI-Assistent--SPPU.git
cd Student-AI-Assistent--SPPU
```

### Step 2 — Backend

```bash
cd backend
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:

```env
GROQ_API_KEY=your_actual_api_key_here
TTS_VOICE_ID=en-US-AriaNeural
```

Start the server:

```bash
uvicorn api:app --reload
```

Leave this terminal running.

### Step 3 — Frontend

In a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

### Step 4 — Build the vector database

The assistant has no knowledge until you feed it documents.

1. Drop SPPU syllabus PDFs, notes, or lab manuals into `backend/data/`.
2. With the backend venv active, run the ingestion script:

```bash
cd backend
python ingest.py
```

The script auto-detects CUDA and falls back to CPU. It skips already-processed files, so re-running it only indexes what's new.

**Verify it worked** — hit the health endpoint:

```bash
curl http://localhost:8000/health
```

A non-zero `chunks_in_db` means retrieval is live. A zero means the database is empty and the assistant will fall back to general knowledge.

**Alternative:** click **Live Sync** in the frontend header to scrape and index the latest SPPU circulars automatically.

---

## 📁 Project Architecture

```text
SPPU-AI-ASSISTANT/
│
├── backend/                  # Python API & AI logic
│   ├── api.py                # FastAPI endpoints (/chat, /speak, /sync-notices, /health)
│   ├── agent.py              # LangGraph ReAct agent + tool definitions
│   ├── backend.py            # Groq routing, embeddings, cross-encoder reranking
│   ├── ingest.py             # PDF chunking, metadata injection, vector DB build
│   ├── scraper.py            # BeautifulSoup SPPU multi-board circular scraper
│   ├── voice_agent.py        # Edge-TTS audio stream generation
│   ├── startup.sh            # Container entrypoint: builds DB, then serves
│   ├── requirements.txt      # Python dependencies
│   ├── .env                  # API keys (gitignored)
│   ├── data/                 # Raw PDF storage (gitignored)
│   └── chroma_db/            # Vector database (gitignored)
│
├── frontend/                 # React UI
│   ├── src/
│   │   ├── App.jsx           # Chat interface, source chips, blob audio player
│   │   └── main.jsx          # React entry point
│   └── package.json
│
├── .github/workflows/
│   └── sync-to-hf.yml        # CD: pushes a clean tree to the HF Space on merge
└── Dockerfile                # HF Spaces container definition
```

---

## 🐛 Troubleshooting

**Answers come back with no source citations.**
Check `/health`. If `chunks_in_db` is `0`, the vector database is empty and the agent is falling back to general knowledge. Run `python ingest.py`.

**Frontend says "Backend is unreachable".**
Confirm FastAPI is on port 8000. If it bound elsewhere, update `VITE_API_URL` in your frontend `.env`.

**Deleted PDFs still show up in answers.**
Vector stores don't auto-remove deleted documents. Delete the whole `chroma_db/` folder and re-run `python ingest.py` for a hard reset.

**Audio isn't playing.**
Edge-TTS needs a live connection to Microsoft's servers. Check network access and that `.env` loaded correctly.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
