import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Status, StopControl } from "./App";
import type { Device } from "./api";
const running: Device = {
  id: "sim-01",
  name: "Simulator",
  connected: true,
  boot_id: "boot",
  error: "",
  observation_age_s: 0,
  observation: {
    state: "RUNNING",
    run_id: "run",
    final_seq: 4,
    output: 0.5,
    reason: "",
  },
};

describe("truthful execution controls", () => {
  it("keeps completed execution and incomplete data visible together", () => {
    render(<Status state="COMPLETED" recording="partial" />);
    expect(screen.getByText("completed")).toBeVisible();
    expect(screen.getByText("Data: partial")).toBeVisible();
  });
  it("does not allow Stop while disconnected even if the last observation was running", async () => {
    const stop = vi.fn();
    render(
      <StopControl
        device={{ ...running, connected: false }}
        busy={false}
        onStop={stop}
      />,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(stop).not.toHaveBeenCalled();
  });
  it("labels an outstanding request without claiming a stopped state or allowing repeats", async () => {
    const stop = vi.fn();
    const { rerender } = render(
      <StopControl device={running} busy={false} onStop={stop} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Stop experiment/ }),
    );
    expect(stop).toHaveBeenCalledTimes(1);
    rerender(<StopControl device={running} busy={true} onStop={stop} />);
    const button = screen.getByRole("button", { name: /Stop requested/ });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
