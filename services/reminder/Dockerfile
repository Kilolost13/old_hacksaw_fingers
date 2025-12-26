FROM python:3.11-slim
RUN mkdir -p /app
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-root
COPY . .
RUN mkdir -p /data
RUN apt-get update && rm -rf /var/lib/apt/lists/*
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9002"]
