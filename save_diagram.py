import urllib.request
import base64
import json
import sys

mermaid_code = """
flowchart TD
    classDef trigger fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    classDef agent fill:#161b22,stroke:#8b949e,stroke-width:1px,color:#fff
    classDef action fill:#238636,stroke:#2ea043,stroke-width:2px,color:#fff
    classDef user fill:#8957e5,stroke:#d2a8ff,stroke-width:2px,color:#fff
    classDef data fill:#1f2428,stroke:#d1d5da,stroke-width:1px,color:#e1e4e8

    subgraph Phase 1: Review Generation
        A["GitHub Webhook (PR Opened)"]:::trigger --> B["FastAPI Server (/webhook)"]:::data
        B --> C["Diff Analyzer"]:::agent
        C -- Extracts Changed Files --> D["Vector DB (Context Search)"]:::data
        C & D --> E["Reviewer Agent (Groq / Llama-3.3)"]:::agent
        E -- Outputs Strict JSON --> F["Save to data/reviews/*.json"]:::data
    end

    subgraph Phase 2: Client Portal
        F -. API Fetch (/api/reviews) .-> G["Dashboard UI (index.html)"]:::user
        G -- User parses issues --> H["Select Checkboxes"]:::user
        H -- Clicks 'Autofix' --> I["POST /api/fix payload"]:::trigger
    end

    subgraph Phase 3: Agentic Resolution
        I --> J["Gemini Orchestrator (gemini-2.5-flash)"]:::agent
        J -- Creates JSON reasoning plan & targets files --> K["Groq Patch Worker (Llama-3.3)"]:::agent
        K -- Outputs strict Unified Git Diff --> L["Save Patch (data/fixed_prs/)"]:::action
        L -. Returns success signal .-> M["UI Loader completes & previews patch"]:::user
    end
"""

state = {"code": mermaid_code, "mermaid": {"theme": "base"}}
json_str = json.dumps(state)
encoded = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
url = f"https://mermaid.ink/img/{encoded}?type=jpeg"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
print("Downloading JPEG from Mermaid Ink API...")
try:
    with urllib.request.urlopen(req) as response, open("agent_workflow.jpeg", "wb") as out_file:
        out_file.write(response.read())
    print("Successfully saved to agent_workflow.jpeg")
except Exception as e:
    print(f"Error downloading: {e}")
    sys.exit(1)
