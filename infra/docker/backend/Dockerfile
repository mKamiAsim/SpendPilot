FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /usr/local/bin/uv

# English and Arabic Tesseract data are Apache-2.0 (ADR 0004). Keep the Debian copyright files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ghostscript \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/* \
    && test -s /usr/share/doc/tesseract-ocr/copyright \
    && test -s /usr/share/doc/tesseract-ocr-eng/copyright \
    && test -s /usr/share/doc/tesseract-ocr-ara/copyright \
    && tesseract --list-langs | grep -qx eng \
    && tesseract --list-langs | grep -qx ara

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin spendpilot

WORKDIR /srv
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable --extra agents --extra documents \
    && mkdir -p /var/lib/spendpilot/files \
    && chown -R spendpilot:spendpilot /srv /var/lib/spendpilot

USER spendpilot
ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SPENDPILOT_PROCESS=api

EXPOSE 8000
CMD ["python", "-m", "app.entrypoint"]
