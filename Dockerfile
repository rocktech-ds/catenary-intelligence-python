FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ git \
    libgl1-mesa-dri libglib2.0-0 \
    libsm6 libxext6 libxrender-dev \
    libgomp1 wget tesseract-ocr \
    ghostscript python3-tk \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8003

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
