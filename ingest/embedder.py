import os
from google import genai
from dotenv import load_dotenv
load_dotenv()

# Configure Google Gemini API (Free tier available)
api_key = os.getenv("GEMINI_API_KEY")
is_valid_key = api_key and not api_key.startswith("your_")

if is_valid_key:
    client = genai.Client(api_key=api_key)
else:
    client = None
    print("[WARNING] GEMINI_API_KEY not configured or is placeholder! Using dummy embedding.")

def get_embedding(text):
    if not client:
        return [0.0] * 768
        
    try:
        response = client.models.embed_content(
            model='text-embedding-004',
            contents=text,
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"[Gemini API Error] {e} - Falling back to dummy embeddings temporarily.")
        return [0.0] * 768
