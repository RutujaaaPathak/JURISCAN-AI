# JURISCAN-AI backend image.
#
# Build context is the repository root (see docker-compose.yml) so this file can
# stay in docker/ while copying from backend/. Python version matches the
# version the backend is developed and tested against (3.13).
FROM python:3.13-slim

# opencv-python (OCR page pre-processing) needs libGL/libglib at runtime on
# slim images; every other dependency ships as a self-contained wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer first so source changes do not invalidate the pip cache.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# The app resolves BASE_DIR as the parent of the backend package, so inside
# the container uploads live under /data and any local models under /models.
# Both are mounted as volumes; pre-create them with the right owner so a
# fresh named volume inherits non-root permissions.
RUN useradd --create-home --uid 1000 juriscan \
    && mkdir -p /data /models \
    && chown -R juriscan:juriscan /app /data /models

USER juriscan

EXPOSE 8000

# Run migrations at startup, then serve. Exactly ONE uvicorn worker is
# intentional and required: the realtime hubs and the auth rate limiter keep
# per-connection state in process memory. Scaling out means multiple
# replicas behind a load balancer that routes by sticky session (WebSocket)
# plus a shared rate-limit store.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"]
