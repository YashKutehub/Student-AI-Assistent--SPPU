import os
import base64
from functools import lru_cache
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

print("🧠 Loading Embedding + Reranker engines...")



@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-base-en-v1.5",
        model_kwargs={"device": "cpu"},        
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,                   
        },
    )

# 
@lru_cache(maxsize=1)
def get_reranker():
    return CrossEncoder('BAAI/bge-reranker-base')


@lru_cache(maxsize=1)
def get_vectorstore():
    return Chroma(persist_directory=DB_PERSIST_DIRECTORY, embedding_function=get_embeddings())

# --- 🚀 GROQ MODEL DEFINITIONS ---
TEXT_MODEL_NAME = "llama-3.3-70b-versatile"         # 70b parameter text model
VISION_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"  # Vision model

print("\n--- 🕵️‍♂️ INITIALIZING GROQ AI ENGINE ---")

if not os.getenv("GROQ_API_KEY"):
    print("❌ ERROR: GROQ_API_KEY not found in .env")
else:
    print(f"✅ Text Engine: {TEXT_MODEL_NAME}")
    print(f"✅ Vision Engine: {VISION_MODEL_NAME}")


@lru_cache(maxsize=4)
def get_groq_llm(model_name):
    """Creates and reuses a Groq LLM instance for lower startup overhead."""
    return ChatGroq(
        model_name=model_name,
        temperature=0.2,
        max_tokens=700,
        max_retries=1,
    )

# --- 🛠️ UTILS ---
def encode_image(image_path):
    """Encodes image to base64 with optimization for local-to-cloud transfer."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')

            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80, optimize=True)

            size_mb = buffer.tell() / (1024 * 1024)
            print(f"📉 Image optimized: {size_mb:.2f} MB")

            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None


#
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

#
RERANK_CONFIDENCE_THRESHOLD = 0.0


def retrieve_context_with_sources(query, vectorstore):
    """Stage 1: Fast candidate retrieval. Stage 2: Cross-encoder reranking for precision."""
    try:
        
        search_query = BGE_QUERY_PREFIX + query

       
        retriever = vectorstore.as_retriever(search_kwargs={"k": 20})
        initial_docs = retriever.invoke(search_query)
        if not initial_docs:
            return "", []

        
      
        reranker = get_reranker()
        sentence_pairs = [[query, doc.page_content] for doc in initial_docs]
        scores = np.asarray(reranker.predict(sentence_pairs), dtype=np.float32)

        sorted_indices = np.argsort(scores)[::-1]

        #
        top_indices = [int(i) for i in sorted_indices if scores[i] >= RERANK_CONFIDENCE_THRESHOLD][:4]

        #
        if not top_indices:
            print("⚠️ No chunk passed the confidence threshold — falling back to general knowledge.")
            return "", []

        top_k_docs = [initial_docs[i] for i in top_indices]

        # 
        print("🔎 Retrieved chunks (reranked):")
        for i in top_indices:
            src = os.path.basename(initial_docs[i].metadata.get('source', 'Unknown'))
            print(f"   score={scores[i]:.3f}  src={src}")

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
            "You are an elite Academic AI Assistant for SPPU engineering students. "
            "Your job is rigorous exam prep: simplify complex concepts and explain logic step-by-step.\n\n"
            "### 🎯 CORE DIRECTIVES:\n"
            "1. **Context is the source of truth.** Answer using ONLY the provided CONTEXT below whenever it "
            "contains the answer. Do NOT add outside facts when the context already covers the topic. "
            "Cite the exact source document name at the end of the relevant points.\n"
            "2. **Partial-context handling:** If the CONTEXT only partially answers the question, answer the "
            "covered part from context (and cite it), then clearly mark any added explanation as general knowledge.\n"
            "3. **True fallback only:** If the CONTEXT does not address the question at all, you MUST begin your "
            "response with this exact warning: '⚠️ *I could not find this specific topic in your provided study "
            "materials, but based on general knowledge:*' and then answer.\n"
            "4. **Study formatting:** STRICTLY follow the user's requested format. "
                  "If the user asks for 7-8 points, give exactly 7-8 points. "
                  "If the user asks for a brief answer, be concise. "
                  "If the user asks for a table, use a table. "
                  "If no format is specified, default to clear numbered points with bold key terms.\n"
            "5. **Technical precision:** Break down algorithms, data structures, and engineering logic systematically.\n"
            "6. **Visual analysis:** If an image (diagram/paper) is provided, analyze it and connect it to the question.\n\n"
            f"--- HISTORY ---\n{chat_history}\n\n"
            f"--- CONTEXT ---\n{context_text}"
        )
    else:
        
        system_text = (
            "You are a helpful SPPU AI Assistant. No specific study material was found for this question, "
            "so answer using general engineering knowledge. Begin your answer with this exact warning: "
            "'⚠️ *I could not find this specific topic in your provided study materials, but based on general knowledge:*'\n"
            f"--- HISTORY ---\n{chat_history}"
        )

    # 4. Payload Construction
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

    try:
        response = current_llm.invoke(messages)
        return response.content
    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return "I encountered an error while processing that request. Please try again."