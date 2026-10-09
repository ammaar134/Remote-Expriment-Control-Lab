"""Test the cloud image, access boundary, persisted runs and rolling owner handoff.

Uses an isolated, disposable PostgreSQL container. Never touches Compose history.
Run after: docker build --target hosted -f backend/Dockerfile -t experiment-lab-hosted .
"""

import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import api_smoke


def docker(*args, env=None):
    result = subprocess.run(["docker", *args], env=env, capture_output=True, text=True)
    if result.returncode:
        # Arguments/env can contain credentials; do not echo them on failure.
        raise RuntimeError("Docker operation failed: " + result.stderr[-2000:])
    return result.stdout.strip()


def eventually(check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (urllib.error.URLError, ConnectionError, RuntimeError):
            pass
        time.sleep(0.25)
    raise AssertionError("Hosted readiness deadline expired")


def main():
    tag = "lab-hosted-test-" + uuid.uuid4().hex[:10]
    database = tag + "-db"
    first, second = tag + "-a", tag + "-b"
    containers = []
    origin = "https://lab.example.com"
    password = secrets.token_urlsafe(32)
    db_password = secrets.token_hex(24)
    environment = {
        **os.environ,
        "POSTGRES_PASSWORD": db_password,
        "LAB_PASSWORD": password,
        "DATABASE_URL": f"postgresql://lab:{db_password}@database:5432/lab",
    }
    docker("network", "create", tag)
    try:
        docker(
            "run",
            "-d",
            "--name",
            database,
            "--network",
            tag,
            "--network-alias",
            "database",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            "POSTGRES_USER=lab",
            "--env",
            "POSTGRES_DB=lab",
            "postgres:17-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826",
            "postgres",
            "-c",
            "idle_session_timeout=45s",
            env=environment,
        )
        containers.append(database)
        eventually(lambda: "accepting connections" in docker("exec", database, "pg_isready", "-U", "lab"))

        def start(name):
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--network",
                tag,
                "--publish",
                "127.0.0.1::8000",
                "--env",
                "LAB_MODE=hosted",
                "--env",
                f"LAB_PUBLIC_ORIGIN={origin}",
                "--env",
                "LAB_PASSWORD",
                "--env",
                "DATABASE_URL",
                "experiment-lab-hosted",
                env=environment,
            )
            containers.append(name)
            address = docker("port", name, "8000/tcp").splitlines()[0]
            return "http://" + address

        def request(base, path, headers=None):
            request = urllib.request.Request(base + path, headers=headers or {})
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.read()

        base = start(first)
        eventually(lambda: request(base, "/healthz")[0] == 200)
        api_smoke.BASE = base
        api_smoke.HEADERS = {
            "Authorization": "Basic " + api_smoke.base64.b64encode(f"operator:{password}".encode()).decode(),
            "Origin": origin,
            "Host": "lab.example.com",
            "X-Forwarded-Proto": "https",
        }
        edge = {"Host": "lab.example.com", "X-Forwarded-Proto": "https"}
        for path in ("/", "/api/runs", "/api/health", "/docs"):
            assert request(base, path, edge)[0] == 401
        assert request(base, "/api/runs", {"Host": "lab.example.com"})[0] == 403
        assert request(base, "/", api_smoke.HEADERS)[0] == 200
        eventually(lambda: api_smoke.call("/health")["instrument_connected"])
        idle_boot = api_smoke.call("/device")["boot_id"]
        # No API/database traffic for longer than the server's idle-session
        # timeout. This reproduces serverless suspension without a five-minute
        # cloud test: the internal heartbeat must preserve the owner session.
        print("Checking an idle hosted session beyond PostgreSQL's 45-second timeout...", flush=True)
        time.sleep(50)
        assert api_smoke.call("/health")["database"] == "ready"
        assert api_smoke.call("/device")["boot_id"] == idle_boot
        assert docker("inspect", "--format", "{{.State.Running}}", first) == "true"
        print("PASS: idle database session remains ready without a container restart.", flush=True)
        api_smoke.main()
        saved = api_smoke.call("/runs")
        assert len(saved) == 2
        # C++ listens on loopback only, and does not inherit database/login secrets.
        docker(
            "exec",
            first,
            "python",
            "-c",
            "import socket; host=socket.gethostbyname(socket.gethostname()); "
            "assert all(socket.socket().connect_ex((host, port)) != 0 for port in (9000,9001))",
        )
        assert (
            docker(
                "exec",
                first,
                "python",
                "-c",
                "import pathlib; p=next(p for p in pathlib.Path('/proc').glob('[0-9]*/cmdline') "
                "if p.read_bytes().startswith(b'/usr/local/bin/instrument')); "
                "v=(p.parent/'environ').read_bytes(); "
                "assert b'DATABASE_URL' not in v and b'LAB_PASSWORD' not in v; print('isolated')",
            )
            == "isolated"
        )

        replacement = start(second)
        eventually(lambda: request(replacement, "/healthz")[0] == 200)
        assert request(replacement, "/api/runs", api_smoke.HEADERS)[0] == 503
        assert request(base, "/api/runs", api_smoke.HEADERS)[0] == 200
        docker("stop", "--time", "15", first)
        assert docker("inspect", "--format", "{{.State.ExitCode}}", first) == "0"
        api_smoke.BASE = replacement
        eventually(lambda: api_smoke.call("/health")["instrument_connected"])
        assert api_smoke.call("/runs") == saved, "Redeploy changed saved history"
        api_smoke.main()
        assert len(api_smoke.call("/runs")) == 4
        preserved = api_smoke.call("/runs")
        # A broken owner connection must exit the whole hosted service instead
        # of leaving a signed-in UI attached to a permanently unusable database.
        assert docker(
            "exec",
            database,
            "psql",
            "-U",
            "lab",
            "-d",
            "lab",
            "-Atc",
            "SELECT pg_terminate_backend(pid) FROM pg_locks "
            "WHERE locktype='advisory' AND objid=134001",
        ) == "t"
        eventually(
            lambda: docker("inspect", "--format", "{{.State.Running}}", second) == "false", 35
        )
        assert docker("inspect", "--format", "{{.State.ExitCode}}", second) == "1"
        docker("start", second)
        replacement = "http://" + docker("port", second, "8000/tcp").splitlines()[0]
        api_smoke.BASE = replacement
        eventually(lambda: request(replacement, "/healthz")[0] == 200)
        eventually(lambda: api_smoke.call("/health")["instrument_connected"])
        assert api_smoke.call("/runs") == preserved, "Database-session restart changed saved history"
        print(
            "PASS: lost database ownership shuts down the service; a fresh boot preserves history.",
            flush=True,
        )
        # A child failure exits the whole service; the provider owns container restart.
        docker(
            "exec",
            second,
            "python",
            "-c",
            "import os,pathlib,signal; p=next(p for p in pathlib.Path('/proc').glob('[0-9]*/cmdline') "
            "if p.read_bytes().startswith(b'/usr/local/bin/instrument')); "
            "os.kill(int(p.parent.name),signal.SIGKILL)",
        )
        eventually(lambda: docker("inspect", "--format", "{{.State.Running}}", second) == "false")
        assert docker("inspect", "--format", "{{.State.ExitCode}}", second) == "1"
        print("PASS: authenticated cloud image, HTTP/origin guards, private C++ ports, two real runs,")
        print("      idle session renewal, owner-loss shutdown, exclusive owner handoff,")
        print("      persistent review after replacement, child failure shutdown.")
    finally:
        for container in reversed(containers):
            docker("rm", "--force", "--volumes", container)
        docker("network", "rm", tag)


if __name__ == "__main__":
    main()
