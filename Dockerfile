# Digest зафиксирован: python:3.11-slim на 2026-11-08.
# Обновлять осознанно: docker buildx imagetools inspect python:3.11-slim
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt
COPY . .
RUN mkdir -p /app/data
CMD ["python", "-m", "app.main"]
