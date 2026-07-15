# image: ghcr.io/langelabs/mesh:latest

FROM python:3.13-slim@sha256:dc1546eefcbe8caaa1f004f16ab76b204b5e1dbd58ff81b899f21cd40541232f AS builder

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.11.14

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.13-slim@sha256:dc1546eefcbe8caaa1f004f16ab76b204b5e1dbd58ff81b899f21cd40541232f AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

USER appuser

EXPOSE 8084

CMD ["uvicorn", "mesh_service.main:app", "--host", "0.0.0.0", "--port", "8084", "--ws", "websockets-sansio"]
