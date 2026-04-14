FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencias del sistema (Incluye librerías para Pillow/ReportLab si generas PDFs de ventas)
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

# Instalación de UV y dependencias
COPY pyproject.toml ./
RUN curl -Ls https://astral.sh/uv/install.sh | bash && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    uv pip compile pyproject.toml -o requirements.txt && \
    sed -i 's/fastapi-limiter>=.*/fastapi-limiter==0.1.6/' requirements.txt && \
    uv pip install -r requirements.txt --system

# Fix de compatibilidad Pydantic v2
RUN pip install --upgrade pip setuptools wheel && \
    pip uninstall -y fastapi-mail fastapi-limiter || true && \
    pip install "fastapi-mail==1.5.0" "fastapi-limiter==0.1.6" "pydantic>=2.7.0" "pydantic-settings>=2.0.3"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]