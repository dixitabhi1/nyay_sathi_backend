FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=7860
ENV FRONTEND_URL=https://example.lovable.app

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
COPY data /app/data
COPY storage /app/storage
COPY .env.example /app/.env.example

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
