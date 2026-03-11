FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY training/requirements.txt /tmp/training-requirements.txt
RUN pip install --no-cache-dir -r /tmp/training-requirements.txt

COPY training /workspace/training
COPY data /workspace/data

CMD ["python", "training/scripts/prepare_dataset.py"]

