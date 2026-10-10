import { useState } from "react";

// Original projected geometry; visual reference: 21st.dev's Geometric Sphere.
// This illustrates the simulator. It is never used to report instrument state.
export function InstrumentSculpture() {
  const [turn, setTurn] = useState(0.35);
  const project = (x: number, y: number, z: number) => {
    const rotatedX = x * Math.cos(turn) + z * Math.sin(turn);
    const depth = z * Math.cos(turn) - x * Math.sin(turn);
    const rotatedY = y * Math.cos(0.45) - depth * Math.sin(0.45);
    const rotatedZ = y * Math.sin(0.45) + depth * Math.cos(0.45);
    const perspective = 310 / (310 + rotatedZ);
    return `${(180 + rotatedX * perspective).toFixed(2)},${(108 + rotatedY * perspective).toFixed(2)}`;
  };
  const meridians = Array.from({ length: 12 }, (_, ring) =>
    Array.from({ length: 65 }, (_, i) => {
      const a = (i / 64) * Math.PI * 2;
      const b = (ring / 12) * Math.PI;
      return project(
        78 * Math.cos(a) * Math.cos(b),
        78 * Math.sin(a),
        78 * Math.cos(a) * Math.sin(b),
      );
    }).join(" "),
  );
  const parallels = [-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75].map((height) =>
    Array.from({ length: 65 }, (_, i) => {
      const a = (i / 64) * Math.PI * 2;
      const radius = 78 * Math.sqrt(1 - height * height);
      return project(radius * Math.cos(a), height * 78, radius * Math.sin(a));
    }).join(" "),
  );
  return (
    <div
      className="sculpture"
      aria-hidden="true"
      onPointerMove={(event) => {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches)
          return;
        const box = event.currentTarget.getBoundingClientRect();
        setTurn(0.35 + ((event.clientX - box.left) / box.width - 0.5) * 0.8);
      }}
      onPointerLeave={() => setTurn(0.35)}
    >
      <svg viewBox="0 0 360 216" fill="none">
        <ellipse
          cx="180"
          cy="190"
          rx="95"
          ry="7"
          fill="currentColor"
          opacity="0.09"
        />
        <path
          d="M24 108H100M260 108H336M180 6V24M180 190V210"
          stroke="currentColor"
          opacity="0.3"
        />
        {meridians.map((points, i) => (
          <polyline
            key={i}
            points={points}
            stroke="currentColor"
            opacity="0.32"
            strokeWidth="0.7"
          />
        ))}
        {parallels.map((points, i) => (
          <polyline
            key={i}
            points={points}
            stroke="currentColor"
            opacity="0.5"
            strokeWidth="0.8"
          />
        ))}
        <ellipse
          cx="180"
          cy="108"
          rx="129"
          ry="34"
          transform="rotate(-24 180 108)"
          stroke="#eca876"
          strokeWidth="1.5"
        />
        <circle cx="295" cy="56" r="4" fill="#eca876" />
        <circle cx="180" cy="108" r="3" fill="currentColor" />
      </svg>
    </div>
  );
}

export function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      width="20"
      height="20"
      fill="none"
    >
      <path d="M4 10h12M11 5l5 5-5 5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function WaveMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 40 40"
      width="40"
      height="40"
      fill="none"
    >
      <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M5 21h7l5-11 6 20 5-9h7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
