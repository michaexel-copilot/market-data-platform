# Market data platform (FastAPI + HTMX web app) as a container.
#
# hl-client (order placement) is intentionally NOT installed: it is a private
# path dependency. Without it the order endpoint answers with a clear error.

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    UV_COMPILE_BYTECODE=1 \
    HL_PAIRS_CSV=/app/seed/hl-main-pairs.csv

WORKDIR /app

# Dependencies first (cached layer). hl-client is excluded from the export.
COPY pyproject.toml uv.lock .python-version ./
RUN uv export --frozen --no-dev --no-hashes --no-emit-project --no-emit-package hl-client \
        -o /tmp/requirements.txt \
 && uv pip install --system --no-cache -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

COPY . .

# coinMarketCapKey.py is a git-ignored secret module; this shim reads the key
# from the environment instead (CMC_API_KEY).
RUN printf 'import os\ncmc_key = os.environ.get("CMC_API_KEY", "")\n' > coinMarketCapKey.py \
 && useradd --uid 1000 --create-home app \
 && mkdir -p data cache png \
 && chown -R app:app /app

USER app
VOLUME ["/app/data", "/app/cache", "/app/png"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/lists', timeout=4)"

# One process: the app keeps state in SQLite and on disk.
CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
