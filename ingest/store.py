import faiss
import numpy as np

class VectorStore:
    def __init__(self, dim=768):
        self.index = faiss.IndexFlatL2(dim)
        self.metadata = []

    def add(self, embedding, meta):
        self.index.add(np.array([embedding]).astype("float32"))
        self.metadata.append(meta)

    def search(self, embedding, k=5):
        if self.index.ntotal == 0:
            return []
        D, I = self.index.search(np.array([embedding]).astype("float32"), k)
        return [self.metadata[i] for i in I[0] if i < len(self.metadata)]

    def save(self, index_path="data/faiss_index.bin", meta_path="data/faiss_metadata.json"):
        import os
        import json
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        faiss.write_index(self.index, index_path)
        with open(meta_path, "w") as f:
            json.dump(self.metadata, f)

    def load(self, index_path="data/faiss_index.bin", meta_path="data/faiss_metadata.json"):
        import json
        self.index = faiss.read_index(index_path)
        with open(meta_path, "r") as f:
            self.metadata = json.load(f)
