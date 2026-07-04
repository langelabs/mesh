# Mesh Service

FastAPI standalone relay service for public mesh hosts.

Workers connect to `/v1/workers/entrypoint`. If `MESH_WORKER_SECRET` is set,
workers must send `Authorization: Bearer <secret>`.

Requests to `{key}.mesh.lange-labs.com/{path}` are forwarded directly to the
connected in-process relay worker registered for `{key}`.
