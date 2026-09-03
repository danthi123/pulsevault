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

      <WatchAppInstall onToast={setToast} />

      <DeviceSync onToast={setToast} />

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

function WatchAppInstall({ onToast }: { onToast: (m: { ok: boolean; msg: string }) => void }) {
  const { data } = useQuery({
    queryKey: ["watch-devices"],
    queryFn: () => api.get<{ devices: Record<string, string> }>("/api/watchapp/devices"),
  });
  const devices = data?.devices ?? {};
  const ids = Object.keys(devices);
  const [device, setDevice] = useState("fenix7xpro");
  const [busy, setBusy] = useState(false);

  async function download() {
    setBusy(true);
    try {
      const url = `/api/watchapp/build?device=${encodeURIComponent(device)}&server=${encodeURIComponent(window.location.origin)}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) {
        let msg = `Build failed (HTTP ${res.status})`;
        try { msg = (await res.json()).detail || msg; } catch { /* text */ }
        throw new Error(msg);
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Vaultwrist-${device}.prg`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
      onToast({ ok: true, msg: "Watch app built — check your downloads." });
    } catch (e: any) { onToast({ ok: false, msg: e.message }); } finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h3>Install on your Garmin watch (Vaultwrist)</h3>
      <p className="muted">
        Download a watch app pre-configured for <b>this</b> server — no Garmin phone
        app or manual setup needed. Pick your watch, download, and copy the <code>.prg</code>
        into the watch's <code>GARMIN/Apps/</code> folder over USB.
      </p>
      <label className="field">Watch model</label>
      <div style={{ display: "flex", gap: 8 }}>
        <select className="input" value={ids.includes(device) ? device : ids[0]}
          onChange={(e) => setDevice(e.target.value)} style={{ flex: 1 }}>
          {ids.map((id) => <option key={id} value={id}>{devices[id]}</option>)}
        </select>
        <button className="btn" disabled={busy || !ids.length} onClick={download}>
          {busy ? "Building…" : "Download app"}
        </button>
      </div>
      <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Then open Vaultwrist on the watch — it syncs immediately, no configuration. Building takes a few seconds.
      </p>
    </div>
  );
}

function DeviceSync({ onToast }: { onToast: (m: { ok: boolean; msg: string }) => void }) {
  const { data } = useQuery({
    queryKey: ["device-config"],
    queryFn: () => api.get<{ ingest_token: string; ingest_path: string }>("/api/device/config"),
  });
  const origin = window.location.origin;
  const copy = (t: string) => navigator.clipboard?.writeText(t);
  const [dling, setDling] = useState<string | null>(null);

  async function download(target: "linux" | "windows") {
    setDling(target);
    try {
      const res = await fetch(`/api/companion/download?target=${target}&server=${encodeURIComponent(origin)}`,
        { credentials: "same-origin" });
      if (!res.ok) {
        let m = `Download failed (HTTP ${res.status})`;
        try { m = (await res.json()).detail || m; } catch { /* */ }
        throw new Error(m);
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `pulsevault-companion-${target}.zip`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
      onToast({ ok: true, msg: `Companion (${target}) downloaded — extract and run.` });
    } catch (e: any) { onToast({ ok: false, msg: e.message }); } finally { setDling(null); }
  }

  return (
    <div className="card">
      <h3>Device Sync (companion agent)</h3>
      <p className="muted">
        The desktop companion pulls FIT files off the watch and pushes them here — no
        vendor cloud. Download a build pre-configured for this server, or configure the
        agent manually with the values below.
      </p>
      <div className="pill-row">
        <button className="btn" disabled={dling !== null} onClick={() => download("linux")}>
          {dling === "linux" ? "Preparing…" : "Download for Linux"}
        </button>
        <button className="btn" disabled={dling !== null} onClick={() => download("windows")}>
          {dling === "windows" ? "Preparing…" : "Download for Windows"}
        </button>
      </div>
      <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
        Extract the zip, keep the binary + <code>config.toml</code> together, and run it.
      </p>
      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "14px 0" }} />
      <p className="muted" style={{ fontSize: 13 }}>Or configure manually:</p>
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
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  async function upload(files: FileList | null) {
    if (!files || !files.length) return;
    setBusy(true); setResult(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const r = await api.postForm<{ accepted: number; total: number; results: any[] }>("/api/upload/fit", form);
      const ok = r.accepted ?? r.results.filter((x) => x.state === "ok").length;
      const total = r.total ?? r.results.length;
      const errs = r.results.filter((x) => x.state === "error");
      const msg = errs.length
        ? `Imported ${ok}/${total}. Failed: ${errs.map((e) => e.file).join(", ")}`
        : `Imported ${ok}/${total} file(s) — see the Workouts page.`;
      const m = { ok: ok > 0, msg };
      setResult(m); onDone(m);
    } catch (e: any) {
      const m = { ok: false, msg: e.message };
      setResult(m); onDone(m);
    } finally { setBusy(false); }
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
      {result && (
        <div className={"toast " + (result.ok ? "ok" : "err")} style={{ marginTop: 10, marginBottom: 0 }}>
          {result.msg}
        </div>
      )}
      <input ref={inputRef} type="file" accept=".fit" multiple hidden
        onChange={(e) => upload(e.target.files)} />
    </div>
  );
}
