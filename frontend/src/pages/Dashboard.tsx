import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, DailyRow, SeriesPoint, SleepRow } from "../api";
import { fmtDistance, fmtDuration, fmtNum, todayISO } from "../format";
import DayNav from "../components/DayNav";
import SeriesChart from "../components/SeriesChart";

interface DashResp {
  day: string;
  summary: DailyRow | null;
  body_battery_now: number | null;
  sleep: SleepRow | null;
}

export default function Dashboard() {
  const [day, setDay] = useState(todayISO());
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", day],
    queryFn: () => api.get<DashResp>(`/api/dashboard?day=${day}`),
  });
  const hr = useQuery({
    queryKey: ["series", "heart_rate", day],
    queryFn: () => api.get<{ points: SeriesPoint[] }>(`/api/series/heart_rate?day=${day}`),
  });

  const s = data?.summary;
  const sleep = data?.sleep;
  const stepPct = s?.steps && s?.steps_goal ? Math.min(100, Math.round((s.steps / s.steps_goal) * 100)) : null;

  return (
    <>
      <div className="page-title">Dashboard</div>
      <DayNav day={day} setDay={setDay} />

      {isLoading ? <div className="spinner">Loading…</div> : !s && !sleep ? (
        <div className="card">
          <p className="muted">No data for this day yet. Connect Garmin and run a sync from{" "}
            <Link to="/settings">Settings</Link>, or upload a FIT file.</p>
        </div>
      ) : (
        <>
          <div className="tiles">
            <Tile label="Steps" value={fmtNum(s?.steps)}
              sub={stepPct !== null ? `${stepPct}% of ${fmtNum(s?.steps_goal)}` : undefined} />
            <Tile label="Resting HR" value={s?.resting_hr ?? "—"} unit=" bpm" />
            <Tile label="Sleep" value={fmtDuration(sleep?.total_s)}
              sub={sleep?.score ? `score ${sleep.score}` : undefined} />
            <Tile label="Body Battery" value={data?.body_battery_now ?? "—"}
              sub={s?.body_battery_low != null ? `${s.body_battery_low}–${s.body_battery_high}` : undefined} />
            <Tile label="Distance" value={fmtDistance(s?.distance_m)} />
            <Tile label="Avg Stress" value={s?.avg_stress ?? "—"} />
            <Tile label="Active" value={fmtDuration(s?.active_seconds)} />
            <Tile label="Intensity min" value={s?.intensity_minutes ?? "—"} />
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>Heart rate</h3>
            {hr.isLoading ? <div className="spinner">Loading…</div>
              : <SeriesChart points={hr.data?.points ?? []} color="#ff7043" unit=" bpm" height={200} />}
          </div>

          {(s?.vo2max || s?.training_status) && (
            <div className="tiles">
              {s?.vo2max ? <Tile label="VO₂ Max" value={Math.round(s.vo2max)} /> : null}
              {s?.training_status ? <Tile label="Training" value={s.training_status} /> : null}
              {s?.floors != null ? <Tile label="Floors" value={s.floors} /> : null}
              {s?.calories != null ? <Tile label="Calories" value={fmtNum(s.calories)} /> : null}
            </div>
          )}
        </>
      )}
    </>
  );
}

function Tile({ label, value, unit = "", sub }: { label: string; value: any; unit?: string; sub?: string }) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      <div className="value">{value}{value !== "—" && unit ? <small>{unit}</small> : null}</div>
      {sub ? <div className="sub">{sub}</div> : null}
    </div>
  );
}
