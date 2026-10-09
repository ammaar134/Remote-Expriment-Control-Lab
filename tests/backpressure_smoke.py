"""Check bounded output and Stop on the independent control connection."""
import socket
import time
from protocol_smoke import Peer, uid, until


def main():
    control = Peer(9000)
    hello = control.call("handshake")
    control.boot = hello["boot_id"]
    if hello["status"]["state"] == "FAULTED":
        assert control.call("reset", command_id=uid())["ok"]
    data = Peer(9001)
    data.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
    data.boot = control.boot
    assert data.call("subscribe")["ok"]
    recipe = {"sample_rate_hz": 100, "seed": 9,
              "steps": [{"setpoint": 0.7, "duration_ms": 60000}]}
    run = uid()
    assert control.call("start", command_id=uid(), run_id=run, recipe=recipe)["ok"]

    def backlog():
        status = control.call("status")["status"]
        assert status["state"] == "RUNNING", status
        return status if status["queued_frames"] >= 8 else None

    before = until(backlog, timeout=10)
    started = time.monotonic()
    stopped = control.call("stop", command_id=uid(), run_id=run)["status"]
    assert time.monotonic() - started < 1, "Stop stalled behind telemetry"
    assert stopped["state"] == "STOPPED" and stopped["output"] == 0
    assert stopped["final_seq"] >= before["final_seq"]
    data.close()

    until(lambda: not control.call("status")["status"]["telemetry_ready"])
    data = Peer(9001)
    data.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
    data.boot = control.boot
    assert data.call("subscribe")["ok"]
    assert control.call("start", command_id=uid(), run_id=uid(), recipe=recipe)["ok"]

    def overflow():
        status = control.call("status")["status"]
        assert status["queued_frames"] <= 128
        return status if status["state"] == "FAULTED" else None

    fault = until(overflow, timeout=12)
    assert fault["output"] == 0
    assert "telemetry" in fault["reason"]
    data.close()
    assert control.call("reset", command_id=uid())["ok"]
    control.close()
    print("PASS: Stop bypasses a real telemetry backlog; overflow faults with zero output; queue <=128.")


if __name__ == "__main__":
    main()
