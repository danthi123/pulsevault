import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, SeriesPoint } from "../api";
import { fmtNum, todayISO } from "../format";
import DayNav from "../components/DayNav";
import SeriesChart from "../components/SeriesChart";

export default function Steps() {
  const [day, setDay] = useState(todayISO());
  const { data, isLoading } = useQuery({
    queryKey: ["series", "steps", day],
    queryFn: () => api.get<{ points: SeriesPoint[] }>(`/api/series/steps?day=${day}`),
  });
  const points = data?.points ?? [];
  const total = points.reduce((a, p) => a + p.v, 0);
  const peak = points.length ? Math.max(...points.map((p) => p.v)) : 0;

  return (
    <>
      <div className="page-title">Steps</div>
      <DayNav day={day} setDay={setDay} />
      <div className="tiles" style={{ marginBottom: 16 }}>
        <div className="tile"><div className="label">Total</div><div className="value">{fmtNum(total)}</div></div>
        <div className="tile"><div className="label">Peak / bucket</div><div className="value">{fmtNum(peak)}</div></div>
        <div className="tile"><div className="label">Buckets</div><div className="value">{points.length}</div></div>
      </div>
      <div className="card">
        <h3>Steps through the day</h3>
        {isLoading ? <div className="spinner">Loading…</div>
          : <SeriesChart points={points} color="#66bb6a" kind="bar" unit=" steps" />}
      </div>
    </>
  );
}
