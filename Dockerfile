FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=7860
ENV FRONTEND_URL=https://example.lovable.app
ENV EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV PERSISTENT_STORAGE_ROOT=/data/nyayasetu
ENV PREFER_LOCAL_APP_DB_ON_SPACE=false
ENV ALLOW_REMOTE_APP_DB_ON_SPACE=true
ENV APP_SQLITE_PATH=db/db.db
ENV ANALYTICS_DB_PATH=analytics/legal_corpus.duckdb
ENV VECTOR_INDEX_PATH=index/legal.index
ENV VECTOR_METADATA_PATH=index/legal_metadata.json
ENV UPLOAD_DIR=uploads
ENV HF_HOME=/data/.huggingface
ENV TRANSFORMERS_CACHE=/data/.huggingface

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
COPY docker/start-space.sh /app/docker/start-space.sh
COPY .env.example /app/.env.example

RUN chmod +x /app/docker/start-space.sh \
    && PERSISTENT_STORAGE_ROOT= \
       APP_SQLITE_PATH=/app/storage/db/nyayasetu.sqlite3 \
       ANALYTICS_DB_PATH=/app/data/analytics/legal_corpus.duckdb \
       VECTOR_INDEX_PATH=/app/data/index/legal.index \
       VECTOR_METADATA_PATH=/app/data/index/legal_metadata.json \
       UPLOAD_DIR=/app/storage/uploads \
       python /app/rag/indexing/build_faiss_index.py --checkpoint-dir /app/data/index/checkpoints/legal_space_build

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app

CMD ["/app/docker/start-space.sh"]
