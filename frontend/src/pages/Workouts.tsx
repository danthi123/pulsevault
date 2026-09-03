import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, WorkoutRow } from "../api";
import { fmtDistance, fmtDuration } from "../format";

const ICON: Record<string, string> = {
  running: "🏃", trail_running: "🏃", treadmill_running: "🏃",
  cycling: "🚴", road_biking: "🚴", mountain_biking: "🚴",
  swimming: "🏊", lap_swimming: "🏊", open_water_swimming: "🏊",
  hiking: "🥾", walking: "🚶", strength_training: "🏋️", cardio: "🤸",
};
const LABEL: Record<string, string> = {
  running: "Run", trail_running: "Trail Run", treadmill_running: "Treadmill Run",
  cycling: "Ride", road_biking: "Road Ride", mountain_biking: "Mountain Bike",
  swimming: "Swim", lap_swimming: "Pool Swim", open_water_swimming: "Open Water Swim",
  hiking: "Hike", walking: "Walk", strength_training: "Strength", cardio: "Cardio",
};
const norm = (t?: string | null) => (t || "").toLowerCase().replace(/^sport\./, "");
const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
function wTitle(w: WorkoutRow): string {
  const t = norm(w.activity_type);
  return w.name || LABEL[t] || (t ? titleCase(t) : "Workout");
}
const wIcon = (w: WorkoutRow) => ICON[norm(w.activity_type)] ?? "🏅";
const wWhen = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export default function Workouts() {
  const { data, isLoading } = useQuery({
    queryKey: ["workouts"],
    queryFn: () => api.get<{ workouts: WorkoutRow[] }>("/api/workouts?limit=60"),
  });
  const rows = data?.workouts ?? [];

  return (
    <>
      <div className="page-title">Workouts</div>
      {isLoading ? <div className="spinner">Loading…</div> : !rows.length ? (
        <div className="card"><p className="muted">No workouts yet. Sync Garmin or upload a FIT file.</p></div>
      ) : (
        <div className="card">
          {rows.map((w) => (
            <Link to={`/workouts/${w.id}`} key={w.id} className="workout-row" style={{ color: "inherit" }}>
              <div>
                <div className="wtype">{wIcon(w)} {wTitle(w)}</div>
                <div className="wsub">{wWhen(w.start)}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div>{fmtDistance(w.distance_m)} · {fmtDuration(w.duration_s)}</div>
                <div className="wsub">
                  {w.avg_hr ? `${w.avg_hr} bpm · ` : ""}<span className="badge">{w.source === "fit_upload" ? "FIT" : "Garmin"}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
