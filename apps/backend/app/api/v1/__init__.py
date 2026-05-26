from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agents, auth, dashboard, documents, environments, exploration, global_knowledge, knowledge, models, operation_logs, projects, requirements, users

v1_router = APIRouter()
v1_router.include_router(auth.router)
v1_router.include_router(dashboard.router)
v1_router.include_router(users.router)
v1_router.include_router(models.router)
v1_router.include_router(projects.router)
v1_router.include_router(operation_logs.router)
v1_router.include_router(operation_logs.project_router)
v1_router.include_router(environments.global_router)
v1_router.include_router(environments.router)
v1_router.include_router(exploration.global_router)
v1_router.include_router(exploration.router)
v1_router.include_router(knowledge.router)
v1_router.include_router(global_knowledge.router)
v1_router.include_router(requirements.router)
v1_router.include_router(requirements.file_router)
v1_router.include_router(documents.router)
v1_router.include_router(agents.router)
