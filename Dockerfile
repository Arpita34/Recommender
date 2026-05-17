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

# Expose FastAPI port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
