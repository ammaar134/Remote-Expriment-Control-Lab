"""Exercise the real API -> C++ -> PostgreSQL path without test doubles."""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

BASE = os.getenv("LAB_URL", "http://127.0.0.1:8000")
HEADERS = {}
if os.getenv("LAB_PASSWORD"):
    HEADERS["Origin"] = os.getenv("LAB_PUBLIC_ORIGIN", BASE)


def login(password, username="operator"):
    request = urllib.request.Request(
        BASE + "/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        assert "www-authenticate" not in response.headers
        HEADERS["Cookie"] = response.headers["Set-Cookie"].split(";", 1)[0]


def call(path, payload=None):
    request = urllib.request.Request(
        BASE + "/api" + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={**HEADERS, **({} if payload is None else {"Content-Type": "application/json"})},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("Condition deadline expired")


def ready():
    device = call("/device")
    if device["connected"] and device["observation"]["state"] == "FAULTED":
        call("/device/reset", {"command_id": str(uuid.uuid4())})
    return device["connected"] and device["observation"]["state"] in ("IDLE", "STOPPED", "COMPLETED")


def terminal(run_id):
    run = call("/runs/" + run_id)
    return run if run["recording"] in ("complete", "partial") else None


def main():
    wait_for(ready)
    command = {
        "command_id": str(uuid.uuid4()), "name": "Baseline response", "alpha": 0.2,
        "recipe": {"seed": 42, "sample_rate_hz": 50, "steps": [
            {"setpoint": 0.2, "duration_ms": 1000}, {"setpoint": 0.8, "duration_ms": 1000},
        ]},
    }
    run_id = call("/runs", command)["run_id"]
    assert call("/runs", command)["run_id"] == run_id, "HTTP retry duplicated the run"
    changed = {**command, "name": "conflicting"}
    try:
        call("/runs", changed)
        raise AssertionError("Conflicting Start was accepted")
    except urllib.error.HTTPError as error:
        assert error.code == 409
    finished = wait_for(lambda: terminal(run_id))
    assert finished["execution"] == "COMPLETED" and finished["recording"] == "complete", finished
    assert finished["final_seq"] == finished["persisted_seq"] == 99
    points = call("/runs/" + run_id + "/samples")
    assert len(points) == 100
    assert [point["seq"] for point in points] == list(range(100))
    assert points[0]["filtered"] == points[0]["response"]
    expected = 0.2 * points[1]["response"] + 0.8 * points[0]["filtered"]
    assert abs(points[1]["filtered"] - expected) < 1e-12
    assert finished["snapshot"]["recipe"] == command["recipe"]
    assert any(event["kind"] == "device_terminal" for event in finished["events"])

    wait_for(ready)
    command["command_id"] = str(uuid.uuid4())
    command["name"] = "Operator stop demonstration"
    command["recipe"]["steps"][0]["duration_ms"] = 10000
    stopped_id = call("/runs", command)["run_id"]
    wait_for(lambda: call("/runs/" + stopped_id)["persisted_seq"] >= 5)
    stop = {"command_id": str(uuid.uuid4())}
    confirmed = call("/runs/" + stopped_id + "/stop", stop)
    assert confirmed["status"]["state"] == "STOPPED"
    assert confirmed["status"]["output"] == 0
    assert call("/runs/" + stopped_id + "/stop", stop) == confirmed
    stopped = wait_for(lambda: terminal(stopped_id))
    assert stopped["execution"] == "STOPPED" and stopped["recording"] == "complete", stopped
    assert stopped["persisted_seq"] == stopped["final_seq"]
    assert len(call("/runs/" + stopped_id + "/samples")) == stopped["final_seq"] + 1
    print("PASS: normal run, 100 ordered durable samples, EMA math, immutable snapshot,")
    print("      duplicate/conflicting HTTP Start, confirmed/repeated Stop and final-sequence drain.")
    print("Complete run:", run_id)
    print("Stopped run:", stopped_id)


if __name__ == "__main__":
    if os.getenv("LAB_PASSWORD"):
        login(os.environ["LAB_PASSWORD"], os.getenv("LAB_USERNAME", "operator"))
    main()
