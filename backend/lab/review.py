"""Read-only history, export and replay. This module has no instrument dependency."""

import csv
import io
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from .store import Store

SAMPLE_FIELDS = "seq,logical_s,setpoint,response,reference,filtered,source_utc,received_utc,device_elapsed_s"
RUN_FIELDS = (
    "id,device_id,boot_id,recipe_id,snapshot,execution,recording,reason,persisted_seq,final_seq,"
    "created_at,finished_at"
)


def chart_points(points: list[dict], budget: int) -> list[dict]:
    """Keep endpoints and each channel's min/max in evenly sized index buckets."""
    if len(points) <= budget:
        return points
    buckets = max(1, (budget - 2) // 6)
    width = math.ceil((len(points) - 2) / buckets)
    indices = {0, len(points) - 1}
    for start in range(1, len(points) - 1, width):
        group = range(start, min(start + width, len(points) - 1))
        for key in ("response", "filtered", "reference"):
            indices.add(min(group, key=lambda i: points[i][key]))
            indices.add(max(group, key=lambda i: points[i][key]))
    return [points[i] for i in sorted(indices)]


def csv_text(value) -> str:
    text = str(value)
    # Quoting handles delimiters, but spreadsheet formula cells also need escaping.
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n"))
        else text
    )


async def get_run(store: Store, run_id: UUID | str) -> dict:
    rows = await store.rows("SELECT " + RUN_FIELDS + " FROM runs WHERE id=%s", (run_id,))
    if not rows:
        raise HTTPException(404, "Run not found")
    return rows[0]


async def summary(store: Store, run: dict) -> dict:
    values = (
        await store.rows(
            "SELECT count(*) AS sample_count,min(seq) AS first_seq,max(seq) AS last_seq,"
            "min(logical_s) AS first_logical_s,max(logical_s) AS last_logical_s,"
            "min(response) AS raw_min,max(response) AS raw_max,avg(response) AS raw_mean,"
            "stddev_pop(response) AS raw_stddev,avg(filtered) AS filtered_mean,"
            "stddev_pop(filtered) AS filtered_stddev,avg(reference) AS reference_mean "
            "FROM samples WHERE run_id=%s AND seq<=%s",
            (run["id"], run["persisted_seq"]),
        )
    )[0]
    values["missing_samples"] = (
        None if run["final_seq"] is None else max(0, run["final_seq"] + 1 - values["sample_count"])
    )
    return {"version": "summary-1", "population": "all committed samples", "unit": "a.u.", **values}


