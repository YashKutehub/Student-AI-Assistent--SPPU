---
title: Student AI SPPU
emoji: 🎓
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---


```markdown
# 🎓 SPPU Student AI Assistant

An advanced, full-stack AI tutor specifically designed for Savitribai Phule Pune University (SPPU) engineering students. It uses a **Two-Stage RAG (Retrieval-Augmented Generation)** architecture to answer syllabus questions, read PDF notes, and provide perfectly cited answers. 

Built as a final-year engineering Major Project, it features human-like text-to-speech audio, an interactive React frontend, and a Live Sync web scraper to automatically fetch the latest university circulars.

---

## ✨ Features
* **Textbook-Accurate RAG:** Uses ChromaDB and Cross-Encoder reranking to find exact answers from SPPU syllabus PDFs and Lab Manuals, immune to the "Lexical Keyword" blindspot via physical metadata injection.
* **On-Demand Audio Tutor:** Listen to answers via ultra-realistic Microsoft Azure Neural voices (Edge-TTS) with lazy-loading binary `Blob` streams to completely eliminate browser memory crashes.
* **Live Circular Sync:** Built-in BeautifulSoup web scraper that safely fetches the newest notices directly from the official SPPU website and tags them temporally (`LATEST_NOTICE_`) for immediate AI recognition.
* **Secure Architecture:** Fully stateless-ready frontend and backend, with strict `.env` isolation for API keys.

---

## 🛠️ Prerequisites
Before you begin, ensure you have the following installed on your machine:
1. **Python 3.10 ([Download Here](https://www.python.org/downloads/))
2. **Node.js (v18+) and npm** ([Download Here](https://nodejs.org/))
3. **A Free Groq API Key** (Get one at [console.groq.com](https://console.groq.com))

---

## 🚀 Installation & Setup Guide

Follow these steps carefully to get both the backend and frontend running on your local development environment.

### Step 1: Clone the Repository
Open your terminal or command prompt and run:
git clone https://github.com/YashKutehub/Student-AI-Assistent--SPPU.git
cd Student-AI-Assistent--SPPU
```

### Step 2: Set Up the Python Backend
You need to create an isolated environment so the project dependencies don't interfere with your system Python.

**1. Navigate to the backend folder:**
```bash
cd backend
```

**2. Create a Virtual Environment:**
* **Windows:**
  ```cmd
  python -m venv .venv
  ```
* **macOS (Intel/Apple Silicon) & Linux:**
  ```bash
  python3 -m venv .venv
  ```

**3. Activate the Virtual Environment:**
* **Windows:**
  ```cmd
  .venv\Scripts\activate
  ```
* **macOS & Linux:**
  ```bash
  source .venv/bin/activate
  ```
*(You should now see `(.venv)` at the start of your terminal line).*

**4. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**5. Configure Environment Variables:**
Create a file exactly named `.env` inside the `backend` folder and paste your Groq API key and preferred Voice ID:
```env
# Your free Groq API Key
GROQ_API_KEY=your_actual_api_key_here

# Premium Azure Neural Voice ID (e.g., en-US-JennyNeural, en-US-AriaNeural, en-GB-SoniaNeural)
TTS_VOICE_ID=en-US-JennyNeural
```

**6. Start the FastAPI Server:**
```bash
uvicorn api:app --reload
```
*(Leave this terminal window open and running in the background).*

---

### Step 3: Set Up the React Frontend
Open a **new, separate terminal window** and navigate to your project folder.

**1. Navigate to the frontend folder:**
```bash
cd frontend
```

**2. Install Node Dependencies:**
```bash
npm install
```

**3. Start the Development Server:**
```bash
npm run dev
```
Your app will automatically open in your default web browser, typically at `http://localhost:5173`.

---

### Step 4: Initialize the AI Memory (RAG Database)
Right now, the AI's ChromaDB instance is empty. You need to feed it SPPU documents to activate the RAG pipeline.

1. Drop your SPPU syllabus, notes, or lab manual PDFs into the `backend/data/` folder.
2. Open a terminal, activate your backend `.venv`, and run the ingestion script:
   ```bash
   cd backend
   python ingest.py
   ```
3. Wait for the terminal to finish splitting, injecting metadata, and embedding the text into `chroma_db`. 

**Alternatively (Live Sync):** Open the React frontend and click the green **"Live Sync"** button in the header. The app will automatically scrape the SPPU SharePoint website for the newest circulars, download them into the `data/` folder, and update the AI's memory in real-time.

---

## 📁 Project Architecture

```text
SPPU-AI-ASSISTANT/
│
├── backend/                  # Python API & AI Logic
│   ├── api.py                # FastAPI endpoints (/chat, /speak, /sync-notices)
│   ├── backend.py            # LangChain Groq routing & Cross-Encoder setup
│   ├── ingest.py             # PDF chunking, metadata injection & Vector DB initialization
│   ├── scraper.py            # BeautifulSoup SPPU targeted multi-board web scraper
│   ├── voice_agent.py        # Edge-TTS audio generation stream
│   ├── requirements.txt      # Pinned Python dependencies
│   ├── .env                  # Hidden API keys (DO NOT COMMIT)
│   ├── data/                 # Raw PDF storage (Ignored by Git)
│   └── chroma_db/            # Local vector database (Ignored by Git)
│
└── frontend/                 # React UI
    ├── src/
    │   ├── App.jsx           # Main chat interface & Blob audio player logic
    │   └── main.jsx          # React entry point
    └── package.json          # Node dependencies
```

## 🐛 Troubleshooting

* **Frontend says "Backend is unreachable":** Ensure your Python FastAPI server is running on port 8000. If it started on a different port, update the `API_URL` variable in `App.jsx`.
* **The AI is hallucinating or missing documents:** If you delete files from the `data/` folder, you must also manually delete the entire `chroma_db` folder and re-run `python ingest.py` to hard-reset the memory. Standard vector databases do not auto-delete removed documents.
* **Audio isn't playing:** Check the backend terminal. Ensure your computer has internet access, as Edge-TTS requires a live connection to Microsoft Azure servers. Verify your `.env` file is loaded correctly.
```
