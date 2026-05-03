FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (backend 폴더)
COPY . .

# Create storage directory (actual data will be mounted via Railway Volume)
RUN mkdir -p /app/storage/data /app/storage/cache /app/storage/prometheus /app/storage/cookies

# Expose port (Railway will assign dynamically)
EXPOSE 8000

# Run the application (production mode - no --reload)
# Use PORT environment variable from Railway, fallback to 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
