# Multi-stage production image: React UI + FastAPI on one port (Render-ready).
FROM node:20-alpine AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# System deps for scientific wheels / reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=webbuild /web/dist /app/static

ENV STATIC_DIR=/app/static
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Render injects $PORT; generate gallery then serve API+SPA.
CMD ["sh", "-c", "python -m samples.make_samples && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
