FROM python:3.11-slim

WORKDIR /app

COPY collector/pyproject.toml /app/collector/pyproject.toml
RUN pip install --no-cache-dir -e /app/collector

COPY collector /app/collector
COPY scripts /app/scripts

WORKDIR /app/collector
CMD ["python", "-m", "collector.main"]
