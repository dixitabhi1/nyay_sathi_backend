FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=7860
ENV FRONTEND_URL=https://example.lovable.app
ENV EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.no-whisper.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /tmp/backend-requirements.txt \
    && pip install --no-cache-dir accelerate

COPY backend /app/backend
COPY ingestion /app/ingestion
COPY rag /app/rag
COPY data /app/data
COPY storage /app/storage
COPY .env.example /app/.env.example

RUN python /app/rag/indexing/build_faiss_index.py --checkpoint-dir /app/data/index/checkpoints/legal_space_build

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app

CMD ["sh", "-c", "if [ ! -f /app/data/index/legal.index ]; then python /app/rag/indexing/build_faiss_index.py --checkpoint-dir /app/data/index/checkpoints/legal_space_runtime; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
