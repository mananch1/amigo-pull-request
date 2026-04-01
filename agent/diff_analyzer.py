import requests
import json

def get_pr_diff(repo_full_name, pr_number, github_token=None):
    """
    Fetches the pull request diff from GitHub.
    repo_full_name: e.g. 'pallets/click'
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff"
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
        
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Error fetching PR diff: {response.status_code} - {response.text}")
        return None

def extract_changed_files(diff_text):
    """
    Parses a raw git diff and extracts minimal context for the LLM
    """
    if not diff_text:
        return []
    
    # A simple parser that just splits by 'diff --git'
    files_diffs = diff_text.split("diff --git")
    
    changes = []
    for f in files_diffs:
        if not f.strip():
            continue
        # Get filename
        lines = f.strip().split("\n")
        header = lines[0]
        try:
            filename = header.split(" b/")[1]
            changes.append({
                "file": filename,
                "diff": "diff --git " + f
            })
        except IndexError:
            continue
            
    return changes
