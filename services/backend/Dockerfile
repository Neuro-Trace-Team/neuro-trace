FROM python:3.12-slim

WORKDIR /app

# curl is used by the Compose health check.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

