from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agents, auth, dashboard, documents, models, projects, requirements, users

v1_router = APIRouter()
v1_router.include_router(auth.router)
v1_router.include_router(dashboard.router)
v1_router.include_router(users.router)
v1_router.include_router(models.router)
v1_router.include_router(projects.router)
v1_router.include_router(requirements.router)
v1_router.include_router(requirements.file_router)
v1_router.include_router(documents.router)
v1_router.include_router(agents.router)
