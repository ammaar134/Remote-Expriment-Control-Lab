"""Real saved-version acquisition, then exports/replay with the engine stopped."""

import csv
import io
import json
import subprocess
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

from api_smoke import BASE, call, ready, terminal, wait_for


def main():
    if urlsplit(BASE).hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit(
            "Run this Compose restart check only against the local test application"
        )
    wait_for(ready)
    recipe = {
        "sample_rate_hz": 100,
        "seed": 31,
        "steps": [{"setpoint": 0.7, "duration_ms": 2000}],
    }
    draft = {
        "request_id": str(uuid.uuid4()),
        "name": "=Synthetic export, study",
        "recipe": recipe,
        "alpha": 0.2,
    }
    first = call("/recipes", draft)
    assert call("/recipes", draft) == first
    second = call(
        "/recipes",
        {
            **draft,
            "request_id": str(uuid.uuid4()),
            "parent_id": first["id"],
            "alpha": 0.3,
        },
    )
    request = {
        "command_id": str(uuid.uuid4()),
        "recipe_version_id": second["id"],
        "name": draft["name"],
        "recipe": recipe,
        "alpha": 0.3,
    }
    try:
        call("/runs", {**request, "alpha": 0.4})
        raise AssertionError("Mutated saved version was accepted")
    except urllib.error.HTTPError as error:
        assert error.code == 409
    run_id = call("/runs", request)["run_id"]
    wait_for(lambda: terminal(run_id))
    prefix = "/runs/" + run_id
    detail = call(prefix)
    assert detail["recipe_id"] == second["id"]
    assert detail["snapshot"]["recipe_version"]["revision"] == 2
    assert call("/recipes/" + first["id"])["alpha"] == 0.2
    before = call(prefix + "/metadata.json")
    subprocess.run(
        ["docker", "compose", "stop", "instrument"], check=True, capture_output=True
    )
    try:
        wait_for(lambda: not call("/device")["connected"])
        playback = call(prefix + "/replay")
        assert playback["mode"] == "saved-observations"
        assert len(playback["samples"]) == 200
        assert len(call(prefix + "/chart?max_points=50")["points"]) <= 50
        assert call(prefix + "/summary")["sample_count"] == 200
        with urllib.request.urlopen(
            BASE + "/api" + prefix + "/export.csv", timeout=5
        ) as response:
            rows = list(csv.DictReader(io.StringIO(response.read().decode())))
        assert len(rows) == 200 and rows[0]["run_name"] == "'" + draft["name"]
        assert float(rows[-1]["response_raw_au"]) == playback["samples"][-1]["response"]
        assert call(prefix + "/metadata.json")["commands"] == before["commands"]
        assert call(prefix)["snapshot"] == detail["snapshot"]
        print(
            json.dumps(
                {
                    "review_smoke": "passed",
                    "full_samples": 200,
                    "engine_offline_replay": True,
                    "recipe_revision": 2,
                }
            )
        )
    finally:
        subprocess.run(
            ["docker", "compose", "start", "instrument"],
            check=True,
            capture_output=True,
        )
        wait_for(ready)


if __name__ == "__main__":
    main()
