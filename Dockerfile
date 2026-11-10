# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Установка необходимых системных утилит сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копирование спецификаций зависимостей
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Сборка и установка пакета
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ==========================================================
# Финальный легковесный образ исполнения
# ==========================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Создание непривилегированного пользователя для безопасности (Least Privilege)
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Копирование установленных библиотек из builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копирование исходных файлов приложения
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml README.md ./

# Переключение на непривилегированного пользователя
USER appuser

# Настройка переменных окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Healthcheck для мониторинга доступности сервиса
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/gestures')" || exit 1

# Запуск FastAPI приложения через оптимизированный Uvicorn
CMD ["uvicorn", "project_omilia.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
