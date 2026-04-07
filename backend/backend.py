import os
import base64
from PIL import Image
import io
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder
import numpy as np
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# 1. SETUP
load_dotenv()
DB_PERSIST_DIRECTORY = "./chroma_db"

print("🧠 Loading Cross-Encoder Reranker...")
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# --- 🚀 GROQ MODEL DEFINITIONS ---
TEXT_MODEL_NAME = "llama-3.1-8b-instant"          # Ultra-fast text model
VISION_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct" # Vision model

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

# --- 🛠️ UTILS ---
def encode_image(image_path):
    """Encodes image to base64 with optimization for local-to-cloud transfer."""
    if not image_path or not os.path.exists(image_path): return None
    try:
        with Image.open(image_path) as img:
            # Convert to standard RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Resize for efficiency
            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to memory buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80, optimize=True)
            
            size_mb = buffer.tell() / (1024 * 1024)
            print(f"📉 Image optimized: {size_mb:.2f} MB")
            
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None

def retrieve_context_with_sources(query, vectorstore):
    """Stage 1: Broad Search. Stage 2: Deep Reranking."""
    try:
        # STAGE 1: Fast Vector Search (Get top 15 candidates)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 15})
        initial_docs = retriever.invoke(query)

        # STAGE 2: Cross-Encoder Reranking
        # We pair the user query with every chunk to score their actual relationship
        sentence_pairs = [[query, doc.page_content] for doc in initial_docs]
        scores = reranker.predict(sentence_pairs)

        # Sort the documents by their new, highly-accurate scores (Highest to Lowest)
        sorted_indices = np.argsort(scores)[::-1]
        
        # Keep only the absolute best 4 chunks for the LLM to read
        top_k_docs = [initial_docs[i] for i in sorted_indices[:4]]

        # Format context and extract unique sources (same as before)
        formatted_text = ""
        sources_with_pages = []
        for d in top_k_docs:
            name = os.path.basename(d.metadata.get('source', 'Unknown'))
            page = d.metadata.get('page', 0) + 1
            formatted_text += f"--- FROM: {name} (Page {page}) ---\n{d.page_content}\n\n"
            sources_with_pages.append(f"{name} [Pg. {page}]")

        unique_sources = list(dict.fromkeys(sources_with_pages))
        
        return formatted_text, unique_sources

    except Exception as e:
        print(f"❌ Reranking Error: {e}")
        return "", []

# --- 🧠 MAIN CHAT FUNCTION ---
def generate_llm_response(query, context_text, chat_history, image_path, use_rag=True):
    # 1. Choose Engine
    if image_path:
        print("📸 Vision Mode...")
        current_llm = get_groq_llm(VISION_MODEL_NAME)
    else:
        print("📝 Text Mode...")
        current_llm = get_groq_llm(TEXT_MODEL_NAME)

    # 2. Skip RAG formatting for small greetings
    query_lower = query.strip().lower()
    common_greetings = ["hi", "hello", "hey", "yo", "thanks", "good morning"]
    if any(query_lower.startswith(g) for g in common_greetings) and len(query.split()) < 4:
        use_rag = False

    # 3. Apply the Specialized SPPU System Prompt
    if use_rag and context_text:
        system_text = (
            "You are an elite Academic AI Assistant specifically designed for SPPU engineering students. "
            "Your primary role is to assist with rigorous exam preparation, simplify complex technical concepts, and break down logic step-by-step.\n\n"
            "### 🎯 CORE DIRECTIVES:\n"
            "1. **Context First:** Always attempt to answer using the provided **CONTEXT** first. If you use the context, you MUST cite the exact source document name at the end of your points.\n"
            "2. **The 'Out-of-Syllabus' Fallback:** If the user's query cannot be answered using the provided context, you MUST STILL answer the question using your general knowledge. However, you MUST begin your response with this exact warning: '⚠️ *I could not find this specific topic in your provided study materials, but based on general knowledge:*'\n"
            "3. **Study-Optimized Formatting:** Structure your answers to be highly readable for a student reviewing for exams. Use bullet points, bold key technical terms, and provide concise summaries.\n"
            "4. **Technical Precision:** When explaining algorithms, data structures, or engineering principles, break down the logic systematically.\n"
            "5. **Visual Analysis:** If an image (diagram/paper) is provided, analyze it meticulously and connect it to the user's question.\n\n"
            f"--- HISTORY ---\n{chat_history}\n\n"
            f"--- CONTEXT ---\n{context_text}"
        )
    else:
        system_text = (
            "You are a helpful SPPU AI Assistant. Answer based on general engineering knowledge.\n"
            f"--- HISTORY ---\n{chat_history}"
        )

    # 4. Payload Construction
    content_payload = []
    if image_path:
        # We pass the image_path directly here if your api.py saves it temporarily, 
        # or adjust if api.py is passing the raw base64 string.
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

    try:
        response = current_llm.invoke(messages)
        return response.content
    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return "I encountered an error while processing that request. Please try again."