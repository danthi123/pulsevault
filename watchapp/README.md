# Vaultwrist — Connect IQ watch app

**Vaultwrist** runs **on your Garmin watch** (Fenix 7 family) and pushes recent
metrics — **heart rate, stress, Body Battery, SpO₂, respiration** and today's
step/calorie totals — to your self-hosted **PulseVault** server. It coexists with
your normal Garmin/iPhone setup: nothing to unpair, no Garmin account changes.
Requests relay through the phone's Garmin Connect Mobile connection (or WiFi
where available).

**Why this exists:** it captures the Garmin-proprietary metrics (stress, Body
Battery) that FIT files and Apple Health don't reliably expose. Use it alongside
the PulseVault USB companion (which handles full activities/sleep).

## What it can and can't do

- ✅ Recent samples of HR / stress / Body Battery / SpO₂ / respiration via
  `Toybox.SensorHistory`, plus today's steps/calories/distance.
- ❌ Recorded activities, GPS tracks, full sleep sessions, historical database —
  Connect IQ apps are sandboxed from those. That's what the USB companion is for.

## Requirements

1. **Connect IQ SDK** (free) — <https://developer.garmin.com/connect-iq/sdk/>.
   The SDK Manager downloads the SDK + device profiles.
   - On most distros: unzip and run `bin/sdkmanager` directly.
   - **On Arch/CachyOS** the SDK Manager needs the EOL WebKitGTK-4.0 stack that's
     no longer packaged. Use the containerized runner in `sdk-runner/` (Ubuntu
     22.04 has those libs): `./sdk-runner/run-sdkmanager.sh`. It renders the GUI
     on your desktop and saves downloads to your real `~/.Garmin`. Build the
     image once: `docker build -t ciq-sdkmanager sdk-runner/`.
2. A **developer key** (`developer_key.der`) — already generated here, or `make key`.

## Configure

Either hard-code the two constants in [`source/Config.mc`](source/Config.mc)
(`DEFAULT_SERVER`, `DEFAULT_TOKEN` — token from the PulseVault web UI → Settings →
Device Sync), **or** leave them and set `serverUrl` / `token` per-install in
Garmin Connect Mobile → this app's settings after sideloading.

## Build & sideload

```bash
cd watchapp
make build                       # -> bin/Vaultwrist.prg (auto-detects the SDK)
```

Then copy the `.prg` onto the watch over USB (Fenix 7 mounts via MTP):

```bash
make sideload WATCH="/run/user/1000/gvfs/mtp:host=.../Primary"
# or copy bin/Vaultwrist.prg into the watch's GARMIN/Apps/ folder by hand
```

Unplug; the app appears in the watch's app/activity list. Open it once — the
foreground view does an immediate push and shows "Synced OK" or an HTTP error.
After that the background service pushes every `intervalMinutes` (≥5).

Tip: test in the **Connect IQ simulator** first (`make sim`, then `make run` in
another terminal) — it can fake sensor data and shows `makeWebRequest` results
without the watch.

## Wireless install (optional)

`make package` builds `bin/Vaultwrist.iq` for the Connect IQ store. Upload it at
the [developer dashboard](https://apps.garmin.com/developer/dashboard) as an
**Unlisted/Beta** app, then install to the watch from Garmin Connect Mobile — no
cable. (Same `developer_key.der` must be reused for updates.)

## HTTPS

Connect IQ requires HTTPS for `makeWebRequest`. Point `DEFAULT_SERVER` at your
PulseVault server behind TLS (e.g. a Caddy vhost with a real cert / Cloudflare
DNS-01, reachable from your phone's network). The watch/phone must trust the
cert chain.

## Notes

- `when.value()` is treated as UNIX epoch seconds; the server assumes the same.
  Verify once against real data and adjust in `backend/app/ingest/metrics.py`
  if your firmware reports a different epoch.
