import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import os

class Retriever:
    def __init__(self, index_dir: str):
        print(f"Loading Retriever Index from {index_dir}...")
        self.index = faiss.read_index(os.path.join(index_dir, "index.faiss"))
        with open(os.path.join(index_dir, "index_meta.json"), 'r', encoding='utf-8') as f:
            self.names = json.load(f)
        # Using the same lightweight model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def search(self, query: str, k: int = 10) -> list:
        # Embed the search query
        emb = self.model.encode([query], normalize_embeddings=True)
        
        # Search the index
        distances, indices = self.index.search(emb.astype(np.float32), k)
        
        results = []
        for idx in indices[0]:
            if idx != -1: # FAISS returns -1 if fewer results exist
                results.append(self.names[idx])
        return results
