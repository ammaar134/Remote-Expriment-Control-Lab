"""An open but silent controller must lose its lease independently of Python."""
import time
from protocol_smoke import Peer, uid, until


def main():
    control = Peer(9000)
    hello = control.call("handshake")
    control.boot = hello["boot_id"]
    if hello["status"]["state"] == "FAULTED":
        assert control.call("reset", command_id=uid())["ok"]
    data = Peer(9001)
    data.boot = control.boot
    assert data.call("subscribe")["ok"]
    run = uid()
    assert control.call("start", command_id=uid(), run_id=run,
                        recipe={"seed": 42, "sample_rate_hz": 10,
                                "steps": [{"setpoint": 0.8, "duration_ms": 10000}]})["ok"]
    # Deliberately no control traffic; the TCP peer stays open.
    time.sleep(5.5)
    replacement = Peer(9000)
    state = replacement.call("handshake")
    assert state["boot_id"] == control.boot
    replacement.boot = state["boot_id"]
    assert state["status"]["state"] == "FAULTED"
    assert state["status"]["reason"] == "controller_lease_expired"
    assert state["status"]["output"] == 0
    assert state["status"]["final_seq"] < 60
    assert replacement.call("reset", command_id=uid())["ok"]
    replacement.close()
    data.close()
    control.close()
    print("PASS: silent open controller loses its five-second lease; output zero, same-boot evidence retained.")


if __name__ == "__main__":
    main()
