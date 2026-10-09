import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class Store:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.lock = asyncio.Lock()
        self.connection: psycopg.AsyncConnection[Any] | None = None

    async def open(self) -> None:
        self.connection = await psycopg.AsyncConnection.connect(
            self.dsn,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=3,
            options="-c statement_timeout=3000",
        )
        async with self.transaction() as cur:
            await cur.execute("SELECT pg_try_advisory_lock(134001) AS acquired")
            if not (await cur.fetchone())["acquired"]:
                raise RuntimeError("Another orchestrator owns this database")
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            for path in sorted(Path("migrations").glob("*.sql")):
                await cur.execute("SELECT version FROM schema_migrations WHERE version=%s", (path.name,))
                if await cur.fetchone():
                    continue
                await cur.execute(path.read_text())
                await cur.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (path.name,))

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()

    @asynccontextmanager
    async def transaction(self):
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            async with self.connection.transaction():
                async with self.connection.cursor() as cursor:
                    yield cursor

    async def rows(self, query: str, params: tuple = ()) -> list[dict]:
        async with self.transaction() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()

    async def execute(self, query: str, params: tuple = ()) -> None:
        async with self.transaction() as cur:
            await cur.execute(query, params)

    async def event(self, run_id: str | None, kind: str, detail: dict) -> None:
        await self.execute(
            "INSERT INTO events(run_id,kind,detail) VALUES (%s,%s,%s)",
            (run_id, kind, Jsonb(detail)),
        )
