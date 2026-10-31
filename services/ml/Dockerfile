FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/src

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Run FastAPI with Uvicorn (Lifespan handles starting the background worker automatically)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]