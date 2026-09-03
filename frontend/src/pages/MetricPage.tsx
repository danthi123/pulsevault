import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, SeriesPoint } from "../api";
import { todayISO } from "../format";
import DayNav from "../components/DayNav";
import SeriesChart from "../components/SeriesChart";

interface Props {
  metric: string;
  title: string;
  color: string;
  unit?: string;
  kind?: "area" | "line" | "bar";
  domain?: [number | "auto", number | "auto"];
  // stress uses negative sentinel values for "unmeasured"; drop them.
  dropNegative?: boolean;
}

export default function MetricPage({ metric, title, color, unit = "", kind = "area", domain, dropNegative }: Props) {
  const [day, setDay] = useState(todayISO());
  const { data, isLoading } = useQuery({
    queryKey: ["series", metric, day],
    queryFn: () => api.get<{ points: SeriesPoint[] }>(`/api/series/${metric}?day=${day}`),
  });

  let points = data?.points ?? [];
  if (dropNegative) points = points.filter((p) => p.v >= 0);
  const values = points.map((p) => p.v);
  const min = values.length ? Math.min(...values) : null;
  const max = values.length ? Math.max(...values) : null;
  const avg = values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null;

  return (
    <>
      <div className="page-title">{title}</div>
      <DayNav day={day} setDay={setDay} />
      <div className="tiles" style={{ marginBottom: 16 }}>
        <Stat label="Min" value={min} unit={unit} />
        <Stat label="Avg" value={avg} unit={unit} />
        <Stat label="Max" value={max} unit={unit} />
        <Stat label="Readings" value={values.length} />
      </div>
      <div className="card">
        <h3>{title} over the day</h3>
        {isLoading ? <div className="spinner">Loading…</div>
          : <SeriesChart points={points} color={color} unit={unit} kind={kind} domain={domain} />}
      </div>
    </>
  );
}

function Stat({ label, value, unit = "" }: { label: string; value: number | null; unit?: string }) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      <div className="value">{value === null ? "—" : value}<small>{value === null ? "" : unit}</small></div>
    </div>
  );
}
