FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    GARTH_HOME=/data/garth

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App code.
COPY app ./app

# Token-cache dir (mounted as a volume in compose).
RUN mkdir -p /data/garth

# Bake in the prebuilt companion binaries from the latest GitHub Release, so the
# "Download for Linux/Windows" buttons work out of the box after `compose up`.
# Fetched from the canonical repo by default (the binaries are config-agnostic —
# each instance's URL+token is injected at download time), overridable for forks.
# Missing (no release yet) is non-fatal: the endpoint just returns 503 until one
# exists. To refresh after a new companion release: `docker compose build --no-cache backend`.
ARG COMPANION_REPO=danthi123/pulsevault
RUN mkdir -p /companion-dist && cd /companion-dist && \
    base="https://github.com/${COMPANION_REPO}/releases/latest/download" && \
    ( python -c "import urllib.request; urllib.request.urlretrieve('${base}/pulsevault-companion-linux','pulsevault-companion')" \
        && chmod +x pulsevault-companion || echo 'note: linux companion binary not published yet' ) && \
    ( python -c "import urllib.request; urllib.request.urlretrieve('${base}/pulsevault-companion-windows.exe','pulsevault-companion.exe')" \
        || echo 'note: windows companion binary not published yet' )

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
