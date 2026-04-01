import sys
import os
import glob
from dotenv import load_dotenv
load_dotenv()

# Ensure we can import from ingest package
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="PR Review Agent Webhook")

@app.get("/")
def read_root():
    reviews_html = ""
    reviews_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reviews")
    
    if os.path.exists(reviews_dir):
        files = glob.glob(os.path.join(reviews_dir, "*.md"))
        files.sort(key=os.path.getmtime, reverse=True) # newest first
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
            name = os.path.basename(file).replace(".md", "")
            reviews_html += f"<div class='review'><h3>{name}</h3><div class='markdown-body'>{content}</div></div>"
            
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI PR Review Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body {{ font-family: 'Inter', -apple-system, sans-serif; padding: 40px; background: #0d1117; color: #c9d1d9; max-width: 1000px; margin: auto; }}
            h1 {{ color: #58a6ff; text-align: center; margin-bottom: 40px; }}
            .review {{ background: #161b22; border: 1px solid #30363d; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            .review h3 {{ margin-top: 0; color: #8b949e; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
            .markdown-body {{ line-height: 1.6; }}
            .markdown-body pre {{ background: #0d1117; padding: 15px; border-radius: 6px; overflow-x: auto; }}
            .markdown-body code {{ font-family: monospace; background: #0d1117; padding: 2px 5px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>Recent Pull Request Reviews</h1>
        <div id="content">
            {reviews_html if reviews_html else "<p style='text-align:center;'>No reviews generated yet. Trigger your first webhook!</p>"}
        </div>
        <script>
            // Convert all markdown-body divs to HTML
            document.querySelectorAll('.markdown-body').forEach(function(el) {{
                el.innerHTML = marked.parse(el.textContent);
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/webhook")
async def github_webhook(request: Request):
    payload = await request.json()
    
    # Listen only for pull request events
    event_type = request.headers.get("X-GitHub-Event")
    if event_type == "pull_request":
        action = payload.get("action")
        pr_number = payload.get("number")
        repo_url = payload["repository"]["clone_url"]
        
        # We process opened or synchronize (pushed new commits) events
        if action in ["opened", "synchronize"]:
            print(f"Triggering Review Pipeline for {repo_url}...", flush=True)
            repo_full_name = payload["repository"]["full_name"]
            
            from agent.diff_analyzer import get_pr_diff, extract_changed_files
            from agent.reviewer import generate_review
            
            diff_text = get_pr_diff(repo_full_name, pr_number)
            if not diff_text:
                return {"status": "Failed to fetch diff"}
                
            changes = extract_changed_files(diff_text)
            
            if not changes:
                return {"status": "No valid file changes found"}
                
            print(f"Extracted {len(changes)} file changes. Requesting LLM reviews...", flush=True)
            reviews = generate_review(changes)
            
            reviews_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reviews")
            os.makedirs(reviews_dir, exist_ok=True)
            
            # Print the reviews securely to the console for MVP and save to disk
            print("\n" + "="*40, flush=True)
            print(f"🤖 Review for PR #{pr_number}", flush=True)
            for r in reviews:
                file_safe = r['file'].replace("/", "_").replace("\\", "_")
                save_path = os.path.join(reviews_dir, f"PR_{pr_number}_{file_safe}.md")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(r["review"])
                    
                print(f"--- File: {r['file']} ---", flush=True)
                print(r["review"], flush=True)
            print("="*40 + "\n", flush=True)
            
            return {"status": "Review completed", "reviews_generated": len(reviews)}
            
    return {"status": "Ignored event"}

if __name__ == "__main__":
    print("Starting Webhook Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
