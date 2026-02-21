import os
import base64
from PIL import Image
import io
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# 1. SETUP
load_dotenv()
DB_PERSIST_DIRECTORY = "./chroma_db"

# --- 🚀 GROQ MODEL DEFINITIONS ---
# Using Groq's lightning-fast models for both tasks
TEXT_MODEL_NAME = "llama-3.1-8b-instant"          # Ultra-fast text model
VISION_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct" # Groq's free vision model

print("\n--- 🕵️‍♂️ INITIALIZING GROQ AI ENGINE ---")

if not os.getenv("GROQ_API_KEY"):
    print("❌ ERROR: GROQ_API_KEY not found in .env")
else:
    print(f"✅ Text Engine: {TEXT_MODEL_NAME}")
    print(f"✅ Vision Engine: {VISION_MODEL_NAME}")

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
        # 1. Open the image with Pillow
        with Image.open(image_path) as img:
            # 2. Convert to standard RGB (removes transparency layers from PNGs which cause errors)
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # 3. Smart Resize: If an image is larger than 1600px, scale it down proportionally
            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 4. Save to a temporary memory buffer (no extra files saved to your PC)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80, optimize=True)
            
            # Optional: Print the new size to your terminal so you can verify it works
            size_mb = buffer.tell() / (1024 * 1024)
            print(f"📉 Image optimized for API: {size_mb:.2f} MB")
            
            # 5. Convert to Base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None

def retrieve_context_with_sources(query, vectorstore):
    try:
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
    # 1. SMART ROUTER: Choose between Groq's Text or Vision model
    if image_path:
        print("📸 Image detected! Using Groq Vision Engine...")
        current_llm = get_groq_llm(VISION_MODEL_NAME)
    else:
        print("📝 Text only. Using Groq Fast Text Engine...")
        current_llm = get_groq_llm(TEXT_MODEL_NAME)

    # 2. GREETING CHECK
    query_lower = query.strip().lower()
    common_greetings = ["hi", "hello", "hey", "yo", "thanks", "good morning"]
    if any(query_lower.startswith(g) for g in common_greetings) and len(query.split()) < 4:
        use_rag = False

    # 3. PREPARE CONTEXT & SYSTEM PROMPT
    sources = []
    context_text = ""
    used_mode = "general"
    
    if use_rag:
        print(f"🔍 RAG MODE...")
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
            "5. **Visual Analysis:** If an image (such as a system diagram or previous year question paper) is provided, analyze it meticulously and connect it to the user's question.\n\n"
            f"--- HISTORY ---\n{chat_history}\n\n"
            f"--- CONTEXT ---\n{context_text}"
        )
    else:
        print(f"🌐 GENERAL MODE...")
        system_text = (
            "You are a helpful AI Assistant.\n"
            "Answer using general knowledge.\n"
            f"--- HISTORY ---\n{chat_history}"
        )

    # 4. PAYLOAD CONSTRUCTION (Groq LangChain Format)
    content_payload = []
    
    if image_path:
        b64 = encode_image(image_path)
        if b64:
            content_payload.append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
            
    content_payload.append({"type": "text", "text": query})

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=content_payload)
    ]

    # 5. EXECUTE
    try:
        response = current_llm.invoke(messages)
        return response.content, sources, used_mode
    except Exception as e:
        print(f"❌ Error on Groq API: {e}")
        if image_path:
             return "I'm sorry, my vision capabilities are currently unavailable due to server traffic. I can still answer text questions!", [], "general"
        return f"Error: The AI engine timed out. Please try again.", [], "error"