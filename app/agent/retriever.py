import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import os
from rank_bm25 import BM25Okapi

class Retriever:
    def __init__(self, index_dir: str):
        print(f"Loading Retriever Index from {index_dir}...")
        self.index = faiss.read_index(os.path.join(index_dir, "index.faiss"))
        with open(os.path.join(index_dir, "index_meta.json"), 'r', encoding='utf-8') as f:
            self.names = json.load(f)
            
        corpus_path = os.path.join(index_dir, "corpus.json")
        if os.path.exists(corpus_path):
            with open(corpus_path, 'r', encoding='utf-8') as f:
                corpus = json.load(f)
            tokenized_corpus = [doc.lower().split(" ") for doc in corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None
            
        # Using the same lightweight model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def search(self, query: str, k: int = 10) -> list:
        # Embed the search query
        emb = self.model.encode([query], normalize_embeddings=True)
        
        # Search the FAISS index (Dense)
        distances, indices = self.index.search(emb.astype(np.float32), k * 2)
        dense_indices = [idx for idx in indices[0] if idx != -1]
        
        if not self.bm25:
            return [self.names[idx] for idx in dense_indices[:k]]
            
        # BM25 Lexical search
        tokenized_query = query.lower().split(" ")
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_indices = np.argsort(bm25_scores)[::-1][:k * 2]
        
        # Reciprocal Rank Fusion (RRF)
        scores = {}
        for rank, idx in enumerate(dense_indices):
            scores[idx] = scores.get(idx, 0) + 1.0 / (60 + rank + 1)
            
        for rank, idx in enumerate(bm25_indices):
            # Convert np.int64 to int so it can be hashed the same way as dense_indices (which are python ints from FAISS output)
            idx_int = int(idx)
            scores[idx_int] = scores.get(idx_int, 0) + 1.0 / (60 + rank + 1)
            
        # Sort by RRF score
        final_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        return [self.names[idx] for idx in final_indices[:k]]
