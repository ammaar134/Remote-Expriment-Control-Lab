"""Append-only recipe versions; saves retry with the same version/request ID."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg.types.json import Jsonb

from .models import RecipeSaveRequest
from .store import Store

RECIPE_FIELDS = (
    "v.id,v.name,v.content AS recipe,v.created_at,r.family_id,r.revision,r.parent_id,r.alpha "
    "FROM recipe_versions v JOIN recipe_revisions r ON r.version_id=v.id "
)


async def insert_recipe(cur, version_id, name, content, alpha, parent_id=None):
    family_id, revision = version_id, 1
    if parent_id:
        await cur.execute("SELECT family_id,revision FROM recipe_revisions WHERE version_id=%s", (parent_id,))
        parent = await cur.fetchone()
        if not parent:
            raise HTTPException(404, "Recipe version not found")
        await cur.execute("SELECT version_id FROM recipe_revisions WHERE parent_id=%s", (parent_id,))
        if await cur.fetchone():
            raise HTTPException(
                409, "A newer version exists. Load it before saving, or save as a new recipe."
            )
        family_id, revision = parent["family_id"], parent["revision"] + 1
    await cur.execute(
        "INSERT INTO recipe_versions(id,name,content) VALUES (%s,%s,%s)",
        (version_id, name, Jsonb(content)),
    )
    await cur.execute(
        "INSERT INTO recipe_revisions(version_id,family_id,revision,parent_id,alpha) VALUES (%s,%s,%s,%s,%s)",
        (version_id, family_id, revision, parent_id, alpha),
    )
    return {"id": str(version_id), "family_id": str(family_id), "revision": revision}


def recipe_routes(store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/recipes")

    @router.get("")
    async def recipes(offset: int = Query(0, ge=0, le=10000), limit: int = Query(50, ge=1, le=100)):
        return await store.rows(
            "SELECT " + RECIPE_FIELDS + "ORDER BY v.created_at DESC,v.id DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )

    @router.get("/{version_id}")
    async def recipe(version_id: UUID):
        rows = await store.rows("SELECT " + RECIPE_FIELDS + "WHERE v.id=%s", (version_id,))
        if not rows:
            raise HTTPException(404, "Recipe version not found")
        return rows[0]

    @router.post("", status_code=201)
    async def save(request: RecipeSaveRequest):
        content = request.recipe.model_dump(mode="json")
        async with store.transaction() as cur:
            await cur.execute("SELECT " + RECIPE_FIELDS + "WHERE v.id=%s", (request.request_id,))
            known = await cur.fetchone()
            if known:
                if (known["name"], known["recipe"], known["alpha"], known["parent_id"]) != (
                    request.name,
                    content,
                    request.alpha,
                    request.parent_id,
                ):
                    raise HTTPException(409, "Save request ID conflicts with an earlier recipe")
                return known
            await insert_recipe(
                cur, request.request_id, request.name, content, request.alpha, request.parent_id
            )
            await cur.execute("SELECT " + RECIPE_FIELDS + "WHERE v.id=%s", (request.request_id,))
            return await cur.fetchone()

    return router
