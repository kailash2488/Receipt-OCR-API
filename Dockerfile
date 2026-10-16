# Use official lightweight Python image
FROM python:3.10-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies including Tesseract OCR and libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . /app/

# Expose port
EXPOSE 8000

# Default run command
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_receipts && python manage.py runserver 0.0.0.0:8000"]

