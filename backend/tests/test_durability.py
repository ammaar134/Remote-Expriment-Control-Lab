import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from lab.orchestrator import Orchestrator
from lab.store import Store

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="Real PostgreSQL required")


@pytest.mark.parametrize("gap", [False, True])
def test_ack_observes_committed_transaction_and_rollback_never_acknowledges(gap):
    async def check():
        dsn = os.environ["DATABASE_URL"]
        schema = "durability_" + uuid4().hex
        store = Store(dsn)
        store.connection = await psycopg.AsyncConnection.connect(dsn, autocommit=True, row_factory=dict_row)
        observer = await psycopg.AsyncConnection.connect(dsn, autocommit=True, row_factory=dict_row)
        run, recipe = str(uuid4()), str(uuid4())
        calls = []
        try:
            await store.connection.execute(
                psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
            )
            for connection in (store.connection, observer):
                await connection.execute(
                    psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema))
                )
            await store.connection.execute(Path("migrations/001_initial.sql").read_text())
            await store.execute(
                "INSERT INTO recipe_versions(id,name,content) VALUES (%s,'Test','{}')", (recipe,)
            )
            await store.execute(
                "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot) VALUES (%s,'sim-01','boot',%s,%s)",
                (run, recipe, Jsonb({"filter": {"alpha": 0.2}})),
            )
            controller = Orchestrator(store)
            controller.link.boot_id = "boot"
            reader = asyncio.StreamReader()
            controller.link.telemetry_reader = reader
            samples = [
                {
                    "seq": i,
                    "logical_s": (i + 1) / 50,
                    "setpoint": 0.5,
                    "response": 0.1 * i,
                    "reference": 0.2,
                    "source_utc": "2026-01-01T00:00:00Z",
                    "device_elapsed_s": 1.0,
                }
                for i in ([0, 2] if gap else [0, 1])
            ]
            frame = {
                "v": 1,
                "type": "samples",
                "instrument_id": "sim-01",
                "boot_id": "boot",
                "run_id": run,
                "samples": samples,
            }
            reader.feed_data((json.dumps(frame) + "\n").encode() * (1 if gap else 2))

            async def ack(kind, **fields):
                assert kind == "ack"
                # A separate connection cannot see uncommitted rows.
                cursor = await observer.execute("SELECT persisted_seq FROM runs WHERE id=%s", (run,))
                row = await cursor.fetchone()
                assert row["persisted_seq"] == fields["persisted_seq"] == 1
                cursor = await observer.execute("SELECT count(*) AS n FROM samples WHERE run_id=%s", (run,))
                assert (await cursor.fetchone())["n"] == 2
                calls.append(fields)
                if len(calls) == 2:
                    raise asyncio.CancelledError
                return {"ok": True}

            controller.link.call = ack
            with pytest.raises(ValueError if gap else asyncio.CancelledError):
                await controller.ingest()
            if gap:
                assert not calls
                assert (await store.rows("SELECT count(*) AS n FROM samples"))[0]["n"] == 0
                assert (await store.rows("SELECT persisted_seq FROM runs"))[0]["persisted_seq"] == -1
            else:
                assert len(calls) == 2  # Resend is harmless and acknowledged again.
                assert (await store.rows("SELECT filtered FROM samples WHERE seq=1"))[0][
                    "filtered"
                ] == pytest.approx(0.02)
        finally:
            await observer.close()
            await store.connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )
            await store.close()

    asyncio.run(check())
