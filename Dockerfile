# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim-bookworm AS python-dependencies
ARG TORCH_VERSION=2.5.1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}" \
    && pip install -r /tmp/requirements-runtime.txt

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/home/parsrag \
    HF_HOME=/home/parsrag/.cache/huggingface

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fas \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 parsrag \
    && useradd --system --uid 10001 --gid parsrag --create-home parsrag

ENV HF_HUB_DISABLE_XET=1

COPY --from=python-dependencies /opt/venv /opt/venv
WORKDIR /app
COPY --chown=parsrag:parsrag backend ./backend
COPY --from=frontend-build --chown=parsrag:parsrag /build/frontend/dist ./frontend/dist
RUN mkdir -p "$HF_HOME" /home/parsrag/.cache/llama_index /var/lib/parsrag \
    && chown -R parsrag:parsrag /home/parsrag /var/lib/parsrag

USER parsrag
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=90s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
