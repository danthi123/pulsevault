import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { MapContainer, Polyline, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, WorkoutRow } from "../api";
import { fmtDistance, fmtDuration, fmtPace } from "../format";
import SeriesChart from "../components/SeriesChart";

interface Detail {
  workout: WorkoutRow;
  track: { lat: number; lon: number }[];
  records: { t: string; hr: number | null; speed: number | null; altitude: number | null }[];
}

export default function WorkoutDetail() {
  const { id } = useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["workout", id],
    queryFn: () => api.get<Detail>(`/api/workouts/${id}`),
  });

  if (isLoading) return <div className="spinner">Loading…</div>;
  if (!data) return <div className="card">Not found. <Link to="/workouts">Back</Link></div>;
  const w = data.workout;
  const line = data.track.map((p) => [p.lat, p.lon]) as [number, number][];
  const center = line.length ? line[Math.floor(line.length / 2)] : null;
  const hrPts = data.records.filter((r) => r.hr != null).map((r) => ({ t: r.t, v: r.hr as number }));
  const altPts = data.records.filter((r) => r.altitude != null).map((r) => ({ t: r.t, v: Math.round(r.altitude as number) }));

  return (
    <>
      <Link to="/workouts" className="muted">‹ Workouts</Link>
      <div className="page-title">{w.name || w.activity_type || "Activity"}</div>
      <div className="tiles">
        <Tile label="Distance" value={fmtDistance(w.distance_m)} />
        <Tile label="Duration" value={fmtDuration(w.duration_s)} />
        <Tile label="Avg pace" value={fmtPace(w.avg_speed)} />
        <Tile label="Avg HR" value={w.avg_hr ? `${w.avg_hr} bpm` : "—"} />
        <Tile label="Max HR" value={w.max_hr ? `${w.max_hr} bpm` : "—"} />
        <Tile label="Calories" value={w.calories ?? "—"} />
        <Tile label="Ascent" value={w.ascent_m != null ? `${Math.round(w.ascent_m)} m` : "—"} />
        <Tile label="Source" value={w.source === "fit_upload" ? "FIT" : "Garmin"} />
      </div>

      {center && line.length > 1 && (
        <div className="card">
          <h3>Route</h3>
          <div className="map">
            <MapContainer center={center} zoom={14} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
              <TileLayer attribution='&copy; OpenStreetMap'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Polyline positions={line} pathOptions={{ color: "#4fc3f7", weight: 4 }} />
            </MapContainer>
          </div>
        </div>
      )}

      {hrPts.length > 0 && (
        <div className="card"><h3>Heart rate</h3>
          <SeriesChart points={hrPts} color="#ff7043" unit=" bpm" kind="line" /></div>
      )}
      {altPts.length > 0 && (
        <div className="card"><h3>Elevation</h3>
          <SeriesChart points={altPts} color="#8d6e63" unit=" m" /></div>
      )}
    </>
  );
}

function Tile({ label, value }: { label: string; value: any }) {
  return <div className="tile"><div className="label">{label}</div><div className="value" style={{ fontSize: 20 }}>{value}</div></div>;
}
