# Este Dockerfile é construído com o CONTEXTO NA RAIZ do repositório (é assim que
# Easypanel e Railway buildam ao apontar para backend/Dockerfile). Por isso os
# COPY usam caminhos a partir da raiz (backend/...). Para buildar localmente:
#   docker build -f backend/Dockerfile -t fitcoach-backend .
FROM python:3.11-slim

# Bibliotecas de sistema do WeasyPrint (Pango/Cairo/gdk-pixbuf) — o pacote
# Python é só um wrapper sobre elas; sem estas libs o `import weasyprint` falha
# em runtime. shared-mime-info e as fontes são necessárias para renderizar PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas do Docker.
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ .

# Usuário não-root (defesa em profundidade — o container não roda como root).
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Easypanel/Railway injetam $PORT; localmente cai para 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
