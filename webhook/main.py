import sys
import os
import glob
import json
from dotenv import load_dotenv

load_dotenv()

# Ensure we can import from ingest package
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI(title="PR Review Agent Webhook")

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

NGROK_URL = None

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

def build_tree(dir_path, ignore_dirs):
    tree = {"name": os.path.basename(dir_path) or dir_path, "type": "directory", "children": []}
    try:
        entries = sorted(os.listdir(dir_path))
        for entry in entries:
            # Simple substring skip for bulky stuff
            if any(ign in entry for ign in ignore_dirs):
                continue
            full_path = os.path.join(dir_path, entry)
            if os.path.isdir(full_path):
                tree["children"].append(build_tree(full_path, ignore_dirs))
            else:
                tree["children"].append({"name": entry, "type": "file"})
    except PermissionError:
        pass
    return tree

@app.get("/tree")
def read_tree():
    return FileResponse(os.path.join(static_dir, "tree.html"))

@app.get("/api/ngrok")
def get_ngrok_url():
    if NGROK_URL:
        return {"status": "success", "url": f"{NGROK_URL}/webhook"}
    return {"status": "error", "message": "Ngrok tunnel not detected"}

from typing import Optional

class RepoMonitorRequest(BaseModel):
    url: str

@app.post("/api/repo")
def monitor_repo(request: RepoMonitorRequest):
    repo_url = request.url
    if not repo_url.startswith("https://github.com/"):
        return {"status": "error", "message": "Only GitHub URLs are supported."}
    
    # Extract username_repo
    repo_url_clean = repo_url.rstrip("/")
    if repo_url_clean.endswith(".git"):
        repo_url_clean = repo_url_clean[:-4]
        
    parts = repo_url_clean.split("/")
    if len(parts) < 2:
        return {"status": "error", "message": "Invalid GitHub URL format."}
    repo_name = f"{parts[-2]}_{parts[-1]}"
    github_name = f"{parts[-2]}/{parts[-1]}"
    
    clone_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "repos", repo_name))
    os.makedirs(os.path.dirname(clone_dir), exist_ok=True)
    
    try:
        from ingest.main import clone_repo, run_ingestion
        print(f"Cloning {repo_url} into {clone_dir}...", flush=True)
        clone_repo(repo_url, clone_dir=clone_dir)
        
        print(f"Running partial AST ingestion into FAISS vector db...", flush=True)
        vectors = run_ingestion(clone_dir, max_files=5)
        
        return {
            "status": "success", 
            "repo_id": repo_name,
            "github_name": github_name,
            "message": f"Cloned & {vectors} vectors embedded!"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to map repository: {str(e)}"}

@app.get("/api/tree")
def get_tree(repo_id: Optional[str] = None):
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    if repo_id:
        root_dir = os.path.join(base_dir, "data", "repos", repo_id)
        if not os.path.exists(root_dir):
            return {"error": "Repository not found locally."}
    else:
        root_dir = base_dir

    ignore_dirs = {".git", ".venv", "__pycache__", "DockerData", "faiss_index.bin"}
    tree_data = build_tree(root_dir, ignore_dirs)
    tree_data["name"] = repo_id if repo_id else "amigo-pull-request"
    return tree_data

@app.get("/api/reviews")
def get_reviews():
    reviews_data = []
    reviews_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reviews")
    
    if os.path.exists(reviews_dir):
        files = glob.glob(os.path.join(reviews_dir, "*.json"))
        # Fallback to legacy Markdown files if there are any that haven't been upgraded
        md_files = glob.glob(os.path.join(reviews_dir, "*.md"))
        
        files.extend(md_files)
        files.sort(key=os.path.getmtime, reverse=True) # newest first
        
        for file in files:
            try:
                if file.endswith(".json"):
                    with open(file, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    
                    content["id"] = os.path.basename(file).replace(".json", "")
                    # Give it a safe format if parsing didn't match perfectly
                    if "issues" not in content:
                        content["issues"] = []
                    reviews_data.append(content)
                else:
                    # Legacy Markdown formatting parsing just in case
                    with open(file, "r", encoding="utf-8") as f:
                        text = f.read()
                    reviews_data.append({
                        "id": os.path.basename(file).replace(".md", ""),
                        "file": "Legacy Markdown Review",
                        "summary": text,
                        "issues": []
                    })
            except Exception as e:
                print(f"Error loading {file}: {e}")
                
    return {"reviews": reviews_data}

@app.get("/api/ast")
def get_ast(filepath: str, repo_id: Optional[str] = None):
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    if repo_id:
        root_dir = os.path.abspath(os.path.join(base_dir, "data", "repos", repo_id))
    else:
        root_dir = os.path.abspath(base_dir)

    # prevent directory traversal outside root context
    full_path = os.path.abspath(os.path.join(root_dir, filepath))
    if not full_path.startswith(root_dir) or not full_path.endswith(".py"):
        return {"error": "Invalid or unauthorized python file path"}
    
    try:
        from ingest.parser import parse_file
        parsed_data = parse_file(full_path)
        return {"status": "success", "data": parsed_data}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

class FixRequest(BaseModel):
    repo_url: str
    pr_number: str
    issues: List[str]

@app.post("/api/fix")
def fix_issues(request: FixRequest):
    if not request.issues:
        return {"status": "error", "message": "No issues selected"}
        
    issues_text = "\n".join([f"- {issue}" for issue in request.issues])
    problem_statement = f"The user selected the following issues to be fixed from the PR code review:\n{issues_text}\nPlease resolve these issues."
    
    # Dynamic Repository Mapping
    repo_url_clean = request.repo_url.rstrip("/")
    if repo_url_clean.endswith(".git"):
        repo_url_clean = repo_url_clean[:-4]
        
    parts = repo_url_clean.split("/")
    repo_name = f"{parts[-2]}_{parts[-1]}"
    repo_full_name = f"{parts[-2]}/{parts[-1]}"
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "repos", repo_name))

    from agent.diff_analyzer import get_pr_diff, extract_changed_files
    github_token = os.getenv("GITHUB_TOKEN")
    
    print(f"Fetching PR {request.pr_number} metadata to isolate affected files...", flush=True)
    diff_text = get_pr_diff(repo_full_name, request.pr_number, github_token)
    changed_targets = [c["file"] for c in extract_changed_files(diff_text)]

    available_files = []
    repo_code_dump = ""
    
    if os.path.exists(repo_dir):
        for target in changed_targets:
            if not target.endswith(".py"): continue
            
            full_path = os.path.join(repo_dir, target.replace("/", os.sep).replace("\\\\", os.sep))
            if os.path.exists(full_path):
                available_files.append(target)
                try:
                    with open(full_path, "r", encoding="utf-8") as pf:
                        repo_code_dump += f"\n\n--- {target} ---\n{pf.read()}"
                except Exception:
                    pass
                    
    repo_context = f"The target PR heavily impacts the following isolated files:\n{chr(10).join(available_files)}\n\nYou MUST strictly target these files for fixes.\n\n### AFFECTED CODEBASE CONTEXT ###\n{repo_code_dump}"

    from agent.orchestrator import GeminiOrchestrator
    from agent.worker import GroqWorker
    
    orchestrator = GeminiOrchestrator()
    worker = GroqWorker()
    
    print(f"Planning fix for PR {request.pr_number}...", flush=True)
    plan_result, _ = orchestrator.plan_resolution(problem_statement, repo_context)
    
    reasoning_plan = plan_result.get("reasoning_plan", "No plan generated.")
    target_files = plan_result.get("target_files", [])
    
    print(f"Files targeted: {target_files}", flush=True)
    
    files_content_dict = {}
    if os.path.exists(repo_dir) and target_files:
        for t_file in target_files:
            # Safely handle mixed slashes
            safe_t_file = t_file.replace("/", os.sep).replace("\\", os.sep)
            file_path = os.path.join(repo_dir, safe_t_file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        files_content_dict[t_file] = f.read()
                except Exception as e:
                    print(f"Error reading {t_file}: {e}")
                    
    if not files_content_dict:
        print("Warning: Could not source target files locally. Falling back to mock.", flush=True)
        files_content_dict = {"mock_file.py": "# Mock content\\n# Agentic Fixer Placeholder"} 
    
    print("Generating Patch...", flush=True)
    patch, _ = worker.generate_patch(reasoning_plan, files_content_dict)
    
    # Save the simulated fix patch locally
    fixes_dir = os.path.join(os.path.dirname(__file__), "..", "data", "fixed_prs")
    os.makedirs(fixes_dir, exist_ok=True)
    fix_path = os.path.join(fixes_dir, f"fix_pr_{request.pr_number}.patch")
    
    with open(fix_path, "w", encoding="utf-8") as f:
        f.write(patch)
        
    # Dispatch patch directly to Github Issue API
    github_token = os.getenv("GITHUB_TOKEN")
    github_status = "Skipped (No GITHUB_TOKEN found in .env)"
    
    if github_token and patch.strip():
        try:
            import urllib.request
            import json
            import subprocess
            
            repo_full_name = f"{parts[-2]}/{parts[-1]}"
            pr_api_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{request.pr_number}"
            issue_url = f"https://api.github.com/repos/{repo_full_name}/issues/{request.pr_number}/comments"
            
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Amigo-Agentic-Reviewer"
            }
            
            # 1. Post Comment
            body_text = f"🤖 **Amigo Agentic Autofix Generated**\\n\\nThe orchestrator has dynamically resolved the selected issues. Below is the file-level rewrite payload generated:\\n\\n```python\\n{patch[:1500]}\\n# ... (truncated for PR summary)\\n```\\n\\n*Applying directly to branch locally and pushing...*"
            data = json.dumps({"body": body_text}).encode("utf-8")
            
            req = urllib.request.Request(issue_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as res:
                if res.status == 201:
                    github_status = f"✅ Commented on PR #{request.pr_number}"
                else:
                    github_status = f"Comment Failed. HTTP {res.status}"
                    
            # 2. Native Branch Push Logic
            # Fetch Pull request target
            req_pr = urllib.request.Request(pr_api_url, headers=headers, method="GET")
            with urllib.request.urlopen(req_pr) as res_pr:
                pr_data = json.loads(res_pr.read().decode('utf-8'))
                head_branch = pr_data['head']['ref']
                head_clone_url = pr_data['head']['repo']['clone_url']
            
            # Auth Git Url inside Repo
            auth_url = head_clone_url.replace("https://", f"https://oauth2:{github_token}@")
            
            print(f"Agentic Branch Checkout: {head_branch}", flush=True)
            subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=repo_dir, check=True)
            subprocess.run(["git", "fetch", "origin", head_branch], cwd=repo_dir, check=True)
            subprocess.run(["git", "checkout", head_branch], cwd=repo_dir, check=True)
            
            print("Applying Agent Patch Natively...", flush=True)
            import re
            
            blocks = re.findall(r"<<<FILE:\s*(.+?)>>>(.*?)<<<ENDFILE>>>", patch, re.DOTALL)
            files_changed = 0
            for filepath, content in blocks:
                safe_filepath = filepath.strip().replace("\\\\", os.sep).replace("/", os.sep)
                full_path = os.path.join(repo_dir, safe_filepath)
                # Ensure it's inside repo_dir for safety
                if os.path.commonpath([repo_dir, os.path.abspath(full_path)]) == repo_dir:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content.strip("\\n") + "\\n")
                    files_changed += 1
            
            if files_changed == 0:
                print("Warning: No exact <<<FILE>>> blocks parsed from LLM output. Fallback to writing the entire patch as a single main update.", flush=True)
                if len(target_files) == 1:
                    fallback_path = os.path.join(repo_dir, target_files[0].replace("\\\\", os.sep).replace("/", os.sep))
                    with open(fallback_path, "w", encoding="utf-8") as f:
                        clean_patch = re.sub(r"^```[a-zA-Z]*\\n", "", patch.strip())
                        clean_patch = re.sub(r"\\n```$", "", clean_patch)
                        f.write(clean_patch)

            subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
            
            # Check if there are changes to commit
            status_res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
            if status_res.stdout.strip():
                subprocess.run(["git", "config", "user.email", "bot@amigoreviewer.com"], cwd=repo_dir)
                subprocess.run(["git", "config", "user.name", "Amigo Agent"], cwd=repo_dir)
                subprocess.run(["git", "commit", "-m", "🤖 Agentic Autofix Applied natively"], cwd=repo_dir, check=True)
                
                print(f"Pushing to origin {head_branch}...", flush=True)
                subprocess.run(["git", "push", "origin", head_branch], cwd=repo_dir, check=True)
                github_status += " | 🚀 Pushed to Branch Successfully!"
            else:
                github_status += " | ⚠️ Patch applied but resulted in no code changes."

        except Exception as e:
            github_status = f"Error during Github Push execution: {str(e)}"
    
    return {
        "status": "success", 
        "patch": patch, 
        "saved_to": fix_path, 
        "github_status": github_status
    }

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
            
            print("\n" + "="*40, flush=True)
            print(f"🤖 Review for PR #{pr_number}", flush=True)
            for r in reviews:
                try:
                    review_str = r.get("review", "{}")
                    review_data = json.loads(review_str)
                    
                    review_data["pr_number"] = str(pr_number)
                    review_data["repo_url"] = repo_url
                    
                    file_safe = r['file'].replace("/", "_").replace("\\", "_")
                    save_path = os.path.join(reviews_dir, f"PR_{pr_number}_{file_safe}.json")
                    
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(review_data, f, indent=4)
                        
                    print(f"--- Saved JSON Review for: {r['file']} ---", flush=True)
                except Exception as e:
                    print(f"Failed to parse or save JSON review for {r['file']}: {e}", flush=True)
                    print(f"Raw output was: {r.get('review')}", flush=True)
            print("="*40 + "\n", flush=True)
            
            return {"status": "Review completed", "reviews_generated": len(reviews)}
            
    return {"status": "Ignored event"}

if __name__ == "__main__":
    print("Starting Webhook Server on port 8000...")
    
    try:
        from pyngrok import ngrok
        http_tunnel = ngrok.connect(8000)
        NGROK_URL = http_tunnel.public_url
        print("=="*30)
        print(f"✅ NGROK TUNNEL CREATED: {NGROK_URL}/webhook")
        print("=="*30, flush=True)
    except Exception as e:
        print(f"❌ Failed to start Ngrok tunnel: {e}")

    uvicorn.run(app, host="0.0.0.0", port=8000)
