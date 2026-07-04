from pydantic import BaseModel

from .__router import management_router


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str


@management_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return a lightweight service health payload.

    :returns: Health status payload.
    """
    return HealthResponse(status="ok")
