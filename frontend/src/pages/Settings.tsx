import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";

interface GStatus { authenticated: boolean; display_name?: string; reason?: string }

export default function Settings() {
  const qc = useQueryClient();
  const { logout } = useAuth();
  const status = useQuery({ queryKey: ["garmin-status"], queryFn: () => api.get<GStatus>("/api/garmin/status") });
  const syncStatus = useQuery({
    queryKey: ["sync-status"], queryFn: () => api.get<any>("/api/sync/status"), refetchInterval: 4000,
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => { status.refetch(); qc.invalidateQueries(); };

  async function doLogin() {
    setBusy(true); setToast(null);
    try {
      const r = await api.post<{ status: string; reason?: string }>("/api/garmin/login", { email, password });
      if (r.status === "needs_mfa") { setNeedMfa(true); setToast({ ok: true, msg: "Enter the code Garmin just sent you." }); }
      else if (r.status === "ok") { setToast({ ok: true, msg: "Connected to Garmin." }); setPassword(""); refresh(); }
      else { setToast({ ok: false, msg: r.reason || "Garmin login failed." }); }
    } catch (e: any) { setToast({ ok: false, msg: e.message }); } finally { setBusy(false); }
  }
  async function doMfa() {
    setBusy(true);
    try {
      const r = await api.post<{ status: string; reason?: string }>("/api/garmin/mfa", { code: mfa });
      if (r.status === "ok") {
        setToast({ ok: true, msg: "Connected to Garmin." });
        setNeedMfa(false); setPassword(""); setMfa(""); refresh();
      } else { setToast({ ok: false, msg: r.reason || "MFA verification failed." }); }
    } catch (e: any) { setToast({ ok: false, msg: e.message }); } finally { setBusy(false); }
  }
  async function sync(days?: number) {
    setBusy(true); setToast(null);
    try {
      await api.post("/api/sync" + (days ? `?days=${days}` : ""));
      setToast({ ok: true, msg: "Sync started / completed." }); syncStatus.refetch();
    } catch (e: any) { setToast({ ok: false, msg: e.message }); } finally { setBusy(false); }
  }
  async function disconnectGarmin() {
    await api.post("/api/garmin/logout"); refresh();
  }

  const gs = status.data;

  return (
    <>
      <div className="page-title">Settings</div>
      {toast && <div className={"toast " + (toast.ok ? "ok" : "err")}>{toast.msg}</div>}

      <div className="card">
        <h3>Garmin Connect</h3>
        {gs?.authenticated ? (
          <>
            <p>Connected{gs.display_name ? ` as ${gs.display_name}` : ""}. ✅</p>
            <div className="pill-row">
              <button className="btn" disabled={busy} onClick={() => sync(2)}>Sync now</button>
              <button className="btn secondary" disabled={busy} onClick={() => sync(30)}>Backfill 30 days</button>
              <button className="btn danger" disabled={busy} onClick={disconnectGarmin}>Disconnect</button>
            </div>
          </>
        ) : needMfa ? (
          <>
            <label className="field">Multi-factor code</label>
            <input className="input" value={mfa} onChange={(e) => setMfa(e.target.value)}
              inputMode="numeric" placeholder="123456" />
            <button className="btn" disabled={busy || !mfa} onClick={doMfa}>Verify</button>
          </>
        ) : (
          <>
            <p className="muted">Log in once. Your password is only used to obtain a token and is never stored.</p>
            <label className="field">Email</label>
            <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="username" />
            <label className="field">Password</label>
            <input className="input" value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" />
            <button className="btn" disabled={busy || !email || !password} onClick={doLogin}>Connect Garmin</button>
            {gs?.reason && <p className="muted" style={{ marginTop: 8 }}>Status: {gs.reason}</p>}
          </>
        )}
      </div>

      <DeviceSync />

      <FitUpload onDone={(m) => { setToast(m); qc.invalidateQueries(); }} />

      <div className="card">
        <h3>Last sync</h3>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, color: "var(--text-dim)" }}>
          {JSON.stringify(syncStatus.data ?? {}, null, 2)}
        </pre>
      </div>

      <div className="card">
        <h3>Account</h3>
        <button className="btn secondary" onClick={() => logout()}>Sign out of PulseVault</button>
      </div>
    </>
  );
}

function DeviceSync() {
  const { data } = useQuery({
    queryKey: ["device-config"],
    queryFn: () => api.get<{ ingest_token: string; ingest_path: string }>("/api/device/config"),
  });
  const origin = window.location.origin;
  const copy = (t: string) => navigator.clipboard?.writeText(t);
  return (
    <div className="card">
      <h3>Device Sync (companion agent)</h3>
      <p className="muted">
        The desktop companion pulls FIT files off the watch (USB now, Bluetooth experimental) and
        pushes them here — no vendor cloud. Paste these into the agent's config.
      </p>
      <label className="field">Server URL</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="input" readOnly value={origin} />
        <button className="btn secondary" onClick={() => copy(origin)}>Copy</button>
      </div>
      <label className="field">Ingest token</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="input" readOnly value={data?.ingest_token ?? "…"} />
        <button className="btn secondary" onClick={() => data && copy(data.ingest_token)}>Copy</button>
      </div>
      <p className="muted" style={{ fontSize: 12 }}>
        Uploads to <code>{data?.ingest_path}</code>. Keep this token secret — it can push data to your server.
      </p>
    </div>
  );
}

function FitUpload({ onDone }: { onDone: (m: { ok: boolean; msg: string }) => void }) {
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function upload(files: FileList | null) {
    if (!files || !files.length) return;
    setBusy(true);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const r = await api.postForm<{ results: any[] }>("/api/upload/fit", form);
      const ok = r.results.filter((x) => x.state === "ok").length;
      onDone({ ok: ok > 0, msg: `Imported ${ok}/${r.results.length} FIT file(s).` });
    } catch (e: any) { onDone({ ok: false, msg: e.message }); } finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h3>Upload FIT files</h3>
      <p className="muted">Cloud-free import. Grab <code>.fit</code> files from the watch (USB → GARMIN/ACTIVITY).</p>
      <div className={"dropzone" + (over ? " over" : "")}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); }}>
        {busy ? "Importing…" : "Tap to choose, or drag .fit files here"}
      </div>
      <input ref={inputRef} type="file" accept=".fit" multiple hidden
        onChange={(e) => upload(e.target.files)} />
    </div>
  );
}
