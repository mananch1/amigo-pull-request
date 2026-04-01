import os
from git import Repo
from ingest.parser import parse_file

REPO_URL = "https://github.com/your/repo.git"
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


if __name__ == "__main__":
    repo_path = clone_repo()
    files = get_python_files(repo_path)

    for f in files[:3]:  # test first 3 files
        chunks = parse_file(f)
        print(f"\nFile: {f}")
        for c in chunks:
            print(c["name"])
