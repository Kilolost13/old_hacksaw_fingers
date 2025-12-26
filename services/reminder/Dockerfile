FROM python:3.11-slim
RUN mkdir -p /app
WORKDIR /app
COPY microservice/reminder/pyproject.toml .
RUN pip install --upgrade pip && pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-root
# Copy whole repository so the microservice package structure is present
COPY . .
RUN mkdir -p /data
RUN apt-get update && rm -rf /var/lib/apt/lists/*
# Ensure Python can import the package from /app
ENV PYTHONPATH=/app
# Run via package import path
CMD ["uvicorn", "microservice.reminder.main:app", "--host", "0.0.0.0", "--port", "9002"]
