FROM python:3.11-slim

WORKDIR /app

COPY api/pyproject.toml /app/api/pyproject.toml
RUN pip install --no-cache-dir -e /app/api

COPY api /app/api
COPY scripts /app/scripts

WORKDIR /app/api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
