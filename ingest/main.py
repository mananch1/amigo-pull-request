import os
from git import Repo
from ingest.parser import parse_file

def clone_repo(repo_url, clone_dir="data/repos/sample_repo", base_commit=None):
    if not os.path.exists(clone_dir):
        repo = Repo.clone_from(repo_url, clone_dir)
    else:
        repo = Repo(clone_dir)
        if repo.remotes.origin.url != repo_url:
            repo.remotes.origin.set_url(repo_url)
        repo.remotes.origin.fetch()
        
    if base_commit:
        repo.git.reset('--hard')
        repo.git.clean('-fd')
        repo.git.checkout(base_commit)
        
    return clone_dir


def get_python_files(repo_path):
    py_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files


from ingest.embedder import get_embedding
from ingest.store import VectorStore

def run_ingestion(repo_path, max_files=5):
    files = get_python_files(repo_path)
    store = VectorStore()

    for f in files[:max_files]:
        try:
            parsed = parse_file(f)
            chunks = parsed["chunks"]
            imports = parsed["imports"]
            print(f"\nProcessing File: {f}")
            
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
        except Exception as e:
            print(f"Error parsing {f}: {e}")

    print(f"\nIngestion complete! Total vectors stored: {store.index.ntotal}")
    store.save()
    print("Saved Vector DB to data/faiss_index.bin")
    return store.index.ntotal

if __name__ == "__main__":
    repo_path = clone_repo("https://github.com/fastapi/fastapi")
    run_ingestion(repo_path)

