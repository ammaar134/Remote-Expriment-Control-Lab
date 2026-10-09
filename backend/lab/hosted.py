"""Run the two existing processes in one free container, with coupled lifetimes."""

import asyncio
import os
import signal
import sys

from .security import AccessSettings


async def main() -> int:
    settings = AccessSettings.from_environment()
    if settings.mode != "hosted":
        raise RuntimeError("The cloud container requires LAB_MODE=hosted")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    processes: list[asyncio.subprocess.Process] = []
    watchers: list[asyncio.Task] = []
    try:
        processes.append(
            await asyncio.create_subprocess_exec(
                "/usr/local/bin/instrument",
                env={"INSTRUMENT_BIND_ADDRESS": "127.0.0.1", "INSTRUMENT_ID": "sim-01"},
            )
        )
        processes.append(
            await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "uvicorn",
                "lab.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                os.getenv("PORT", "8000"),
                "--workers",
                "1",
                "--limit-concurrency",
                "64",
                "--timeout-keep-alive",
                "5",
                "--timeout-graceful-shutdown",
                "8",
                "--proxy-headers",
                "--forwarded-allow-ips",
                "*",
                env={**os.environ, "INSTRUMENT_HOST": "127.0.0.1"},
            )
        )
        watchers = [asyncio.create_task(p.wait()) for p in processes]
        watchers.append(asyncio.create_task(stop.wait()))
        await asyncio.wait(watchers, return_when=asyncio.FIRST_COMPLETED)
        return 0 if stop.is_set() else 1
    finally:
        # No child is silently restarted: a new boot must reconcile saved evidence.
        for process in reversed(processes):
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
        try:
            await asyncio.wait_for(asyncio.gather(*(p.wait() for p in processes)), 10)
        except TimeoutError:
            for process in processes:
                if process.returncode is None:
                    process.kill()
            await asyncio.gather(*(p.wait() for p in processes))
        for watcher in watchers:
            watcher.cancel()
        await asyncio.gather(*watchers, return_exceptions=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
