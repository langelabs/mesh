"""Mesh service endpoint routers."""

from fastapi import APIRouter

from .management import management_router
from .relay import relay_router
from .workers import workers_router

mesh_api_router = APIRouter()

mesh_api_router.include_router(management_router)
mesh_api_router.include_router(workers_router, prefix="/v1")
mesh_api_router.include_router(relay_router)


__all__ = ["mesh_api_router"]
