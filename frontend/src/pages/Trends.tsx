import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api, DailyRow } from "../api";

const RANGES = [
  { label: "7d", days: 7 }, { label: "30d", days: 30 }, { label: "90d", days: 90 },
];

const METRICS: { key: keyof DailyRow; label: string; color: string; kind: "bar" | "line"; xform?: (n: number) => number }[] = [
  { key: "steps", label: "Steps", color: "#66bb6a", kind: "bar" },
  { key: "resting_hr", label: "Resting HR", color: "#ff7043", kind: "line" },
  { key: "avg_stress", label: "Avg stress", color: "#ab47bc", kind: "line" },
  { key: "vo2max", label: "VO₂ max", color: "#4fc3f7", kind: "line" },
];

export default function Trends() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["daily", days],
    queryFn: () => {
      const end = new Date();
      const start = new Date(); start.setDate(start.getDate() - days + 1);
      return api.get<{ days: DailyRow[] }>(
        `/api/daily?start=${start.toISOString().slice(0, 10)}&end=${end.toISOString().slice(0, 10)}`
      );
    },
  });
  const rows = data?.days ?? [];

  return (
    <>
      <div className="page-title">Trends</div>
      <div className="pill-row">
        {RANGES.map((r) => (
          <button key={r.days}
            className={"btn " + (days === r.days ? "" : "secondary")}
            onClick={() => setDays(r.days)}>{r.label}</button>
        ))}
      </div>
      {isLoading ? <div className="spinner">Loading…</div> : !rows.length ? (
        <div className="card"><p className="muted">No daily data yet.</p></div>
      ) : (
        <>
          {METRICS.map((m) => (
            <div className="card" key={m.key as string}>
              <h3>{m.label}</h3>
              <MetricTrend rows={rows} mkey={m.key} color={m.color} kind={m.kind} />
            </div>
          ))}
        </>
      )}
    </>
  );
}

function fmtDay(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function MetricTrend({ rows, mkey, color, kind }: { rows: DailyRow[]; mkey: keyof DailyRow; color: string; kind: "bar" | "line" }) {
  const data = rows.map((r) => ({ day: fmtDay(r.day), v: r[mkey] as number | null }));
  const axis = (
    <>
      <CartesianGrid stroke="#263543" vertical={false} />
      <XAxis dataKey="day" stroke="#8ba0b3" fontSize={11} minTickGap={24} />
      <YAxis stroke="#8ba0b3" fontSize={11} width={38} domain={["auto", "auto"]} />
      <Tooltip contentStyle={{ background: "#17212b", border: "1px solid #263543", borderRadius: 10 }} />
    </>
  );
  return (
    <ResponsiveContainer width="100%" height={200}>
      {kind === "bar"
        ? <BarChart data={data}>{axis}<Bar dataKey="v" fill={color} radius={[3, 3, 0, 0]} /></BarChart>
        : <LineChart data={data}>{axis}<Line dataKey="v" stroke={color} dot={false} strokeWidth={2} connectNulls /></LineChart>}
    </ResponsiveContainer>
  );
}
