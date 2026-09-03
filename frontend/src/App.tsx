import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import MetricPage from "./pages/MetricPage";
import Sleep from "./pages/Sleep";
import Steps from "./pages/Steps";
import Trends from "./pages/Trends";
import Workouts from "./pages/Workouts";
import WorkoutDetail from "./pages/WorkoutDetail";
import Hrv from "./pages/Hrv";
import Settings from "./pages/Settings";

function Gate() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen muted">Loading…</div>;
  if (!user) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/heart" element={
          <MetricPage metric="heart_rate" title="Heart Rate" color="#ff7043" unit=" bpm" kind="line" />} />
        <Route path="/sleep" element={<Sleep />} />
        <Route path="/steps" element={<Steps />} />
        <Route path="/stress" element={
          <MetricPage metric="stress" title="Stress" color="#ab47bc" domain={[0, 100]} dropNegative />} />
        <Route path="/spo2" element={
          <MetricPage metric="spo2" title="SpO₂" color="#42a5f5" unit="%" domain={[80, 100]} kind="line" />} />
        <Route path="/bodybattery" element={
          <MetricPage metric="body_battery" title="Body Battery" color="#66bb6a" domain={[0, 100]} />} />
        <Route path="/hrv" element={<Hrv />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/workouts" element={<Workouts />} />
        <Route path="/workouts/:id" element={<WorkoutDetail />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Gate />
      </BrowserRouter>
    </AuthProvider>
  );
}
