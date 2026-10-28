FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime libraries needed by scientific Python packages such as
# scikit-learn/scipy. Keeping this layer separate makes dependency rebuilds
# independent from source changes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-service.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r requirements-service.txt

RUN useradd --create-home --uid 10001 preprocessing

COPY --chown=preprocessing:preprocessing src/ ./src/

RUN mkdir -p /tmp/preprocessing \
    && chown -R preprocessing:preprocessing /tmp/preprocessing

USER preprocessing

ENV PREPROCESSING_WORK_ROOT=/tmp/preprocessing

EXPOSE 8001

CMD ["uvicorn", "main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8001"]

