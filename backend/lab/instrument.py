import asyncio
import json
import os
from uuid import uuid4

MAX_FRAME = 65_536


async def read_frame(reader: asyncio.StreamReader) -> dict:
    line = await reader.readline()
    if not line or len(line) > MAX_FRAME or not line.endswith(b"\n"):
        raise ConnectionError("Incomplete or oversized instrument frame")
    value = json.loads(line)
    if not isinstance(value, dict) or value.get("v") != 1:
        raise ConnectionError("Invalid instrument envelope")
    return value


class Instrument:
    def __init__(self):
        self.host = os.getenv("INSTRUMENT_HOST", "instrument")
        self.device_id = "sim-01"
        self.boot_id = ""
        self.control_reader: asyncio.StreamReader | None = None
        self.control_writer: asyncio.StreamWriter | None = None
        self.telemetry_reader: asyncio.StreamReader | None = None
        self.telemetry_writer: asyncio.StreamWriter | None = None
        self.lock = asyncio.Lock()
        self.connected = False

    async def connect(self) -> dict:
        self.control_reader, self.control_writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, 9000, limit=MAX_FRAME), 3
        )
        hello = await self.call("handshake")
        self.boot_id = hello["boot_id"]
        telemetry_reader, telemetry_writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, 9001, limit=MAX_FRAME), 3
        )
        self.telemetry_reader, self.telemetry_writer = telemetry_reader, telemetry_writer
        telemetry_writer.write(json.dumps(self.message("subscribe")).encode() + b"\n")
        await telemetry_writer.drain()
        response = await asyncio.wait_for(read_frame(telemetry_reader), 3)
        if not response.get("ok") or response.get("boot_id") != self.boot_id:
            raise ConnectionError("Telemetry handshake rejected")
        self.connected = True
        return hello

    def message(self, kind: str, **fields) -> dict:
        return {
            "v": 1,
            "type": kind,
            "instrument_id": self.device_id,
            "boot_id": self.boot_id,
            "request_id": str(uuid4()),
            **fields,
        }

    async def call(self, kind: str, **fields) -> dict:
        request = self.message(kind, **fields)
        async with self.lock:
            if self.control_writer is None or self.control_reader is None:
                raise ConnectionError("Instrument is disconnected")
            self.control_writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            async with asyncio.timeout(2):
                await self.control_writer.drain()
                response = await read_frame(self.control_reader)
            if response.get("request_id") != request["request_id"]:
                raise ConnectionError("Instrument response correlation mismatch")
            if response.get("instrument_id") != self.device_id:
                raise ConnectionError("Instrument identity mismatch")
            if kind != "handshake" and response.get("boot_id") != self.boot_id:
                raise ConnectionError("Engine restarted")
            return response

    async def close(self) -> None:
        self.connected = False
        for writer in (self.control_writer, self.telemetry_writer):
            if writer:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), 1)
                except (TimeoutError, OSError):
                    pass
        self.control_reader = self.control_writer = None
        self.telemetry_reader = self.telemetry_writer = None
