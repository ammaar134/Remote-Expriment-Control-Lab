"""Local-only Phase 2 fault scenarios through real TCP, API and PostgreSQL.

Run with LAB_ENABLE_FAULTS=1 on both Compose services. Never targets hosted URLs.
"""
import subprocess
import time
import uuid

from api_smoke import BASE, call, ready, terminal, wait_for


def start(scenario="normal", duration=4000):
    wait_for(ready, timeout=25)
    request = {
        "command_id": str(uuid.uuid4()), "name": "Reliability: " + scenario,
        "scenario": scenario, "alpha": 0.2,
        "recipe": {"seed": 42, "sample_rate_hz": 50,
                   "steps": [{"setpoint": 0.7, "duration_ms": duration}]},
    }
    return call("/runs", request)["run_id"], request


def verify(run_id, execution, complete=True):
    result = wait_for(lambda: terminal(run_id), timeout=25)
    assert result["execution"] == execution, result
    assert result["recording"] == ("complete" if complete else "partial"), result
    points = call("/runs/" + run_id + "/samples")
    assert [p["seq"] for p in points] == list(range(len(points)))
    assert result["persisted_seq"] == len(points) - 1
    if complete:
        assert result["final_seq"] == len(points) - 1
    for previous, point in zip(points, points[1:]):
        assert abs(point["filtered"] - (0.2 * point["response"] + 0.8 * previous["filtered"])) < 1e-12
    return result, points


def api_returns():
    try:
        return call("/device")["connected"]
    except Exception:
        return False


def main():
    assert BASE == "http://127.0.0.1:8000", "Fault tests only operate local Compose"
    assert call("/device")["faults_enabled"], "Enable the explicit local demo profile"
    lost, request = start("lost_start_ack")
    assert call("/runs", request)["run_id"] == lost
    result, points = verify(lost, "COMPLETED")
    results = [e["detail"]["response"] for e in result["events"] if e["kind"] == "command_result"]
    assert results[0]["attempts"] == 2
    assert len(points) == 200
    print("PASS lost Start response: one run, identical command retry, 200 persisted samples", lost)

    recovered, _ = start("telemetry_reconnect")
    result, recovered_points = verify(recovered, "COMPLETED")
    assert len(recovered_points) == 200
    assert [p["response"] for p in points] == [p["response"] for p in recovered_points]
    assert any(e["kind"] == "telemetry_reconnecting" for e in result["events"])
    print("PASS telemetry interruption: same-boot replay, identical seeded samples and EMA", recovered)

    for scenario in ("controller_disconnect", "database_write_failure"):
        run_id, _ = start(scenario)
        result, _ = verify(run_id, "FAULTED")
        assert any(e["kind"] == "same_boot_reconciled" for e in result["events"])
        assert not any(e["kind"] == "rolled_back_demo" for e in result["events"])
        assert call("/device")["observation"]["output"] == 0
        print("PASS", scenario, "safe fault, no premature ACK, retained samples committed", run_id)

    restarted, _ = start(duration=10000)
    wait_for(lambda: call("/runs/" + restarted)["persisted_seq"] >= 5)
    boot = call("/device")["boot_id"]
    subprocess.run(["docker", "compose", "restart", "lab"], check=True, capture_output=True)
    wait_for(api_returns, timeout=30)
    assert call("/device")["boot_id"] == boot
    verify(restarted, "FAULTED")
    print("PASS API restart: same boot reconciled; experiment not restarted", restarted)

    changed, _ = start(duration=10000)
    wait_for(lambda: call("/runs/" + changed)["persisted_seq"] >= 5)
    before = call("/runs/" + changed + "/samples")
    subprocess.run(["docker", "compose", "restart", "instrument"], check=True, capture_output=True)
    wait_for(lambda: api_returns() and call("/device")["boot_id"] != boot, timeout=30)
    result, after = verify(changed, "UNKNOWN", complete=False)
    assert result["reason"] == "engine_restarted"
    assert after[:len(before)] == before
    assert call("/device")["observation"]["state"] == "IDLE"
    print("PASS engine restart: changed boot, unknown execution, visible partial recording", changed)


if __name__ == "__main__":
    main()
