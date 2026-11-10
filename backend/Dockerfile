FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema para psycopg2/geoalchemy2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini .
# Modelos pré-treinados (se existirem). O .gitignore exclui os artefatos,
# então a ausência é esperada e o serving cai em fallback.
COPY models ./models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
