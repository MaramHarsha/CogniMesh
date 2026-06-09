from __future__ import annotations

from fastapi import APIRouter

from app.api.rest import graph, health, identity, lineage, links, objects, sources, tables, workspaces

router = APIRouter()
router.include_router(health.router)
router.include_router(workspaces.router, prefix="/v1")
router.include_router(sources.router, prefix="/v1")
router.include_router(tables.router, prefix="/v1")
router.include_router(lineage.router, prefix="/v1")
router.include_router(objects.router, prefix="/v1")
router.include_router(links.router, prefix="/v1")
router.include_router(graph.router, prefix="/v1")
router.include_router(identity.router, prefix="/v1")
