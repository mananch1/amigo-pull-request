import os
from git import Repo
from ingest.parser import parse_file

REPO_URL = "https://github.com/mananch1/DS_ALL_Experiments.git"
CLONE_DIR = "data/repos/sample_repo"

def clone_repo():
    if not os.path.exists(CLONE_DIR):
        Repo.clone_from(REPO_URL, CLONE_DIR)
    return CLONE_DIR


def get_python_files(repo_path):
    py_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files


from ingest.embedder import get_embedding
from ingest.store import VectorStore

if __name__ == "__main__":
    repo_path = clone_repo()
    files = get_python_files(repo_path)
    store = VectorStore()

    for f in files[:3]:  # test first 3 files
        parsed = parse_file(f)
        chunks = parsed["chunks"]
        imports = parsed["imports"]
        print(f"\nProcessing File: {f}")
        
        # Store file imports as a separate metadata chunk
        if imports:
            emb = get_embedding(" ".join(imports))
            store.add(emb, {
                "file": f,
                "type": "imports",
                "imports": imports
            })

        for c in chunks:
            print(f"Embedding Function: {c['name']}")
            emb = get_embedding(c["code"])
            store.add(emb, {
                "file": f,
                "type": "function",
                "name": c["name"],
                "code": c["code"],
                "calls": c.get("calls", [])
            })

    print(f"\nIngestion complete! Total vectors stored: {store.index.ntotal}")
    store.save()
    print("Saved Vector DB to data/faiss_index.bin")

    print("\n--- Testing FAISS Search ---")
    query = "function parameter argument"
    print(f"Searching for: '{query}'")
    q_emb = get_embedding(query)
    results = store.search(q_emb, k=2)
    
    for r in results:
        name = r.get("name", "imports node")
        print(f"Match: {name} in ({r['file']})")
