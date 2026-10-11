"""Two independent engines; immutable ping evidence and derived clock alignment."""

import asyncio
import math
import time
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb
from pydantic import Field

from .models import ClockSettings, Recipe, StartRequest, Step, StrictModel
from .orchestrator import Orchestrator
from .store import Store

DEVICES = ("sim-01", "sim-02")


def epoch(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def estimate(probes: list[dict]) -> dict:
    """NTP-style midpoint estimator, using no injected clock parameters.

    Interval sizes are conservative *under symmetric/ bounded path delay*, not
    statistical confidence intervals and not hardware synchronization guarantees.
    """
    points = []
    for p in probes:
        if not p.get("ok") or p.get("attempts") != 1:
            continue
        t = p["transport_timing"]
        a, b = epoch(t["sent_utc"]), epoch(t["received_utc"])
        c, d = epoch(p["device_receive_utc"]), epoch(p["device_send_utc"])
        rtt = t["roundtrip_s"]
        if not all(math.isfinite(v) for v in (a, b, c, d, rtt)):
            continue
        if not 0 <= rtt <= 0.25 or d < c or abs((b - a) - rtt) > 0.02:
            continue
        points.append(((a + b) / 2, (c + d - a - b) / 2, rtt, p["elapsed_s"]))
    result = {
        "method": "midpoint-linear-v1",
        "accepted": len(points),
        "total": len(probes),
        "offset_ms": None,
        "drift_ppm": None,
        "uncertainty_ms": None,
        "drift_uncertainty_ppm": None,
        "reason": "Insufficient evidence: need three valid round trips.",
    }
    if len(points) < 3:
        return result
    # UTC steps between probes invalidate this session's relationship to UTC.
    first = points[0]
    if any(abs((p[0] - first[0]) - (p[3] - first[3])) > 0.05 for p in points):
        result["reason"] = "Clock discontinuity: UTC and local elapsed time disagree."
        return result
    origin = sum(p[0] for p in points) / len(points)
    offset = sum(p[1] for p in points) / len(points)
    span = points[-1][0] - points[0][0]
    variance = sum((p[0] - origin) ** 2 for p in points)
    slope = sum((p[0] - origin) * (p[1] - offset) for p in points) / variance if variance else 0
    residual = max(abs(p[1] - offset - slope * (p[0] - origin)) for p in points)
    uncertainty = max(p[2] for p in points) / 2 + residual + 0.000002
    rate_uncertainty = 2 * uncertainty / span * 1e6 if span > 0 else math.inf
    supported = len(points) >= 8 and span >= 20 and rate_uncertainty <= 1500 and abs(slope) < 0.02
    if not supported:
        slope = 0
        uncertainty = max(p[2] / 2 + abs(p[1] - offset) for p in points) + 0.000002
    result.update(
        {
            "offset_ms": offset * 1000,
            "drift_ppm": slope * 1e6 if supported else None,
            "uncertainty_ms": uncertainty * 1000,
            "drift_uncertainty_ppm": rate_uncertainty if supported else None,
            "origin_utc_s": origin,
            "slope": slope,
            "from_utc_s": points[0][0],
            "to_utc_s": points[-1][0],
            "span_s": span,
            "reason": "Offset and drift estimated."
            if supported
            else "Offset only; drift needs eight probes over 20 seconds with sufficiently low jitter.",
        }
    )
    return result


def aligned(source: datetime, model: dict) -> str | None:
    if model["offset_ms"] is None:
        return None
    origin = model["origin_utc_s"]
    value = origin + (source.timestamp() - origin - model["offset_ms"] / 1000) / (1 + model["slope"])
    if not model["from_utc_s"] <= value <= model["to_utc_s"]:
        return None  # No extrapolation beyond the measured observation window.
    return datetime.fromtimestamp(value, UTC).isoformat()


class TimingRequest(StrictModel):
    request_id: UUID
    duration_s: int = Field(default=30, ge=1, le=60, strict=True)
    clocks: list[ClockSettings] = Field(min_length=2, max_length=2)


class TimingLab:
    def __init__(self, store: Store, devices: dict[str, Orchestrator]):
        self.store, self.devices = store, devices
        self.lock = asyncio.Lock()
        self.task: asyncio.Task | None = None
        self.stop_requested = asyncio.Event()

    async def recover(self):
        # Engines independently fault on controller loss; never repeat old Starts.
        await self.store.execute(
            "UPDATE timing_groups SET status='interrupted', result=result || "
            '\'{"interruption":"API restarted; inspect each run reconciliation"}\'::jsonb '
            "WHERE status IN ('starting','collecting')"
        )

    async def create(self, request: TimingRequest):
        payload = request.model_dump(mode="json")
        async with self.lock:
            known = await self.store.rows("SELECT * FROM timing_groups WHERE id=%s", (request.request_id,))
            if known:
                if known[0]["payload"] != payload:
                    raise HTTPException(409, "Comparison ID conflicts with an earlier request")
                return {"id": request.request_id}
            if self.task and not self.task.done():
                raise HTTPException(409, "Wait for the current comparison to finish")
            await self.store.execute(
                "INSERT INTO timing_groups(id,payload) VALUES (%s,%s)", (request.request_id, Jsonb(payload))
            )
            self.stop_requested.clear()
            self.task = asyncio.create_task(self.acquire(request))
            return {"id": request.request_id}

    async def acquire(self, request: TimingRequest):
        group_id = str(request.request_id)
        results: dict = {}
        try:

            async def start_one(index: int, device: str):
                command_id = uuid5(NAMESPACE_URL, f"{group_id}/{device}/start")
                entry: dict = {
                    "command_id": str(command_id),
                    "requested_utc": datetime.now(UTC).isoformat(),
                    "outcome": "unconfirmed",
                }
                try:
                    await self.devices[device].start(
                        StartRequest(
                            command_id=command_id,
                            name="Clock comparison · " + device,
                            recipe=Recipe(
                                sample_rate_hz=20,
                                seed=7,
                                steps=[Step(setpoint=0.7, duration_ms=request.duration_s * 1000)],
                            ),
                            clock=request.clocks[index],
                        )
                    )
                    entry["outcome"] = "accepted"
                except HTTPException as exc:
                    entry.update(outcome="unconfirmed", detail=str(exc.detail))
                finally:
                    commands = await self.store.rows(
                        "SELECT run_id,outcome FROM commands WHERE id=%s", (command_id,)
                    )
                    if commands:
                        entry["run_id"] = str(commands[0]["run_id"])
                        entry["response"] = commands[0]["outcome"]
                    entry["resolved_utc"] = datetime.now(UTC).isoformat()
                    results[device] = entry
                    # Persist each result independently, even if its peer is interrupted.
                    await self.store.execute(
                        "UPDATE timing_groups SET result=result || %s WHERE id=%s",
                        (Jsonb({device: entry}), group_id),
                    )

            # Wait for both bounded attempts even if one fails unexpectedly, so
            # compensation cannot race a still-pending peer Start.
            attempts = await asyncio.gather(
                *(start_one(i, d) for i, d in enumerate(DEVICES)), return_exceptions=True
            )
            if any(isinstance(attempt, BaseException) for attempt in attempts):
                raise RuntimeError("A Start attempt failed unexpectedly")
            if any(v["outcome"] != "accepted" for v in results.values()):
                await self.stop_members(group_id)
                await self.store.execute("UPDATE timing_groups SET status='partial' WHERE id=%s", (group_id,))
                return
            await self.store.execute("UPDATE timing_groups SET status='collecting' WHERE id=%s", (group_id,))
            begin = time.monotonic()
            for sequence in range(request.duration_s + 1):
                if self.stop_requested.is_set():
                    break

                async def probe(device: str, sequence: int = sequence):
                    try:
                        p = await self.devices[device].link.call("clock_probe")
                        if p.get("run_id") != results[device].get("run_id"):
                            p = {"ok": False, "reason": "Device is observing another run"}
                        else:
                            p["elapsed_s"] = (
                                time.monotonic() - begin - p["transport_timing"]["roundtrip_s"] / 2
                            )
                    except (ConnectionError, OSError, TimeoutError):
                        p = {"ok": False, "reason": "Probe unavailable"}
                    await self.store.execute(
                        "INSERT INTO clock_probes VALUES (%s,%s,%s,%s)",
                        (group_id, device, sequence, Jsonb(p)),
                    )

                await asyncio.gather(*(probe(d) for d in DEVICES))
                if sequence < request.duration_s:
                    try:
                        await asyncio.wait_for(
                            self.stop_requested.wait(), max(0.01, begin + sequence + 1 - time.monotonic())
                        )
                    except TimeoutError:
                        pass
            await self.store.execute(
                "UPDATE timing_groups SET status=%s WHERE id=%s",
                ("partial" if self.stop_requested.is_set() else "complete", group_id),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed background task must not leave a comparison labelled active.
            await self.stop_members(group_id)
            await self.store.execute("UPDATE timing_groups SET status='interrupted' WHERE id=%s", (group_id,))

    async def stop_members(self, group_id: str):
        rows = await self.store.rows("SELECT result FROM timing_groups WHERE id=%s", (group_id,))
        if not rows:
            raise HTTPException(404, "Comparison not found")

        async def stop_one(device: str):
            member = rows[0]["result"].get(device, {})
            if not member.get("run_id"):
                return
            try:
                response = await self.devices[device].stop(
                    member["run_id"], str(uuid5(NAMESPACE_URL, f"{group_id}/{device}/stop"))
                )
            except HTTPException as exc:
                response = {"outcome": "unconfirmed", "detail": str(exc.detail)}
            await self.store.execute(
                "UPDATE timing_groups SET result=jsonb_set(result,%s,%s) WHERE id=%s",
                ([device, "stop_result"], Jsonb(response), group_id),
            )

        await asyncio.gather(*(stop_one(d) for d in DEVICES))

    async def detail(self, group_id: UUID, full: bool = False):
        rows = await self.store.rows("SELECT * FROM timing_groups WHERE id=%s", (group_id,))
        if not rows:
            raise HTTPException(404, "Comparison not found")
        group = rows[0]
        members = []
        for i, device in enumerate(DEVICES):
            probes = [
                r["evidence"]
                for r in await self.store.rows(
                    "SELECT evidence FROM clock_probes WHERE group_id=%s AND device_id=%s ORDER BY sequence",
                    (group_id, device),
                )
            ]
            model = estimate(probes)
            member = {
                "device_id": device,
                "injected": group["payload"]["clocks"][i],
                "estimate": model,
                "start": group["result"].get(device),
                "points": [],
                "run": None,
            }
            run_id = (member["start"] or {}).get("run_id")
            if run_id:
                runs = await self.store.rows("SELECT * FROM runs WHERE id=%s", (run_id,))
                member["run"] = runs[0] if runs else None
                samples = await self.store.rows(
                    "SELECT seq,logical_s,response,source_utc,received_utc,device_elapsed_s "
                    "FROM samples WHERE run_id=%s ORDER BY seq LIMIT 6000",
                    (run_id,),
                )
                stride = max(1, math.ceil(len(samples) / 300))
                member["points"] = [
                    {**s, "aligned_utc": aligned(s["source_utc"], model)}
                    for s in (samples if full else samples[::stride])
                ]
            if full:
                member["probes"] = probes
            members.append(member)
        return {
            **group,
            "members": members,
            "point_limit_per_device": 6000 if full else 300,
            "limitations": "Educational simulated clocks. Symmetric-delay assumption; "
            "jitter and asymmetry bias estimates. "
            "Receipt time includes scheduling and transport, not measured one-way latency. "
            "Alignment does not prove simultaneous execution. "
            "Only times inside the measured window are aligned; all originals remain unchanged.",
        }


def timing_routes(lab: TimingLab):
    router = APIRouter(prefix="/api/timing")

    @router.post("", status_code=202)
    async def create(request: TimingRequest):
        return await lab.create(request)

    @router.get("")
    async def history(offset: int = Query(0, ge=0, le=10000)):
        return await lab.store.rows(
            "SELECT id,status,created_at FROM timing_groups "
            "ORDER BY created_at DESC,id DESC LIMIT 20 OFFSET %s",
            (offset,),
        )

    @router.get("/{group_id}")
    async def detail(group_id: UUID):
        return await lab.detail(group_id)

    @router.get("/{group_id}/evidence.json")
    async def evidence(group_id: UUID):
        return JSONResponse(
            jsonable_encoder(await lab.detail(group_id, True)),
            headers={"Content-Disposition": f'attachment; filename="timing-{group_id}.json"'},
        )

    @router.post("/{group_id}/stop", status_code=202)
    async def stop(group_id: UUID):
        async with lab.lock:
            rows = await lab.store.rows("SELECT status FROM timing_groups WHERE id=%s", (group_id,))
            if not rows:
                raise HTTPException(404, "Comparison not found")
            if rows[0]["status"] in {"starting", "collecting"}:
                lab.stop_requested.set()
                # A Start may still be resolving. Await its bounded result before Stop.
                if lab.task:
                    await asyncio.shield(lab.task)
                await lab.stop_members(str(group_id))
        return {"outcome": "Stop attempts recorded; inspect each device result"}

    return router
