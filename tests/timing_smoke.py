"""Real two-process timing, evidence, Stop and partial Start (local Compose only)."""
import os
import subprocess
import time
import uuid
from datetime import datetime

from api_smoke import BASE, call, login, wait_for


def ready():
    devices = call("/devices")
    for d in devices:
        if d["connected"] and d["observation"]["state"] == "FAULTED":
            call("/device/reset?device_id=" + d["id"], {"command_id": str(uuid.uuid4())})
    return all(d["connected"] and not d["recovering"] and d["observation"]["state"] in
               ("IDLE", "COMPLETED", "STOPPED") for d in devices)


def request(seconds):
    return {"request_id": str(uuid.uuid4()), "duration_s": seconds, "clocks": [
        {"offset_ms": -750, "drift_ppm": -3000}, {"offset_ms": 1200, "drift_ppm": 5000}]}


def done(group_id):
    data = call("/timing/" + group_id)
    return data if data["status"] not in ("starting", "collecting") else None


def main():
    if os.getenv("LAB_PASSWORD"):
        login(os.environ["LAB_PASSWORD"])
    wait_for(ready, 60)
    payload = request(26)
    group_id = call("/timing", payload)["id"]
    assert call("/timing", payload)["id"] == group_id
    group = wait_for(lambda: done(group_id), 60)
    assert group["status"] == "complete", group
    full = call(f"/timing/{group_id}/evidence.json")
    for member in full["members"]:
        run_id = member["run"]["id"]
        run = wait_for(lambda: (r if (r := call("/runs/" + run_id))["recording"] == "complete" else None), 15)
        assert run["persisted_seq"] == 519
        measured = member["estimate"]
        assert measured["drift_ppm"] is not None, measured
        assert abs(measured["drift_ppm"] - member["injected"]["drift_ppm"]) < max(150, measured["drift_uncertainty_ppm"])
        assert len(member["points"]) == 520
        assert any(p["aligned_utc"] for p in member["points"])
        original = call("/runs/" + run_id + "/samples")
        assert [p["source_utc"] for p in member["points"]] == [p["source_utc"] for p in original]
        assert member["start"]["response"]["transport_timing"]["roundtrip_s"] >= 0
        first = member["points"][0]
        difference = (datetime.fromisoformat(first["source_utc"]) - datetime.fromisoformat(first["received_utc"])).total_seconds()
        assert abs(difference * 1000 - member["injected"]["offset_ms"]) < 500
    assert full["members"][0]["run"]["boot_id"] != full["members"][1]["run"]["boot_id"]
    wait_for(ready)
    stop_id = call("/timing", request(30))["id"]
    wait_for(lambda: call("/timing/" + stop_id)["status"] == "collecting")
    call(f"/timing/{stop_id}/stop", {})
    stopped = wait_for(lambda: done(stop_id))
    assert stopped["status"] == "partial"
    for member in stopped["members"]:
        assert member["start"]["stop_result"]["status"]["state"] == "STOPPED"
    if BASE == "http://127.0.0.1:8000":
        wait_for(ready)
        subprocess.run(["docker", "compose", "stop", "instrument-2"], check=True)
        try:
            wait_for(lambda: not call("/devices")[1]["connected"])
            partial_id = call("/timing", request(10))["id"]
            partial = wait_for(lambda: done(partial_id))
            assert partial["status"] == "partial"
            a, b = partial["members"]
            assert a["start"]["outcome"] == "accepted"
            assert a["start"]["stop_result"]["status"]["state"] == "STOPPED"
            assert b["start"]["outcome"] == "unconfirmed"
        finally:
            subprocess.run(["docker", "compose", "start", "instrument-2"], check=True)
        wait_for(ready, 30)
    print("PASS: distinct C++ boots, 1040 samples, measured clock drift/alignment, immutable originals,")
    print("      idempotent group Start, independent command evidence, Stop and partial-start compensation.")
    print("Timing comparison:", group_id)


if __name__ == "__main__":
    main()
