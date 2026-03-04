FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# ffmpeg is CRITICAL for video processing
# build-essential for compiling python packages if needed
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command is overridden by docker-compose, but good default
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
