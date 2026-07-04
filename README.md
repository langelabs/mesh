# Mesh Service

[![CI](https://github.com/langelabs/mesh/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/langelabs/mesh/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/langelabs/mesh/branch/main/graph/badge.svg)](https://codecov.io/gh/langelabs/mesh)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0)

FastAPI standalone relay service for public mesh hosts.

Workers connect to `/v1/workers/entrypoint`. If `MESH_WORKER_SECRET` is set,
workers must send `Authorization: Bearer <secret>`.

Requests to `{key}.mesh.lange-labs.com/{path}` are forwarded directly to the
connected in-process relay worker registered for `{key}`.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## Installation

Install the project and development dependencies:

```bash
uv sync --dev
```

## Running with Docker

Run the published container image:

```bash
docker run --rm -p 8084:8084 ghcr.io/langelabs/mesh:latest
```

Configure the mesh base domain and optional worker secret with environment
variables:

```bash
docker run --rm \
  -p 8084:8084 \
  -e MESH_BASE_DOMAIN=mesh.lange-labs.com \
  -e MESH_WORKER_SECRET=<secret> \
  ghcr.io/langelabs/mesh:latest
```

## Running with Python

Start the FastAPI app with Uvicorn:

```bash
uv run uvicorn mesh_service.main:app --host 0.0.0.0 --port 8000
```

The service reads the following environment variables:

- `MESH_BASE_DOMAIN`: base domain used to extract relay worker names.
- `MESH_WORKER_SECRET`: optional bearer token required by worker websocket clients.

## Usage

Workers connect to the versioned websocket entrypoint:

```text
/v1/workers/entrypoint
```

When `MESH_WORKER_SECRET` is configured, workers must send:

```text
Authorization: Bearer <secret>
```

Relay requests are routed by host name. A request to
`{key}.<MESH_BASE_DOMAIN>/<path>` is forwarded to the connected worker
registered for `{key}`.

## Checks

Lint the source package:

```bash
uv run ruff check src
```

Run unit tests with coverage:

```bash
uv run pytest -q --cov=src/mesh_service --cov-report=term-missing --cov-report=xml
```

## License

This project is licensed under the
[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0).
See [LICENSE](LICENSE) for the full license text.
