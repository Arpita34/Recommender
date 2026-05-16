import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

def build_index():
    catalog_path = 'data/catalog.json'
    if not os.path.exists(catalog_path):
        print(f"Error: {catalog_path} not found. Run scraper first.")
        return

    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    if not catalog:
        print("Catalog is empty. Nothing to index.")
        return

    # Load the embedding model (runs locally)
    print("Loading embedding model 'all-MiniLM-L6-v2'...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    texts, names = [], []
    for name, item in catalog.items():
        # Combine all relevant fields into one searchable string
        text = f"{name}. {item.get('description', '')}. "
        text += f"Type: {item.get('test_type', 'Unknown')}. "
        text += f"Competencies: {', '.join(item.get('competencies', []))}. "
        text += f"Job Levels: {', '.join(item.get('job_levels', []))}"
        texts.append(text)
        names.append(name)

    print(f'Embedding {len(texts)} assessments...')
    # normalize_embeddings=True is required for Inner Product to act as Cosine Similarity
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    # Build flat cosine index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension) 
    index.add(embeddings.astype(np.float32))

    # Ensure index directory exists
    os.makedirs('data/faiss_index', exist_ok=True)

    # Save index and metadata
    faiss.write_index(index, 'data/faiss_index/index.faiss')
    with open('data/faiss_index/index_meta.json', 'w', encoding='utf-8') as f:
        json.dump(names, f)
        
    print('Index built successfully and saved to data/faiss_index/.')

if __name__ == '__main__':
    build_index()