def review_routes(store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/runs")

    @router.get("")
    async def runs(
        q: str = Query("", max_length=80),
        execution: Literal[
            "", "PENDING", "RUNNING", "COMPLETED", "STOPPED", "FAULTED", "UNKNOWN", "REJECTED"
        ] = "",
        recording: Literal["", "recording", "draining", "complete", "partial"] = "",
        device: str = Query("", max_length=80),
        since: date | None = None,
        until: date | None = None,
        offset: int = Query(0, ge=0, le=10000),
        limit: int = Query(50, ge=1, le=100),
    ):
        if since and until and since > until:
            raise HTTPException(422, "Start date must not be after end date")
        clauses: list[str] = []
        params: list[Any] = []
        if q:
            clauses.append("snapshot->>'name' ILIKE %s")
            params.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        for key, value in (("execution", execution), ("recording", recording), ("device_id", device)):
            if value:
                clauses.append(key + "=%s")
                params.append(value)
        if since:
            clauses.append("created_at >= %s")
            params.append(datetime.combine(since, datetime.min.time(), UTC))
        if until:
            if until == date.max:
                raise HTTPException(422, "End date is outside the supported range")
            clauses.append("created_at < %s")
            params.append(datetime.combine(until + timedelta(days=1), datetime.min.time(), UTC))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return await store.rows(
            "SELECT id,device_id,snapshot->>'name' AS name,execution,recording,reason,"
            "persisted_seq,final_seq,"
            "created_at,finished_at FROM runs"
            + where
            + " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )

    @router.get("/{run_id}")
    async def detail(run_id: UUID):
        run = await get_run(store, run_id)
        events = await store.rows(
            "SELECT id,kind,detail,created_at FROM events WHERE run_id=%s ORDER BY id LIMIT 201",
            (run_id,),
        )
        return {**run, "events": events[:200], "events_more": len(events) > 200}

    @router.get("/{run_id}/events")
    async def events(run_id: UUID, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=200)):
        await get_run(store, run_id)
        rows = await store.rows(
            "SELECT id,kind,detail,created_at FROM events WHERE run_id=%s AND id>%s ORDER BY id LIMIT %s",
            (run_id, after, limit + 1),
        )
        return {"events": rows[:limit], "more": len(rows) > limit}

    @router.get("/{run_id}/samples")
    async def samples(
        run_id: UUID, after: int = Query(-1, ge=-1, le=5999), limit: int = Query(6000, ge=1, le=6000)
    ):
        await get_run(store, run_id)
        return await store.rows(
            "SELECT " + SAMPLE_FIELDS + " FROM samples WHERE run_id=%s AND seq>%s ORDER BY seq LIMIT %s",
            (run_id, after, limit),
        )

    @router.get("/{run_id}/chart")
    async def chart(
        run_id: UUID,
        from_s: float = Query(0, ge=0, le=60),
        to_s: float = Query(60, ge=0, le=60),
        max_points: int = Query(800, ge=50, le=1200),
    ):
        run = await get_run(store, run_id)
        if from_s > to_s:
            raise HTTPException(422, "Chart start must not follow chart end")
        points = await store.rows(
            "SELECT " + SAMPLE_FIELDS + " FROM samples WHERE run_id=%s AND seq<=%s "
            "AND logical_s BETWEEN %s AND %s ORDER BY seq LIMIT 6000",
            (run_id, run["persisted_seq"], from_s, to_s),
        )
        return {
            "points": chart_points(points, max_points),
            "sample_count": len(points),
            "method": "bucket-channel-extrema-1",
            "recording": run["recording"],
        }

    @router.get("/{run_id}/summary")
    async def statistics(run_id: UUID):
        return await summary(store, await get_run(store, run_id))

    async def metadata(run_id: UUID):
        run = await get_run(store, run_id)
        event_rows = await store.rows(
            "SELECT id,kind,detail,created_at FROM events WHERE run_id=%s ORDER BY id LIMIT 2001",
            (run_id,),
        )
        commands = await store.rows(
            "SELECT id,kind,payload,outcome,created_at FROM commands "
            "WHERE run_id=%s ORDER BY created_at LIMIT 201",
            (run_id,),
        )
        return {
            "format": "experiment-lab-metadata-1",
            "run": run,
            "summary": await summary(store, run),
            "events": event_rows[:2000],
            "events_truncated": len(event_rows) > 2000,
            "commands": commands[:200],
            "commands_truncated": len(commands) > 200,
            "timing": {
                "civil": "UTC",
                "logical_s": "fixed simulated ticks since run start",
                "device_elapsed_s": "monotonic within the recorded boot only",
                "received_utc": "orchestrator receipt, including transport and scheduling delay",
            },
            "csv": {
                "text_escape": "Potential spreadsheet formulas have a leading apostrophe",
                "missing_tail": "Blank when final sample sequence is unknown",
            },
        }

    @router.get("/{run_id}/metadata.json")
    async def metadata_download(run_id: UUID):
        return JSONResponse(
            jsonable_encoder(await metadata(run_id)),
            headers={
                "Content-Disposition": f'attachment; filename="run-{run_id}-metadata.json"',
            },
        )

    @router.get("/{run_id}/export.csv")
    async def export(run_id: UUID):
        run = await get_run(store, run_id)
        if run["recording"] in {"recording", "draining"}:
            raise HTTPException(409, "Wait for recording to finish before exporting")
        points = await store.rows(
            "SELECT " + SAMPLE_FIELDS + " FROM samples WHERE run_id=%s AND seq<=%s ORDER BY seq LIMIT 6000",
            (run_id, run["persisted_seq"]),
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "run_id",
                "run_name",
                "device_id",
                "boot_id",
                "recipe_version_id",
                "sequence",
                "logical_time_s",
                "source_timestamp_utc",
                "receipt_timestamp_utc",
                "device_elapsed_s",
                "setpoint_au",
                "response_raw_au",
                "reference_raw_au",
                "response_ema_au",
                "recording_status",
                "missing_before_sample",
                "unrecorded_tail_samples",
                "quality_reason",
            ]
        )
        last = -1
        tail = "" if run["final_seq"] is None else max(0, run["final_seq"] - run["persisted_seq"])
        for point in points:
            writer.writerow(
                [
                    run_id,
                    csv_text(run["snapshot"]["name"]),
                    csv_text(run["device_id"]),
                    csv_text(run["boot_id"]),
                    run["recipe_id"],
                    point["seq"],
                    point["logical_s"],
                    point["source_utc"].isoformat(),
                    point["received_utc"].isoformat(),
                    point["device_elapsed_s"],
                    point["setpoint"],
                    point["response"],
                    point["reference"],
                    point["filtered"],
                    run["recording"],
                    max(0, point["seq"] - last - 1),
                    tail,
                    csv_text(run["reason"]),
                ]
            )
            last = point["seq"]
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="run-{run_id}.csv"',
            },
        )

    @router.get("/{run_id}/replay")
    async def replay(run_id: UUID):
        data = await metadata(run_id)
        run = data["run"]
        if run["recording"] in {"recording", "draining"}:
            raise HTTPException(409, "Wait for recording to finish before replaying")
        points = await store.rows(
            "SELECT " + SAMPLE_FIELDS + " FROM samples WHERE run_id=%s AND seq<=%s ORDER BY seq LIMIT 6000",
            (run_id, run["persisted_seq"]),
        )
        # Playback uses saved logical sample time, never a newly simulated signal.
        # Event UTC positions are approximate and capped: a later reconciliation
        # must not turn a sixty-second acquisition into hours of empty playback.
        duration = points[-1]["logical_s"] if points else 0.0
        for point in points:
            point["replay_s"] = point["logical_s"]
        for event in data["events"]:
            event["replay_s"] = min(
                duration, max(0, (event["created_at"] - run["created_at"]).total_seconds())
            )
        return {
            **data,
            "samples": points,
            "chart": chart_points(points, 800),
            "duration_s": duration,
            "mode": "saved-observations",
            "clock": "saved logical sample time",
        }

    return router
