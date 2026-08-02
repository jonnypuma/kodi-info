# Use Python 3.11 slim image
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kodi_info.py kodi_client.py connection_tokens.py library_actions.py operation_store.py webapp.py ./
COPY templates ./templates
COPY static ./static
COPY favicon.ico background.jpg kodi.png movies.png tv.png music.png new.png refresh.png ./

RUN chmod 644 *.py *.png *.jpg *.ico \
    && chmod -R a+rX templates static \
    && mkdir -p /app/output/artwork

EXPOSE 5005

ENV PYTHONUNBUFFERED=1

# Liveness: process up. Prefer /ready in orchestration when Kodi reachability matters.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5005/health || exit 1

CMD ["python", "kodi_info.py", "--web-server", "--web-port", "5005"]
