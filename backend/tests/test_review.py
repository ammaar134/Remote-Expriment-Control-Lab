"""Real PostgreSQL: migration, immutable recipe lineage, review/export/replay."""

import asyncio
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from lab.recipes import recipe_routes
from lab.review import chart_points, csv_text, review_routes
from lab.store import Store


@asynccontextmanager
async def database():
    store = Store(os.environ["DATABASE_URL"])
    schema = "review_" + uuid4().hex
    store.connection = await psycopg.AsyncConnection.connect(store.dsn, autocommit=True, row_factory=dict_row)
    try:
        await store.connection.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )
        await store.connection.execute(
            psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema))
        )
        await store.connection.execute(Path("migrations/001_initial.sql").read_text())
        yield store
    finally:
        await store.connection.execute(
            psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
        )
        await store.close()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="Real PostgreSQL required")
def test_upgrade_recipe_conflicts_exports_and_replay_without_an_instrument():
    async def check():
        async with database() as store:
            recipe = {"sample_rate_hz": 50, "seed": 7, "steps": [{"setpoint": 0.5, "duration_ms": 1000}]}
            old_recipe, run_id = uuid4(), uuid4()
            snapshot = {
                "name": '=SUM("x,y")\nSynthetic',
                "recipe": recipe,
                "filter": {"alpha": 0.2, "version": "ema-1"},
            }
            await store.execute(
                "INSERT INTO recipe_versions(id,name,content) VALUES (%s,%s,%s)",
                (old_recipe, snapshot["name"], Jsonb(recipe)),
            )
            await store.execute(
                "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot,execution,recording,"
                "persisted_seq,final_seq,created_at) "
                "VALUES (%s,'sim-01','test-boot',%s,%s,'COMPLETED','partial',1,3,'2026-01-01T00:00:00Z')",
                (run_id, old_recipe, Jsonb(snapshot)),
            )
            # Apply the upgrade with real legacy history, not merely an empty schema.
            await store.connection.execute(Path("migrations/002_recipe_revisions.sql").read_text())
            assert (await store.rows("SELECT snapshot FROM runs WHERE id=%s", (run_id,)))[0][
                "snapshot"
            ] == snapshot
            app = FastAPI()
            app.include_router(recipe_routes(store))
            app.include_router(review_routes(store))
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://testserver"
            ) as client:
                versions = (await client.get("/api/recipes")).json()
                assert versions[0]["alpha"] == 0.2
                assert versions[0]["revision"] == 1
                saved = {
                    "request_id": str(uuid4()),
                    "parent_id": str(old_recipe),
                    "name": "Edited",
                    "recipe": recipe,
                    "alpha": 0.3,
                }
                first, duplicate = await asyncio.gather(
                    client.post("/api/recipes", json=saved), client.post("/api/recipes", json=saved)
                )
                assert first.status_code == duplicate.status_code == 201
                assert first.json() == duplicate.json()
                assert first.json()["revision"] == 2
                assert first.json()["family_id"] == str(old_recipe)
                conflict = await client.post("/api/recipes", json={**saved, "alpha": 0.4})
                assert conflict.status_code == 409
                stale = await client.post("/api/recipes", json={**saved, "request_id": str(uuid4())})
                assert stale.status_code == 409
                assert len((await client.get("/api/recipes")).json()) == 2
                assert (await client.get("/api/recipes/" + str(old_recipe))).json()["alpha"] == 0.2
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    await store.execute(
                        "UPDATE recipe_revisions SET alpha=0.6 WHERE version_id=%s", (old_recipe,)
                    )
                for i, value in enumerate([0.1234567890123456, 0.9]):
                    await store.execute(
                        "INSERT INTO samples VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            run_id,
                            "test-boot",
                            i,
                            (i + 1) / 50,
                            0.5,
                            value,
                            0.2,
                            value / 2,
                            f"2026-01-01T00:00:00.{i + 1:06d}Z",
                            f"2026-01-01T00:00:00.{100000 + i:06d}Z",
                            1 + i / 50,
                        ),
                    )
                await store.event(str(run_id), "recording_partial", {"reason": "missing_tail"})
                prefix = "/api/runs/" + str(run_id)
                assert (
                    await client.get(
                        "/api/runs",
                        params={
                            "q": "x,y",
                            "recording": "partial",
                            "device": "sim-01",
                            "since": "2026-01-01",
                            "until": "2026-01-01",
                        },
                    )
                ).json()[0]["id"] == str(run_id)
                assert (await client.get("/api/runs", params={"q": "%"})).json() == []
                assert (
                    await client.get("/api/runs", params={"since": "2026-01-02", "until": "2026-01-01"})
                ).status_code == 422
                chart = (await client.get(prefix + "/chart", params={"from_s": 0.03, "to_s": 0.1})).json()
                assert chart["sample_count"] == 1
                stats = (await client.get(prefix + "/summary")).json()
                assert stats["sample_count"] == 2 and stats["missing_samples"] == 2
                assert stats["raw_mean"] == pytest.approx((0.1234567890123456 + 0.9) / 2)
                exported = await client.get(prefix + "/export.csv")
                assert exported.status_code == 200
                rows = list(csv.DictReader(io.StringIO(exported.text)))
                assert len(rows) == 2
                assert rows[0]["run_name"] == "'" + snapshot["name"]
                assert float(rows[0]["response_raw_au"]) == 0.1234567890123456
                assert rows[-1]["unrecorded_tail_samples"] == "2"
                assert rows[-1]["recording_status"] == "partial"
                assert rows[0]["source_timestamp_utc"] != rows[0]["receipt_timestamp_utc"]
                metadata = (await client.get(prefix + "/metadata.json")).json()
                assert metadata["run"]["snapshot"] == snapshot
                playback = (await client.get(prefix + "/replay")).json()
                assert playback["mode"] == "saved-observations"
                assert [p["seq"] for p in playback["samples"]] == [0, 1]
                assert playback["samples"][0]["replay_s"] == 0.02
                assert playback["duration_s"] == 0.04
                assert playback["events"][0]["replay_s"] == 0.04
                assert len(playback["events"]) == 1
                assert (await store.rows("SELECT count(*) AS n FROM commands"))[0]["n"] == 0
                assert len((await client.get("/api/runs")).json()) == 1
                assert (await client.get("/api/runs/" + str(uuid4()) + "/replay")).status_code == 404
                assert (await client.get(prefix + "/chart?max_points=6000")).status_code == 422
                # Empty stopped recordings export a header and have no invented statistics.
                await store.execute(
                    "UPDATE runs SET persisted_seq=-1,final_seq=-1,execution='STOPPED',"
                    "recording='complete' WHERE id=%s",
                    (run_id,),
                )
                assert (
                    len(list(csv.DictReader(io.StringIO((await client.get(prefix + "/export.csv")).text))))
                    == 0
                )
                assert (await client.get(prefix + "/summary")).json()["raw_mean"] is None
                await store.execute("UPDATE runs SET recording='recording' WHERE id=%s", (run_id,))
                assert (await client.get(prefix + "/replay")).status_code == 409
                assert (await client.get(prefix + "/export.csv")).status_code == 409

    asyncio.run(check())


def test_downsampling_keeps_channel_extrema_order_and_bounds():
    points = [{"seq": i, "response": 0.0, "filtered": 0.0, "reference": 0.0} for i in range(6000)]
    points[17]["response"] = 99.0
    points[3333]["filtered"] = -99.0
    points[5888]["reference"] = 88.0
    shown = chart_points(points, 50)
    assert len(shown) <= 50
    assert [p["seq"] for p in shown] == sorted({p["seq"] for p in shown})
    assert {0, 17, 3333, 5888, 5999} <= {p["seq"] for p in shown}
    assert chart_points([], 50) == []
    assert chart_points(points[:2], 50) == points[:2]


@pytest.mark.parametrize("value", ["=1+1", " +SUM(A1)", "-1", "@command", "\ttext", "\ntext"])
def test_csv_formula_prefixes_are_neutralized(value):
    assert csv_text(value) == "'" + value
