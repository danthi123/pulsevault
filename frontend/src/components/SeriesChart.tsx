import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { SeriesPoint } from "../api";

interface Props {
  points: SeriesPoint[];
  color: string;
  kind?: "area" | "line" | "bar";
  unit?: string;
  height?: number;
  domain?: [number | "auto", number | "auto"];
}

const hhmm = (ms: number) =>
  new Date(ms).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

// Insert null breaks where consecutive samples are far apart, so lines/areas
// don't draw a straight interpolation across a data gap (e.g. offline periods).
// Threshold is adaptive: 3x the typical (median) spacing, floored at 6 minutes.
function withGaps<T extends { ms: number; v: number | null }>(pts: T[]): T[] {
  if (pts.length < 3) return pts;
  const deltas = pts.slice(1).map((p, i) => p.ms - pts[i].ms).sort((a, b) => a - b);
  const median = deltas[Math.floor(deltas.length / 2)] || 0;
  const threshold = Math.max(6 * 60 * 1000, median * 3);
  const out: T[] = [];
  for (let i = 0; i < pts.length; i++) {
    if (i > 0 && pts[i].ms - pts[i - 1].ms > threshold) {
      out.push({ ms: pts[i - 1].ms + 1, v: null } as T);  // break the segment
    }
    out.push(pts[i]);
  }
  return out;
}

export default function SeriesChart({ points, color, kind = "area", unit = "", height = 240, domain }: Props) {
  if (!points.length) return <div className="spinner">No data for this day.</div>;
  const raw = points.map((p) => ({ ms: Date.parse(p.t), v: p.v as number | null }));
  // Bars are discrete, so gaps don't need breaking; lines/areas do.
  const data = kind === "bar" ? raw : withGaps(raw);
  const common = (
    <>
      <CartesianGrid stroke="#263543" vertical={false} />
      <XAxis
        dataKey="ms" type="number" scale="time"
        domain={["dataMin", "dataMax"]} tickFormatter={hhmm}
        stroke="#8ba0b3" fontSize={11} minTickGap={40}
      />
      <YAxis stroke="#8ba0b3" fontSize={11} width={34} domain={domain ?? ["auto", "auto"]} />
      <Tooltip
        contentStyle={{ background: "#17212b", border: "1px solid #263543", borderRadius: 10, color: "#e6edf3" }}
        labelFormatter={(ms) => hhmm(Number(ms))}
        formatter={(v: number) => [`${v}${unit}`, ""]}
      />
    </>
  );
  return (
    <ResponsiveContainer width="100%" height={height}>
      {kind === "bar" ? (
        <BarChart data={data}>{common}<Bar dataKey="v" fill={color} radius={[3, 3, 0, 0]} /></BarChart>
      ) : kind === "line" ? (
        <LineChart data={data}>{common}<Line dataKey="v" stroke={color} dot={false} strokeWidth={2} connectNulls={false} /></LineChart>
      ) : (
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`g-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.5} />
              <stop offset="100%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          {common}
          <Area dataKey="v" stroke={color} fill={`url(#g-${color})`} strokeWidth={2} connectNulls={false} />
        </AreaChart>
      )}
    </ResponsiveContainer>
  );
}
