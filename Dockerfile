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
# Reuse committed detectors/empirical_baselines.json (do not retrain at build).
ENV FORCE_BASELINE_FIT=0

# Bake the gallery/snapshots/bench into the image so runtime can bind $PORT
# immediately. Render kills deploys that don't open a port within ~5 minutes;
# make_samples alone exceeds that window if run in CMD.
RUN python -m samples.make_samples

EXPOSE 8000

# Render injects $PORT — bind it right away (no pre-start work).
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
