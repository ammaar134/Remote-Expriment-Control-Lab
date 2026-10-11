import asyncio
import copy
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi import FastAPI, HTTPException
from psycopg.types.json import Jsonb
from test_review import database

from lab.instrument import Instrument
from lab.models import Recipe, StartRequest, Step
from lab.orchestrator import Orchestrator
from lab.timing import TimingLab, aligned, estimate, timing_routes


def stamp(seconds):
    return datetime.fromtimestamp(1_780_000_000 + seconds, UTC).isoformat()


def probe(t, offset=1.2, drift=0.005, outbound=0.001, inbound=0.001):
    return {
        "ok": True,
        "attempts": 1,
        "elapsed_s": t + (outbound + inbound) / 2,
        "transport_timing": {
            "sent_utc": stamp(t),
            "received_utc": stamp(t + outbound + inbound),
            "roundtrip_s": outbound + inbound,
        },
        "device_receive_utc": stamp(t + outbound + offset + (t + outbound) * drift),
        "device_send_utc": stamp(t + outbound + offset + (t + outbound) * drift),
    }


def test_measured_drift_alignment_and_immutable_originals():
    evidence = [probe(t) for t in range(31)]
    original = copy.deepcopy(evidence)
    result = estimate(evidence)
    assert result["drift_ppm"] == pytest.approx(5000, abs=0.1)
    assert result["offset_ms"] == pytest.approx(1275.005, abs=0.01)
    assert result["uncertainty_ms"] >= 1
    source = datetime.fromisoformat(stamp(10 + 1.2 + 10 * 0.005))
    assert (
        abs(
            datetime.fromisoformat(aligned(source, result)).timestamp()
            - datetime.fromisoformat(stamp(10)).timestamp()
        )
        < 0.00001
    )
    assert aligned(datetime.fromisoformat(stamp(80)), result) is None
    assert original == evidence


def test_insufficient_jitter_retry_and_clock_step_are_explicit():
    assert estimate([])["offset_ms"] is None
    assert estimate([probe(0), probe(1)])["offset_ms"] is None
    assert estimate([probe(t) for t in range(10)])["drift_ppm"] is None
    jitter = [probe(t, outbound=0.10, inbound=0.10) for t in range(31)]
    assert estimate(jitter)["drift_ppm"] is None
    retried = [probe(t) for t in range(31)]
    for item in retried:
        item["attempts"] = 2
    assert estimate(retried)["accepted"] == 0
    jump = [probe(t) for t in range(31)]
    for item in jump[15:]:
        item["elapsed_s"] -= 1
    assert "discontinuity" in estimate(jump)["reason"]
    bad_wall = [probe(t) for t in range(31)]
    for item in bad_wall:
        item["transport_timing"]["roundtrip_s"] = 0.2
    assert estimate(bad_wall)["offset_ms"] is None


def test_asymmetric_delay_bias_stays_visible_in_uncertainty():
    evidence = [probe(t, drift=0, outbound=0.018, inbound=0.002) for t in range(31)]
    result = estimate(evidence)
    assert result["offset_ms"] == pytest.approx(1208, abs=0.01)
    assert result["uncertainty_ms"] >= 10
    assert abs(result["offset_ms"] - 1200) < result["uncertainty_ms"]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="Real PostgreSQL required")
def test_group_idempotency_partial_start_stop_and_append_only_probes():
    class Unavailable:
        async def start(self, request):
            raise HTTPException(409, "Instrument is not ready for a new run")

    async def check():
        async with database() as store:
            await store.connection.execute(Path("migrations/002_recipe_revisions.sql").read_text())
            await store.connection.execute(Path("migrations/003_timing.sql").read_text())
            lab = TimingLab(store, {"sim-01": Unavailable(), "sim-02": Unavailable()})
            app = FastAPI()
            app.include_router(timing_routes(lab))
            request = {
                "request_id": str(uuid4()),
                "duration_s": 1,
                "clocks": [{"offset_ms": -750, "drift_ppm": -3000}, {"offset_ms": 1200, "drift_ppm": 5000}],
            }
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://testserver"
            ) as c:
                a, b = await asyncio.gather(
                    c.post("/api/timing", json=request), c.post("/api/timing", json=request)
                )
                assert a.status_code == b.status_code == 202 and a.json() == b.json()
                await lab.task
                group = (await c.get("/api/timing/" + request["request_id"])).json()
                assert group["status"] == "partial"
                assert all(m["start"]["outcome"] == "unconfirmed" for m in group["members"])
                assert all(m["estimate"]["offset_ms"] is None for m in group["members"])
                conflict = await c.post("/api/timing", json={**request, "duration_s": 2})
                assert conflict.status_code == 409
                assert (await c.get("/api/timing/" + str(uuid4()))).status_code == 404
                assert (await c.post("/api/timing", json={**request, "duration_s": 61})).status_code == 422
                await store.execute(
                    "INSERT INTO clock_probes VALUES (%s,'sim-01',0,'{}')", (request["request_id"],)
                )
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    await store.execute("UPDATE clock_probes SET evidence='{}'")
                with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
                    await store.execute("UPDATE timing_groups SET payload='{}'")
                await store.execute("UPDATE timing_groups SET status='collecting'")
                await lab.recover()
                assert (await store.rows("SELECT status FROM timing_groups"))[0]["status"] == "interrupted"

    asyncio.run(check())


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="Real PostgreSQL required")
def test_reconciliation_and_command_identity_stay_on_the_owning_device():
    async def check():
        async with database() as store:
            recipe_id, first, second, command_id = uuid4(), uuid4(), uuid4(), uuid4()
            await store.execute(
                "INSERT INTO recipe_versions(id,name,content) VALUES (%s,'fixture','{}')", (recipe_id,)
            )
            for device, run_id in (("sim-01", first), ("sim-02", second)):
                await store.execute(
                    "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot) "
                    "VALUES (%s,%s,'old-boot',%s,'{}')",
                    (run_id, device, recipe_id),
                )
            controller = Orchestrator(store, Instrument("sim-01"))
            controller.link.boot_id = "new-boot"
            controller.observation = {"state": "IDLE", "run_id": ""}
            await controller.reconcile()
            rows = await store.rows("SELECT device_id,execution,recording FROM runs ORDER BY device_id")
            assert rows[0] == {"device_id": "sim-01", "execution": "UNKNOWN", "recording": "partial"}
            assert rows[1] == {"device_id": "sim-02", "execution": "PENDING", "recording": "recording"}
            request = StartRequest(
                command_id=command_id,
                name="fixture",
                recipe=Recipe(steps=[Step(setpoint=0.5, duration_ms=1000)]),
            )
            await store.execute(
                "INSERT INTO commands(id,run_id,kind,payload) VALUES (%s,%s,'start',%s)",
                (command_id, second, Jsonb(request.model_dump(mode="json"))),
            )
            with pytest.raises(HTTPException, match="another device"):
                await controller.start(request)

    asyncio.run(check())
