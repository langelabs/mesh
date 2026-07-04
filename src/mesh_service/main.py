"""FastAPI app for the standalone public mesh relay service."""

from fastapi import FastAPI

from .endpoints import mesh_api_router

app = FastAPI(title="Lange Labs Mesh Router")
app.include_router(mesh_api_router)
