import os
import sys
from groq import Groq
from dotenv import load_dotenv

# Ensure we can import from ingest package
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ingest.store import VectorStore
from ingest.embedder import get_embedding

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=groq_api_key) if groq_api_key else None

if not groq_client:
    print("[WARNING] GROQ_API_KEY not set. LLM reviews will fail.")

# Initialize and load vector DB
store = VectorStore()
try:
    store.load()
    print("Loaded Vector DB context successfully.")
except Exception as e:
    print(f"Warning: Could not load Vector DB. Run ingest/main.py first. ({e})")

def generate_review(pr_diff_changes):
    if not groq_client:
        return [{"file": "Error", "review": "GROQ_API_KEY not configured."}]

    reviews = []
    
    for change in pr_diff_changes:
        filename = change["file"]
        diff = change["diff"]
        
        # Query context from the Vector DB based on the file and diff snippet
        search_query = f"File {filename} diff context" 
        q_emb = get_embedding(search_query)
        # Search the top 3 similar chunks to give context
        context_results = store.search(q_emb, k=3)
        
        context_text = "\n\n".join([
            f"Context from {r['file']} (Type: {r['type']}):\n{r.get('code', r.get('imports', ''))}" 
            for r in context_results
        ])
        
        prompt = f"""You are a senior software engineer reviewing a pull request.
We are reviewing changes for the file: {filename}

Here is the Git Diff:
```diff
{diff}
```

Here is related contextual code from the repository (functions, imports, etc.) to help you understand the surrounding codebase context:
```python
{context_text}
```

Focus on:
1. Bugs or logical errors
2. Missing edge cases
3. Performance or security issues
4. Actionable feedback

If the diff looks perfectly fine and has no issues, simply output "Looks good to me!". Provide your review in markdown format.
"""
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        reviews.append({
            "file": filename,
            "review": response.choices[0].message.content
        })
        
    return reviews
