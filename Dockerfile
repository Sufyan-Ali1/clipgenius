FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.py .

# Create storage directories
RUN mkdir -p storage/uploads storage/outputs storage/temp credentials

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "run.py", "--host", "0.0.0.0"]
