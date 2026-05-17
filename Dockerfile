FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and pre-built data (FAISS index + catalog)
COPY data/ ./data/
COPY app/ ./app/

# Copy HTML pages served at / and /app
COPY landing.html ./landing.html
COPY chat_test.html ./chat_test.html

# Prevent memory fragmentation and limit threads for Render's 512MB tier
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1

# Pre-download the embedding model so it doesn't spike memory at startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Expose FastAPI port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
