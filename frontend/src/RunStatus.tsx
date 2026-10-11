import { readable } from "./format";
export function Status({
  state,
  recording,
  finalSeq,
  persistedSeq,
}: {
  state: string;
  recording?: string;
  finalSeq?: number | null;
  persistedSeq?: number;
}) {
  const missing =
    recording === "partial" &&
    typeof finalSeq === "number" &&
    typeof persistedSeq === "number"
      ? Math.max(0, finalSeq - persistedSeq)
      : null;
  return (
    <div className="status-pair">
      <span className={"pill " + state.toLowerCase()}>{readable(state)}</span>
      {recording && (
        <span className={"pill recording-" + recording}>
          Data: {recording === "draining" ? "finalizing" : readable(recording)}
          {missing !== null &&
            missing > 0 &&
            ` · ${missing} ${missing === 1 ? "sample" : "samples"} missing`}
        </span>
      )}
    </div>
  );
}
