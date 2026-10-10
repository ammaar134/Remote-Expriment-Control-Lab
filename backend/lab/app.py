import asyncio
import logging
import os
import signal
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
from .recipes import recipe_routes
from .review import review_routes
from .security import AccessControls, AccessSettings
from .store import OwnerBusyError, Store

logging.basicConfig(level=logging.INFO, format="%(message)s")
store = Store(os.environ.get("DATABASE_URL", ""))
orchestrator = Orchestrator(store)
access = AccessSettings.from_environment()


async def maintain_database_session():
    while True:
        # A session advisory lock needs the same live connection. Neon suspends
        # idle compute even with a connection open, so renew activity while this
        # hosted controller is running. Render can still sleep on HTTP inactivity.
        async with asyncio.timeout(10):
            await store.rows("SELECT 1")
        await asyncio.sleep(20)


async def own_and_run(app: FastAPI):
    deadline = time.monotonic() + 180
    while True:
        try:
            await store.open()
            app.state.ready = app.state.startup_healthy = True
            break
        except (psycopg.OperationalError, OwnerBusyError) as exc:
            await store.close()
            # During a rolling deploy, allow traffic to switch so the old owner can
            # shut down. Controls stay unavailable until its session lock is released.
            app.state.startup_healthy = access.mode == "hosted" and isinstance(exc, OwnerBusyError)
            if time.monotonic() >= deadline:
                app.state.startup_healthy = False
                logging.error('{"event":"startup_deadline_expired"}')
                return
            await asyncio.sleep(2)
        except Exception as exc:
            await store.close()
            app.state.startup_healthy = False
            logging.error('{"event":"startup_failed","error_type":"%s"}', type(exc).__name__)
            return
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(orchestrator.run())
            tasks.create_task(maintain_database_session())
    except Exception as exc:
        # Losing this connection also loses exclusive ownership. Shut down both
        # processes through the hosted supervisor; a fresh boot reacquires the
        # lock rather than continuing to control with an unowned connection.
        logging.error('{"event":"database_session_failed","error_type":"%s"}', type(exc).__name__)
        app.state.ready = app.state.startup_healthy = False
        os.kill(os.getpid(), signal.SIGTERM)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if int(os.getenv("WEB_CONCURRENCY", "1")) != 1:
        raise RuntimeError("Run exactly one API worker")
    app.state.ready = app.state.startup_healthy = False
    orchestrator.task = asyncio.create_task(own_and_run(app))
    try:
        yield
    finally:
        app.state.ready = app.state.startup_healthy = False
        orchestrator.task.cancel()
        with suppress(asyncio.CancelledError):
            await orchestrator.task
        await store.close()


app = FastAPI(title="Remote Experiment Control Lab", lifespan=lifespan)
app.state.ready = app.state.startup_healthy = False


@app.middleware("http")
async def ready_controls(request: Request, call_next):
    if request.url.path.startswith("/api/") and not app.state.ready:
        return JSONResponse(
            {"detail": "Starting the experiment service; please retry shortly"},
            status_code=503,
            headers={"Retry-After": "2"},
        )
    return await call_next(request)


app.add_middleware(AccessControls, settings=access)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=access.hosts)


@app.get("/healthz")
async def platform_health():
    return JSONResponse(
        {"status": "ok" if app.state.startup_healthy else "starting"},
        status_code=200 if app.state.startup_healthy else 503,
    )


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
        "recovering": orchestrator.recovering,
        "faults_enabled": orchestrator.faults_enabled,
        "diagnostics": {
            "command_retries": orchestrator.link.retry_count,
            "telemetry_reconnects": orchestrator.link.telemetry_reconnects,
        },
    }


app.include_router(recipe_routes(store))
app.include_router(review_routes(store))


@app.post("/api/runs", status_code=202)
async def start(request: StartRequest):
    return await orchestrator.start(request)


@app.post("/api/runs/{run_id}/stop", status_code=202)
async def stop(run_id: UUID, request: StopRequest):
    return await orchestrator.stop(str(run_id), str(request.command_id))


@app.post("/api/device/reset")
async def reset(request: StopRequest):
    async with orchestrator.actions:
        if await store.rows("SELECT id FROM runs WHERE recording IN ('recording','draining')"):
            raise HTTPException(409, "Wait for recording reconciliation before resetting the fault")
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
