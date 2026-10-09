import asyncio
import time

from lab.orchestrator import Orchestrator


class Evidence:
    def __init__(self):
        self.updates = []
        self.events = []

    async def execute(self, sql, params=()):
        self.updates.append(params)

    async def event(self, run_id, kind, detail):
        self.events.append((kind, detail))


def test_terminal_execution_does_not_imply_complete_recording():
    async def check():
        evidence = Evidence()
        controller = Orchestrator(evidence)
        controller.active = "run"
        controller.observation = {"state": "COMPLETED", "final_seq": 4, "reason": "recipe_complete"}
        row = {
            "id": "run",
            "persisted_seq": 3,
            "execution": "RUNNING",
            "recording": "recording",
            "final_seq": None,
            "reason": "",
        }
        await controller.observe_terminal(row)
        assert evidence.updates[-1][:3] == ("COMPLETED", "draining", 4)
        assert controller.active == "run"
        row.update(execution="COMPLETED", recording="draining", final_seq=4, reason="recipe_complete")
        controller.drain_deadline = time.monotonic() - 1
        await controller.observe_terminal(row)
        assert evidence.updates[-1][1] == "partial"
        assert "missing_samples" in evidence.updates[-1][3]
        row["persisted_seq"] = 4
        await controller.observe_terminal(row)
        assert evidence.updates[-1][1] == "complete"

    asyncio.run(check())
