import os
import re
import sys
import subprocess

from backend import (
    get_vectorstore,
    retrieve_context_with_sources,
    generate_llm_response,
)
from scraper import scrape_latest_sppu_notice


# Questions that genuinely need a live scrape of the SPPU circulars page.
# Everything else goes straight to vector retrieval.
NOTICE_PATTERNS = re.compile(
    r"\b(notice|circular|announcement|exam\s*date|time\s*table|timetable|"
    r"result\s*date|latest|recent|new\s+update|deadline)\b",
    re.IGNORECASE,
)


def check_latest_sppu_notices() -> str:
    """Scrape the official SPPU circulars page and index anything new."""
    success, message = scrape_latest_sppu_notice()
    if not success:
        return f"Could not check for new notices: {message}"

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "ingest.py"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return f"Found notices but failed to index them: {(result.stderr or '')[-500:]}"

    get_vectorstore.cache_clear()
    return message


def run_agent(question: str, history: str = ""):
    """
    Deterministic RAG pipeline.

    The previous implementation used a LangGraph ReAct agent. That cost three
    LLM round-trips per question (decide -> tool -> answer) and re-sent the full
    retrieved context on every hop, which blew past Groq's free-tier 8000 TPM
    limit. Retrieval is mandatory for every syllabus question here, so there is
    nothing for the model to decide: retrieve once, answer once.
    """
    notice_prefix = ""

    if NOTICE_PATTERNS.search(question):
        print("Time-sensitive question detected — checking SPPU circulars...")
        notice_prefix = check_latest_sppu_notices()

    context, sources = retrieve_context_with_sources(question, get_vectorstore())

    if notice_prefix:
        context = f"--- LATEST NOTICE CHECK ---\n{notice_prefix}\n\n{context}"

    answer = generate_llm_response(
        query=question,
        context_text=context,
        chat_history=history,
        image_path=None,
        use_rag=bool(context),
    )

    print(f"Sources returned: {sources or 'none'}")
    return answer, sources