FROM python:3.11-slim

# Install system dependencies for USB handling
RUN apt-get update && apt-get install -y \
    usbutils \
    udev \
    cryptsetup \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY microservice/usb_transfer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code from repository root so package structure (microservice/) is present
COPY . .

# Create config directory
RUN mkdir -p /etc/kilo

# Expose port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1

# Ensure Python can import the package from /app
ENV PYTHONPATH=/app

# Run the application via uvicorn using the package import path so relative imports work
CMD ["uvicorn", "microservice.usb_transfer.main:app", "--host", "0.0.0.0", "--port", "8006"]