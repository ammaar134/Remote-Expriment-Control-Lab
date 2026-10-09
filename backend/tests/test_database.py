import asyncio
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="Real PostgreSQL required")


def test_postgres_immutability_duplicates_and_single_owner():
    async def check():
        connection = await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"])
        try:
            async with connection.cursor() as cur:
                schema = "test_" + uuid4().hex
                await cur.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
                await cur.execute(
                    psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema))
                )
                await cur.execute(Path("migrations/001_initial.sql").read_text())
                recipe, run = uuid4(), uuid4()
                await cur.execute(
                    "INSERT INTO recipe_versions(id,name,content) VALUES (%s,'Test','{}')", (recipe,)
                )
                await cur.execute(
                    "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot) "
                    "VALUES (%s,'sim','boot',%s,%s)",
                    (run, recipe, Jsonb({"seed": 7})),
                )
                with pytest.raises(psycopg.errors.UniqueViolation):
                    async with connection.transaction():
                        await cur.execute(
                            "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot) "
                            "VALUES (%s,'sim','boot',%s,'{}')",
                            (uuid4(), recipe),
                        )
                with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
                    async with connection.transaction():
                        await cur.execute("UPDATE runs SET snapshot='{}' WHERE id=%s", (run,))
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    async with connection.transaction():
                        await cur.execute("UPDATE recipe_versions SET content='{}' WHERE id=%s", (recipe,))
                values = (
                    run,
                    "boot",
                    0,
                    0.02,
                    0.5,
                    0.1,
                    0.08,
                    0.1,
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    1.0,
                )
                await cur.execute("INSERT INTO samples VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", values)
                with pytest.raises(psycopg.errors.UniqueViolation):
                    async with connection.transaction():
                        await cur.execute(
                            "INSERT INTO samples VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", values
                        )
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    async with connection.transaction():
                        await cur.execute("UPDATE samples SET response=99 WHERE run_id=%s", (run,))
        finally:
            await connection.rollback()  # All test schema/data removed by rollback, no live history touched.
            await connection.close()

    asyncio.run(check())
