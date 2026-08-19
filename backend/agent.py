import os
import sys
import subprocess
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from backend import get_groq_llm, get_vectorstore, retrieve_context_with_sources, TEXT_MODEL_NAME
from scraper import scrape_latest_sppu_notice


@tool
def search_syllabus_notes(query: str) -> str:
    """
    Search SPPU syllabus PDFs, lab manuals and notes using vector search
    + cross-encoder reranking. Use for any question about course content,
    concepts, definitions, or lab procedures.
    """
    vectorstore = get_vectorstore()
    context, sources = retrieve_context_with_sources(query, vectorstore)
    if not context:
        return "No relevant content found in the syllabus notes."
    return context + "\n\nSources: " + ", ".join(sources)


@tool
def check_latest_sppu_notices() -> str:
    """
    Scrapes the official SPPU circulars website for new notices and indexes
    them. Use ONLY when the question is time-sensitive - new exam dates,
    latest circulars, recent announcements - NOT for regular syllabus questions.
    """
    success, message = scrape_latest_sppu_notice()
    if not success:
        return f"Could not check for new notices: {message}"

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "ingest.py"], cwd=backend_dir,
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return f"Found notices but failed to index them: {result.stderr[-500:]}"

    get_vectorstore.cache_clear()
    return message


TOOLS = [search_syllabus_notes, check_latest_sppu_notices]
agent = create_react_agent(get_groq_llm(TEXT_MODEL_NAME), TOOLS)


def run_agent(question: str, history: str = ""):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an academic assistant for SPPU students. "
                "For ANY question about syllabus, course content, concepts, "
                "definitions, lab procedures, or exam topics, you MUST call the "
                "search_syllabus_notes tool BEFORE answering. Do not answer such "
                "questions from your own knowledge. Only skip tool use for greetings "
                "or small talk. Use check_latest_sppu_notices only for questions about "
                "dates, circulars, or recent announcements."
            ),
        }
    ]
    if history:
        messages.append({"role": "system", "content": f"Conversation so far:\n{history}"})
    messages.append({"role": "user", "content": question})

    result = agent.invoke({"messages": messages})
    answer = result["messages"][-1].content

    tool_calls = [m.name for m in result["messages"] if getattr(m, "name", None)]
    print(f"🤖 Tools called: {tool_calls or 'none — answered directly'}")

    sources = []
    for m in result["messages"]:
        if getattr(m, "name", None) == "search_syllabus_notes" and "Sources:" in m.content:
            sources = m.content.split("Sources:")[-1].strip().split(", ")
    return answer, sources