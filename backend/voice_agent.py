import edge_tts

async def generate_tutor_audio(text: str):
    """
    Takes LLM text and generates an audio byte stream using free Microsoft Azure Neural voices.
    """
    voice_id = "en-US-AriaNeural" 
    print(f"📡 Requesting free Azure audio (Voice: {voice_id})...")
    
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
                
        return audio_bytes

    except Exception as e:
        print(f"❌ Edge-TTS Error: {e}")
        return None