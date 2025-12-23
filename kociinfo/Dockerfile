# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY kodi_info.py .
COPY favicon.ico .
COPY background.jpg .
COPY kodi.png .
COPY movies.png .
COPY tv.png .
COPY music.png .
COPY new.png .
COPY refresh.png .

# Ensure all image files are readable
RUN chmod 644 *.png *.jpg *.ico

# Create directory for output files
RUN mkdir -p /app/output/artwork

# Expose port for web server
EXPOSE 5005

# Set environment variables
ENV PYTHONUNBUFFERED=1
# KODI_HOST, KODI_USERNAME, KODI_PASSWORD, and WEB_PORT will be set by docker-compose

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5005/health || exit 1

# Default command - start web server
CMD ["python", "kodi_info.py", "--web-server", "--web-port", "5005"]
