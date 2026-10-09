import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from .filtering import EMA
from .instrument import Instrument, read_frame
from .models import Sample, StartRequest
from .store import Store

log = logging.getLogger("lab")
TERMINAL = {"COMPLETED", "STOPPED", "FAULTED"}


class Orchestrator:
    def __init__(self, store: Store):
        self.store = store
        self.link = Instrument()
        self.actions = asyncio.Lock()
        self.observation: dict = {"state": "UNKNOWN", "run_id": "", "final_seq": -1, "output": None}
        self.active: str | None = None
        self.filters: dict[str, EMA] = {}
        self.drain_deadline: float | None = None
        self.last_seen: float | None = None
        self.error = "Connecting to instrument"
        self.task: asyncio.Task | None = None

    async def run(self):
        delay = 0.5
        while True:
            try:
                await self.link.connect()
                delay = 0.5
                self.error = ""
                # An interrupted application does not fabricate completion or repeat Start.
                pending = await self.store.rows(
                    "SELECT id FROM runs WHERE recording IN ('recording','draining') ORDER BY created_at"
                )
                self.active = str(pending[0]["id"]) if pending else None
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(self.monitor())
                    tasks.create_task(self.ingest())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = "Instrument/data connection interrupted; execution needs reconciliation"
                log.warning(json.dumps({"event": "connection_interrupted", "error_type": type(exc).__name__}))
                if self.active:
                    try:
                        await self.store.execute(
                            "UPDATE runs SET execution='UNKNOWN',recording='partial',reason=%s WHERE id=%s",
                            ("connection_interrupted", self.active),
                        )
                        await self.store.event(self.active, "connection_interrupted", {"outcome": "unknown"})
                    except Exception:
                        log.error('{"event":"could_not_persist_interruption"}')
                self.active = None
                self.filters.clear()
            finally:
                await self.link.close()  # Engine independently faults on controller loss.
            await asyncio.sleep(delay)
            delay = min(5, delay * 2)

    async def monitor(self):
        while True:
            response = await self.link.call("status")  # Also renews the controller lease.
            if not response.get("ok"):
                raise ConnectionError("Status rejected")
            self.observation = response["status"]
            self.last_seen = time.monotonic()
            run_id = self.observation.get("run_id")
            if run_id:
                rows = await self.store.rows("SELECT * FROM runs WHERE id=%s", (run_id,))
                if rows:
                    row = rows[0]
                    if row["boot_id"] != self.link.boot_id:
                        raise ConnectionError("Saved run belongs to a different engine boot")
                    if self.observation["state"] in TERMINAL:
                        await self.observe_terminal(row)
                    elif self.observation["state"] == "RUNNING":
                        if row["execution"] != "RUNNING":
                            await self.store.execute(
                                "UPDATE runs SET execution='RUNNING' WHERE id=%s", (run_id,)
                            )
                            await self.store.event(run_id, "device_observed", self.observation)
            await asyncio.sleep(0.4)

    async def observe_terminal(self, row):
        run_id = str(row["id"])
        final_seq = self.observation["final_seq"]
        complete = row["persisted_seq"] == final_seq
        if row["execution"] != self.observation["state"] or row["final_seq"] != final_seq:
            await self.store.event(run_id, "device_terminal", self.observation)
            self.drain_deadline = time.monotonic() + 3
        timed_out = self.drain_deadline is not None and time.monotonic() > self.drain_deadline
        recording = "complete" if complete else ("partial" if timed_out else "draining")
        reason = self.observation.get("reason", "")
        if recording == "partial":
            reason += ";missing_samples"
        if (row["execution"], row["recording"], row["final_seq"], row["reason"]) != (
            self.observation["state"],
            recording,
            final_seq,
            reason,
        ):
            await self.store.execute(
                "UPDATE runs SET execution=%s,recording=%s,final_seq=%s,reason=%s,"
                "finished_at=COALESCE(finished_at,now()) WHERE id=%s",
                (self.observation["state"], recording, final_seq, reason, run_id),
            )
        if recording in {"complete", "partial"} and self.active == run_id:
            self.active = None
            self.filters.pop(run_id, None)

    async def ingest(self):
        reader = self.link.telemetry_reader
        if reader is None:
            raise ConnectionError("Telemetry disconnected")
        while True:
            frame = await read_frame(reader)
            received = datetime.now(UTC)
            if (
                frame.get("type") != "samples"
                or frame.get("boot_id") != self.link.boot_id
                or frame.get("instrument_id") != self.link.device_id
            ):
                raise ConnectionError("Misrouted telemetry")
            samples = frame.get("samples")
            if not isinstance(samples, list) or not 1 <= len(samples) <= 25:
                raise ConnectionError("Invalid sample batch")
            run_id = frame["run_id"]
            # Awaiting each bounded transaction applies backpressure to the data socket,
            # while the independent control coroutine remains available.
            async with self.store.transaction() as cur:
                await cur.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,))
                row = await cur.fetchone()
                if row is None or row["boot_id"] != self.link.boot_id:
                    raise ConnectionError("Unknown run or boot")
                last = row["persisted_seq"]
                await cur.execute(
                    "SELECT filtered FROM samples WHERE run_id=%s AND boot_id=%s AND seq=%s",
                    (run_id, self.link.boot_id, last),
                )
                previous = await cur.fetchone()
                ema = EMA(
                    row["snapshot"]["filter"]["alpha"], last, previous["filtered"] if previous else None
                )
                for raw in samples:
                    sample = Sample.model_validate(raw)
                    if sample.seq <= last:
                        await cur.execute(
                            "SELECT response,reference,logical_s,setpoint FROM samples "
                            "WHERE run_id=%s AND boot_id=%s AND seq=%s",
                            (run_id, self.link.boot_id, sample.seq),
                        )
                        old = await cur.fetchone()
                        if not old or any(old[k] != getattr(sample, k) for k in old):
                            raise ConnectionError("Conflicting duplicate sample")
                        continue
                    filtered = ema.apply(sample.seq, sample.response)
                    await cur.execute(
                        "INSERT INTO samples VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            run_id,
                            self.link.boot_id,
                            sample.seq,
                            sample.logical_s,
                            sample.setpoint,
                            sample.response,
                            sample.reference,
                            filtered,
                            sample.source_utc,
                            received,
                            sample.device_elapsed_s,
                        ),
                    )
                    last = sample.seq
                await cur.execute("UPDATE runs SET persisted_seq=%s WHERE id=%s", (last, run_id))
            # No telemetry durability ACK in Phase 1: that is a Phase 2 extension.

    async def start(self, request: StartRequest):
        payload = request.model_dump(mode="json")
        command_id = str(request.command_id)
        async with self.actions:
            known = await self.store.rows("SELECT * FROM commands WHERE id=%s", (command_id,))
            if known:
                if known[0]["kind"] != "start" or known[0]["payload"] != payload:
                    raise HTTPException(409, "Command ID conflicts with an earlier request")
                return {"run_id": str(known[0]["run_id"]), "outcome": known[0]["outcome"]}
            if not self.link.connected or self.observation["state"] not in {"IDLE", "STOPPED", "COMPLETED"}:
                raise HTTPException(409, "Instrument is not ready for a new run")
            if await self.store.rows("SELECT id FROM runs WHERE recording IN ('recording','draining')"):
                raise HTTPException(409, "The previous recording is still being finalized")
            run_id, recipe_id = str(uuid4()), str(uuid4())
            snapshot = {
                "name": request.name,
                "recipe": payload["recipe"],
                "filter": {"version": "ema-1", "alpha": request.alpha},
                "channels": [{"name": "response", "unit": "a.u."}, {"name": "reference", "unit": "a.u."}],
                "model": {"version": "first-order-1", "tau_s": 0.5, "noise": "xorshift32-uniform-0.02"},
                "protocol_version": 1,
                "engine_version": "0.1.0",
                "build": "phase-1",
            }
            async with self.store.transaction() as cur:
                await cur.execute(
                    "INSERT INTO recipe_versions(id,name,content) VALUES (%s,%s,%s)",
                    (recipe_id, request.name, Jsonb(payload["recipe"])),
                )
                await cur.execute(
                    "INSERT INTO runs(id,device_id,boot_id,recipe_id,snapshot) VALUES (%s,%s,%s,%s,%s)",
                    (run_id, self.link.device_id, self.link.boot_id, recipe_id, Jsonb(snapshot)),
                )
                await cur.execute(
                    "INSERT INTO commands(id,run_id,kind,payload) VALUES (%s,%s,'start',%s)",
                    (command_id, run_id, Jsonb(payload)),
                )
                await cur.execute(
                    "INSERT INTO events(run_id,kind,detail) VALUES (%s,'start_requested',%s)",
                    (run_id, Jsonb({"command_id": command_id})),
                )
            self.active = run_id
            await self.send_command("start", command_id, run_id, recipe=payload["recipe"])
            return {"run_id": run_id}

    async def send_command(self, kind, command_id, run_id, **fields):
        try:
            result = await self.link.call(
                kind, request_id=command_id, command_id=command_id, run_id=run_id, **fields
            )
        except (TimeoutError, ConnectionError, OSError, ValueError):
            await self.store.execute(
                "UPDATE commands SET outcome=%s WHERE id=%s",
                (Jsonb({"outcome": "unknown"}), command_id),
            )
            await self.store.event(run_id, "command_outcome_unknown", {"command_id": command_id})
            await self.link.close()
            raise HTTPException(503, "Command outcome unknown; waiting for device reconciliation") from None
        await self.store.execute("UPDATE commands SET outcome=%s WHERE id=%s", (Jsonb(result), command_id))
        await self.store.event(run_id, "command_result", {"command_id": command_id, "response": result})
        if not result.get("ok"):
            if kind == "start":
                await self.store.execute(
                    "UPDATE runs SET execution='REJECTED',recording='complete',final_seq=-1,"
                    "reason=%s,finished_at=now() WHERE id=%s",
                    (result["error"]["code"], run_id),
                )
                self.active = None
            raise HTTPException(409, result["error"]["message"])
        self.observation = result["status"]
        self.last_seen = time.monotonic()
        return result

    async def stop(self, run_id: str, command_id: str):
        async with self.actions:
            payload = {"run_id": run_id}
            known = await self.store.rows("SELECT * FROM commands WHERE id=%s", (command_id,))
            if known:
                if known[0]["kind"] != "stop" or known[0]["payload"] != payload:
                    raise HTTPException(409, "Command ID conflicts with an earlier request")
                return known[0]["outcome"] or {"outcome": "unknown"}
            if not self.link.connected:
                raise HTTPException(503, "Instrument disconnected; Stop cannot yet be confirmed")
            if not await self.store.rows("SELECT id FROM runs WHERE id=%s", (run_id,)):
                raise HTTPException(404, "Run not found")
            await self.store.execute(
                "INSERT INTO commands(id,run_id,kind,payload) VALUES (%s,%s,'stop',%s)",
                (command_id, run_id, Jsonb(payload)),
            )
            await self.store.event(run_id, "stop_requested", {"command_id": command_id})
            return await self.send_command("stop", command_id, run_id)
