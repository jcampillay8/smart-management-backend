FROM python:3.12-slim

# 1. Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 2. Instalación de dependencias del sistema
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-icu0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 3. Traer uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 4. Preparar dependencias
COPY pyproject.toml ./

# 5. Instalar con uv (las versiones conflictivas ya están fijadas en pyproject.toml)
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install -r requirements.txt --system

# 6. Copiar el resto del código
COPY . .

# 7. Comando de inicio
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]