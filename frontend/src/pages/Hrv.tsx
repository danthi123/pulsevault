import { useQuery } from "@tanstack/react-query";
import {
  Area, AreaChart, CartesianGrid, Line, ComposedChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

interface HrvDay {
  day: string; last_night_avg: number | null;
  baseline_low: number | null; baseline_high: number | null; status: string | null;
}

export default function Hrv() {
  const { data, isLoading } = useQuery({
    queryKey: ["hrv"], queryFn: () => api.get<{ days: HrvDay[] }>("/api/hrv"),
  });
  const rows = data?.days ?? [];
  const latest = rows[rows.length - 1];
  const chart = rows.map((r) => ({
    day: new Date(r.day + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    avg: r.last_night_avg,
    band: r.baseline_low != null && r.baseline_high != null ? [r.baseline_low, r.baseline_high] : null,
  }));

  return (
    <>
      <div className="page-title">HRV</div>
      {isLoading ? <div className="spinner">Loading…</div> : !rows.length ? (
        <div className="card"><p className="muted">No HRV data yet (Garmin records HRV overnight).</p></div>
      ) : (
        <>
          <div className="tiles" style={{ marginBottom: 16 }}>
            <div className="tile"><div className="label">Last night avg</div><div className="value">{latest?.last_night_avg ?? "—"}<small> ms</small></div></div>
            <div className="tile"><div className="label">Status</div><div className="value" style={{ fontSize: 20 }}>{latest?.status ?? "—"}</div></div>
            <div className="tile"><div className="label">Baseline</div><div className="value" style={{ fontSize: 18 }}>
              {latest?.baseline_low != null ? `${latest.baseline_low}–${latest.baseline_high}` : "—"}</div></div>
          </div>
          <div className="card">
            <h3>Overnight HRV vs baseline</h3>
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={chart}>
                <CartesianGrid stroke="#263543" vertical={false} />
                <XAxis dataKey="day" stroke="#8ba0b3" fontSize={11} minTickGap={24} />
                <YAxis stroke="#8ba0b3" fontSize={11} width={38} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#17212b", border: "1px solid #263543", borderRadius: 10 }} />
                <Area dataKey="band" stroke="none" fill="#26c6da" fillOpacity={0.15} />
                <Line dataKey="avg" stroke="#26c6da" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </>
  );
}
