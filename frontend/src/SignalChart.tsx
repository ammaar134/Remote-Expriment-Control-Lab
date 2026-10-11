import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Sample } from "./api";
import { WaveMark } from "./InstrumentSculpture";
export default function SignalChart({ samples }: { samples: Sample[] }) {
  const display = samples.slice(0, 1200);
  return (
    <div
      className="chart"
      role="img"
      aria-label={
        samples.length
          ? "Raw response, filtered response and reference over logical time"
          : "Chart awaiting recorded samples"
      }
    >
      {samples.length ? (
        <ResponsiveContainer width="100%" height={290} minWidth={0}>
          <LineChart
            data={display}
            margin={{ top: 12, right: 16, left: 0, bottom: 4 }}
          >
            <CartesianGrid
              strokeDasharray="3 5"
              vertical={false}
              stroke="#d9dce3"
            />
            <XAxis
              dataKey="logical_s"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => Number(Number(v).toFixed(2)) + "s"}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[-0.1, 1.1]}
              width={42}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              labelFormatter={(v) =>
                "Logical time: " + Number(v).toFixed(2) + " s"
              }
            />
            <Legend iconType="plainline" />
            <Line
              dataKey="response"
              name="Raw response (a.u.)"
              stroke="#5e719f"
              dot={false}
              strokeWidth={1}
              isAnimationActive={false}
            />
            <Line
              dataKey="filtered"
              name="EMA (a.u.)"
              stroke="#263e7d"
              dot={false}
              strokeWidth={2.5}
              isAnimationActive={false}
            />
            <Line
              dataKey="reference"
              name="Reference (a.u.)"
              stroke="#b35531"
              dot={false}
              strokeWidth={1.3}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="chart-empty">
          <WaveMark />
          <strong>No recorded samples in this view</strong>
          <p>Measurements appear as acquisition or saved playback advances.</p>
        </div>
      )}
    </div>
  );
}
