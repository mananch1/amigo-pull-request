import urllib.request
import base64
import json
import sys

mermaid_code = """
flowchart TD
    classDef trigger fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    classDef logic fill:#161b22,stroke:#8b949e,stroke-width:1px,color:#fff
    classDef model fill:#8957e5,stroke:#d2a8ff,stroke-width:2px,color:#fff
    classDef storage fill:#238636,stroke:#2ea043,stroke-width:2px,color:#fff
    classDef data fill:#1f2428,stroke:#d1d5da,stroke-width:1px,color:#e1e4e8

    A["Target Repository URL"]:::trigger --> B["clone_repo() (GitPython)"]:::logic
    B --> C["get_python_files() (Walk Directory)"]:::logic
    
    C --> D{"Iterate through .py files"}:::data
    
    subgraph Tree-sitter AST Extraction
        D --> E["parse_file() (Tree-sitter)"]:::logic
        E -. Extracts .-> F["File Imports"]:::data
        E -. Extracts .-> G["Code Chunks (Functions/Classes)"]:::data
    end
    
    subgraph Embedding Generation
        F --> H["get_embedding() (Google Gemini)"]:::model
        G --> H
    end
    
    subgraph Vector Database
        H -- Generates dense vector --> I["store.add()"]:::logic
        I --> J["FAISS Vector Store"]:::storage
        J -- Saves to disk --> K["data/faiss_index.bin"]:::storage
    end
"""

state = {"code": mermaid_code, "mermaid": {"theme": "base"}}
json_str = json.dumps(state)
encoded = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
url = f"https://mermaid.ink/img/{encoded}?type=jpeg"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
print("Downloading JPEG from Mermaid Ink API...")
try:
    with urllib.request.urlopen(req) as response, open("ingestion_workflow.jpeg", "wb") as out_file:
        out_file.write(response.read())
    print("Successfully saved to ingestion_workflow.jpeg")
except Exception as e:
    print(f"Error downloading: {e}")
    sys.exit(1)
