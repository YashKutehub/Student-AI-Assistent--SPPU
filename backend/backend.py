import os
import base64
from PIL import Image
import io
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma
# Switched from HuggingFace to Google
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# 1. SETUP
load_dotenv()
DB_PERSIST_DIRECTORY = "./chroma_db"

# --- 🚀 GROQ MODEL DEFINITIONS ---
TEXT_MODEL_NAME = "llama-3.1-8b-instant"          
VISION_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct" 

print("\n--- 🕵️‍♂️ INITIALIZING GROQ AI ENGINE ---")

if not os.getenv("GROQ_API_KEY"):
    print("❌ ERROR: GROQ_API_KEY not found in .env")
else:
    print(f"✅ Text Engine: {TEXT_MODEL_NAME}")
    print(f"✅ Vision Engine: {VISION_MODEL_NAME}")

# --- NEW: GOOGLE EMBEDDINGS CONFIG ---
# We initialize this once so it can be reused by the vectorstore
print("🧠 Initializing Google Embedding Engine...")
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query" # 'retrieval_query' is optimized for searching
)

def get_groq_llm(model_name):
    """Creates a Groq LLM instance."""
    return ChatGroq(
        model_name=model_name,
        temperature=0.7,
        max_retries=2,
    )

# --- UTILS ---
def encode_image(image_path):
    if not image_path or not os.path.exists(image_path): return None
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None

def retrieve_context_with_sources(query, vectorstore):
    try:
        # The vectorstore now uses the Google embeddings passed from api.py
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        docs = retriever.invoke(query)
        formatted_text = "\n\n".join([f"--- FROM DOCUMENT: {os.path.basename(d.metadata.get('source', 'Unknown'))} ---\n{d.page_content}" for d in docs])
        sources = list(set([os.path.basename(d.metadata.get("source", 'Unknown')) for d in docs]))
        return formatted_text, sources
    except Exception as e:
        print(f"Retrieval Error: {e}")
        return "", []

# --- MAIN CHAT FUNCTION ---
def ask_gemini_multimodal(query, chat_history, image_path, vectorstore, use_rag=True):
    if image_path:
        current_llm = get_groq_llm(VISION_MODEL_NAME)
    else:
        current_llm = get_groq_llm(TEXT_MODEL_NAME)

    query_lower = query.strip().lower()
    common_greetings = ["hi", "hello", "hey", "yo", "thanks", "good morning"]
    if any(query_lower.startswith(g) for g in common_greetings) and len(query.split()) < 4:
        use_rag = False

    sources = []
    context_text = ""
    used_mode = "general"
    
    if use_rag:
        used_mode = "rag"
        context_text, sources = retrieve_context_with_sources(query, vectorstore)
        system_text = (
            "You are an elite Academic AI Assistant specifically designed for SPPU engineering students. "
            "Your primary role is to assist with rigorous exam preparation, simplify complex technical concepts, and break down logic step-by-step.\n\n"
            "### 🎯 CORE DIRECTIVES:\n"
            "1. **Context First:** Always attempt to answer using the provided **CONTEXT** first. If you use the context, you MUST cite the exact source document name at the end of your points.\n"
            "2. **The 'Out-of-Syllabus' Fallback:** If the user's query cannot be answered using the provided context, you MUST STILL answer the question using your general knowledge. However, you MUST begin your response with this exact warning: '⚠️ *I could not find this specific topic in your provided study materials, but based on general knowledge:*'\n"
            "3. **Study-Optimized Formatting:** Structure your answers to be highly readable for a student reviewing for exams. Use bullet points, bold key technical terms, and provide concise summaries.\n"
            "4. **Technical Precision:** When explaining algorithms, data structures, or engineering principles, break down the logic systematically.\n"
            "5. **Visual Analysis:** If an image is provided, analyze it meticulously and connect it to the user's question.\n\n"
            f"--- HISTORY ---\n{chat_history}\n\n"
            f"--- CONTEXT ---\n{context_text}"
        )
    else:
        system_text = (
            "You are a helpful AI Assistant.\n"
            "Answer using general knowledge.\n"
            f"--- HISTORY ---\n{chat_history}"
        )

    content_payload = [{"type": "text", "text": query}]
    if image_path:
        b64 = encode_image(image_path)
        if b64:
            content_payload.insert(0, {
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

    messages = [SystemMessage(content=system_text), HumanMessage(content=content_payload)]

    try:
        response = current_llm.invoke(messages)
        return response.content, sources, used_mode
    except Exception as e:
        print(f"❌ Error on Groq API: {e}")
        return "The AI engine is currently busy. Please try again in a moment.", [], "error"