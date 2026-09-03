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

export default function SeriesChart({ points, color, kind = "area", unit = "", height = 240, domain }: Props) {
  if (!points.length) return <div className="spinner">No data for this day.</div>;
  const data = points.map((p) => ({ ms: Date.parse(p.t), v: p.v }));
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
        <LineChart data={data}>{common}<Line dataKey="v" stroke={color} dot={false} strokeWidth={2} /></LineChart>
      ) : (
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`g-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.5} />
              <stop offset="100%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          {common}
          <Area dataKey="v" stroke={color} fill={`url(#g-${color})`} strokeWidth={2} />
        </AreaChart>
      )}
    </ResponsiveContainer>
  );
}
