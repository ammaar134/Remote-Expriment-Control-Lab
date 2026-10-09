"""Real TCP contract checks. Run with the API stopped and instrument service running."""
import json
import os
import socket
import time
import uuid

HOST = os.getenv("INSTRUMENT_HOST", "instrument")


def uid():
    return str(uuid.uuid4())


class Peer:
    def __init__(self, port):
        self.socket = socket.create_connection((HOST, port), timeout=3)
        self.socket.settimeout(3)
        self.file = self.socket.makefile("rb")
        self.boot = ""

    def request(self, kind, **fields):
        return {"v": 1, "type": kind, "instrument_id": "sim-01",
                "boot_id": self.boot, "request_id": uid(), **fields}

    def send(self, request):
        self.socket.sendall(json.dumps(request).encode() + b"\n")
        return self.read()

    def read(self):
        line = self.file.readline(65537)
        assert line and line.endswith(b"\n") and len(line) <= 65536, "Invalid frame"
        return json.loads(line)

    def call(self, kind, **fields):
        return self.send(self.request(kind, **fields))

    def close(self):
        self.file.close()
        self.socket.close()


def until(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    raise AssertionError("Condition deadline expired")


def main():
    control = Peer(9000)
    hello = control.request("handshake")
    encoded = json.dumps(hello).encode() + b"\n"
    control.socket.sendall(encoded[:13])
    control.socket.sendall(encoded[13:])
    response = control.read()
    assert response["ok"] and response["request_id"] == hello["request_id"]
    control.boot = response["boot_id"]
    # A previous test can leave a fault; acknowledge it explicitly.
    if response["status"]["state"] == "FAULTED":
        assert control.call("reset", command_id=uid())["ok"]

    data = Peer(9001)
    data.boot = control.boot
    assert data.call("subscribe")["ok"]
    first, second = control.request("status"), control.request("heartbeat")
    control.socket.sendall((json.dumps(first) + "\n" + json.dumps(second) + "\n").encode())
    assert control.read()["request_id"] == first["request_id"]
    assert control.read()["request_id"] == second["request_id"]
    invalid = control.request("status"); invalid["v"] = 999
    assert control.send(invalid)["error"]["code"] == "VERSION_UNSUPPORTED"

    run = uid()
    recipe = {"sample_rate_hz": 50, "seed": 7, "steps": [{"setpoint": 0.8, "duration_ms": 100}]}
    start = control.request("start", command_id=uid(), run_id=run, recipe=recipe)
    applied = control.send(start)
    assert applied["ok"] and applied["applied"]
    assert control.send(start) == applied
    conflicting = {**start, "recipe": {**recipe, "seed": 8}}
    assert control.send(conflicting)["error"]["code"] == "COMMAND_CONFLICT"
    points = [data.read()["samples"][0] for _ in range(5)]
    assert [point["seq"] for point in points] == list(range(5))
    state = until(lambda: r if (r := control.call("status")["status"])["state"] == "COMPLETED" else False)
    assert state["final_seq"] == 4 and state["output"] == 0
    assert control.send(start) == applied  # Must not execute the recipe a second time.
    assert control.call("status")["status"]["state"] == "COMPLETED"
    assert control.call("stop", run_id=run, command_id=uid())["status"]["state"] == "COMPLETED"

    second_run = uid()
    recipe["steps"][0]["duration_ms"] = 2000
    assert control.call("start", command_id=uid(), run_id=second_run, recipe=recipe)["ok"]
    assert control.call("stop", command_id=uid(), run_id=run)["error"]["code"] == "STALE_RUN"
    data.read()
    stopped = control.call("stop", command_id=uid(), run_id=second_run)
    assert stopped["status"]["state"] == "STOPPED" and stopped["status"]["output"] == 0
    assert stopped["status"]["final_seq"] >= 0
    assert control.call("stop", command_id=uid(), run_id=second_run)["status"]["state"] == "STOPPED"

    # A lost telemetry connection faults the engine independently of Python.
    third_run = uid()
    assert control.call("start", command_id=uid(), run_id=third_run, recipe=recipe)["ok"]
    data.close()
    fault = until(lambda: r if (r := control.call("status")["status"])["state"] == "FAULTED" else False)
    assert fault["output"] == 0
    assert control.call("reset", command_id=uid())["ok"]
    # The parser rejects an oversized unterminated frame.
    control.socket.sendall(b"x" * 65537)
    try:
        assert control.file.read(1) == b""
    except ConnectionResetError:
        pass
    control.close()
    print("PASS: fragmented/coalesced frames, version rejection, real samples, idempotent Start,")
    print("      conflicting IDs, stale/repeated Stop, confirmed zero output, telemetry loss, frame limit.")


if __name__ == "__main__":
    main()
