"""Shared router for worker endpoints."""

from fastapi import APIRouter

workers_router = APIRouter(prefix="/workers", tags=["workers"])
