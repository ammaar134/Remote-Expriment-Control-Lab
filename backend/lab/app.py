import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import StartRequest, StopRequest
from .orchestrator import Orchestrator
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(message)s")
store = Store(os.environ.get("DATABASE_URL", ""))
orchestrator = Orchestrator(store)
ORIGINS = {
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("LAB_MODE", "local") != "local":
        raise RuntimeError("Only the unauthenticated local demo mode is implemented")
    if int(os.getenv("WEB_CONCURRENCY", "1")) != 1:
        raise RuntimeError("Run exactly one API worker")
    for attempt in range(10):
        try:
            await store.open()
            break
        except psycopg.OperationalError:
            await store.close()
            if attempt == 9:
                raise
            await asyncio.sleep(min(attempt + 1, 3))
    orchestrator.task = asyncio.create_task(orchestrator.run())
    try:
        yield
    finally:
        orchestrator.task.cancel()
        with suppress(asyncio.CancelledError):
            await orchestrator.task
        await store.close()


app = FastAPI(title="Remote Experiment Control Lab", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "lab", "testserver"])


@app.middleware("http")
async def local_controls(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ORIGINS:
        return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    if request.method in {"POST", "PUT", "PATCH"}:
        length = request.headers.get("content-length")
        if not length or not length.isdigit() or int(length) > 65_536:
            return JSONResponse({"detail": "A body of at most 64 KiB is required"}, status_code=413)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "JSON is required"}, status_code=415)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error):
    return JSONResponse({"detail": "Database unavailable; recording may be incomplete"}, status_code=503)


@app.get("/api/health")
async def health():
    await store.rows("SELECT 1")
    return {"api": "ready", "database": "ready", "instrument_connected": orchestrator.link.connected}


@app.get("/api/device")
async def device():
    age = None if orchestrator.last_seen is None else time.monotonic() - orchestrator.last_seen
    return {
        "id": "sim-01",
        "name": "Response simulator",
        "connected": orchestrator.link.connected,
        "boot_id": orchestrator.link.boot_id,
        "observation": orchestrator.observation,
        "observation_age_s": age,
        "error": orchestrator.error,
    }


@app.get("/api/runs")
async def runs():
    return await store.rows(
        "SELECT id,snapshot->>'name' AS name,execution,recording,reason,persisted_seq,final_seq,"
        "created_at,finished_at FROM runs ORDER BY created_at DESC LIMIT 50"
    )


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: UUID):
    rows = await store.rows("SELECT * FROM runs WHERE id=%s", (run_id,))
    if not rows:
        raise HTTPException(404, "Run not found")
    events = await store.rows(
        "SELECT id,kind,detail,created_at FROM events WHERE run_id=%s ORDER BY id LIMIT 200", (run_id,)
    )
    return {**rows[0], "events": events}


@app.get("/api/runs/{run_id}/samples")
async def samples(run_id: UUID, after: int = -1):
    if after < -1 or after > 5999:
        raise HTTPException(422, "Sequence outside allowed bounds")
    return await store.rows(
        "SELECT seq,logical_s,setpoint,response,reference,filtered,source_utc,received_utc "
        "FROM samples WHERE run_id=%s AND seq>%s ORDER BY seq LIMIT 6000",
        (run_id, after),
    )


@app.post("/api/runs", status_code=202)
async def start(request: StartRequest):
    return await orchestrator.start(request)


@app.post("/api/runs/{run_id}/stop", status_code=202)
async def stop(run_id: UUID, request: StopRequest):
    return await orchestrator.stop(str(run_id), str(request.command_id))


@app.post("/api/device/reset")
async def reset(request: StopRequest):
    async with orchestrator.actions:
        known = await store.rows("SELECT kind,outcome FROM commands WHERE id=%s", (request.command_id,))
        if known:
            if known[0]["kind"] != "reset":
                raise HTTPException(409, "Command ID conflict")
            return known[0]["outcome"] or {"outcome": "unknown"}
        if not orchestrator.link.connected:
            raise HTTPException(503, "Instrument disconnected")
        await store.execute(
            "INSERT INTO commands(id,kind,payload) VALUES (%s,'reset',%s)",
            (request.command_id, Jsonb({})),
        )
        result = await orchestrator.link.call(
            "reset", command_id=str(request.command_id), request_id=str(request.command_id)
        )
        await store.execute("UPDATE commands SET outcome=%s WHERE id=%s", (Jsonb(result), request.command_id))
        await store.event(None, "fault_reset_result", result)
        if not result.get("ok"):
            raise HTTPException(409, result["error"]["message"])
        orchestrator.observation = result["status"]
        return result


app.mount("/", StaticFiles(directory="static", html=True, check_dir=False), name="frontend")
