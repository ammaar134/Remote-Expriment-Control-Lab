import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ReplayPlayer } from "./ReplayPlayer";
import { recipeKey, type ReplayData } from "./api";
vi.mock("./Chart", () => ({ Chart: () => <div>Saved chart</div> }));
vi.mock("./RunEvidence", () => ({
  RunEvidence: () => <div>Saved evidence</div>,
}));
afterEach(() => vi.useRealTimers());

test("playback pause, speed, seek and restart change only the saved-data cursor", () => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "performance"] });
  const data = {
    duration_s: 4,
    samples: [1, 2, 3, 4].map((value) => ({
      replay_s: value,
      response: value,
      filtered: value,
    })),
    chart: [],
    events: [],
    run: {},
  } as unknown as ReplayData;
  render(<ReplayPlayer data={data} onClose={() => undefined} />);
  fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByLabelText("Replay position")).toHaveTextContent(
    "1.00 / 4.00 s",
  );
  fireEvent.click(screen.getByRole("button", { name: "Pause replay" }));
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByLabelText("Replay position")).toHaveTextContent(
    "1.00 / 4.00 s",
  );
  fireEvent.change(screen.getByLabelText("Playback speed"), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByLabelText("Replay position")).toHaveTextContent(
    "3.00 / 4.00 s",
  );
  fireEvent.change(screen.getByLabelText("Seek replay"), {
    target: { value: "4" },
  });
  expect(screen.getByText("4 / 4 recorded samples shown")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Restart replay" }));
  expect(screen.getByLabelText("Replay position")).toHaveTextContent(
    "0.00 / 4.00 s",
  );
  expect(screen.getByRole("button", { name: "Play replay" })).toBeVisible();
});

test("loading a JSONB recipe does not invent unsaved changes from key order", () => {
  const recipe = {
    sample_rate_hz: 50,
    seed: 7,
    steps: [{ setpoint: 0.5, duration_ms: 1000 }],
  };
  expect(recipeKey(recipe)).toBe(
    recipeKey({
      steps: [{ duration_ms: 1000, setpoint: 0.5 }],
      seed: 7,
      sample_rate_hz: 50,
    }),
  );
});
