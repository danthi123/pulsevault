import { useState } from "react";
import { useAuth } from "../auth";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await login(username, password); }
    catch (e: any) { setErr(e.message || "Login failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="center-screen">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand" style={{ padding: "0 0 16px" }}>Pulse<span style={{ color: "var(--accent)" }}>Vault</span></div>
        {err && <div className="toast err">{err}</div>}
        <label className="field">Username</label>
        <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
        <label className="field">Password</label>
        <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        <button className="btn" style={{ width: "100%", marginTop: 6 }} disabled={busy}>Sign in</button>
      </form>
    </div>
  );
}
