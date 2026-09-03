# PulseVault Companion

A small desktop agent that pulls FIT files off your Garmin watch over USB and
pushes them to your PulseVault server — **no vendor cloud involved**.

## How it works — the inbox model

```
Watch ──USB(MTP)──▶ [ auto-pull ] ──▶ FIT/ folder ──▶ [ upload ] ──▶ PulseVault
                                          ▲                 │
                                    drop files here    delete on success
```

The agent keeps a `FIT/` folder next to the executable and, each cycle:

1. **Auto-pulls** new `.fit` off the connected watch into `FIT/` (from
   `GARMIN/{Activity,Monitor,Sleep,Metrics}` — never the sport-preset templates).
2. **Drains** `FIT/`: uploads each file and **deletes it on success** (keeps it if
   the server rejected it; retries when offline).

Files you drop into `FIT/` by hand are handled identically. The server parses and
dedupes, so re-running is always safe.

This is the cloud-free backfill path for activities, all-day wellness, and **sleep**.
It complements the on-watch Vaultwrist app (live sensor metrics) — see
[../docs/DATA-FLOW.md](../docs/DATA-FLOW.md) for how they combine, and why the watch
retains files for this to pull only while it isn't syncing to Garmin.

## Get it (recommended): download from the web UI

**PulseVault → Settings → Device Sync → Download for Linux / Windows.** You get a
zip containing the prebuilt binary, a `config.toml` already filled in with your
server URL + token, a `README.txt`, and an empty `FIT/` inbox. Extract, keep the
files together, and run the binary:

- **Linux:** `chmod +x pulsevault-companion && ./pulsevault-companion`
- **Windows:** double-click `pulsevault-companion.exe` (or run it in a terminal)

It syncs immediately on launch, then every `poll_interval` seconds.

### Auto-pull support

| OS | Auto-pull | Notes |
|---|---|---|
| **Linux** | ✅ | Uses the gvfs MTP mount when the watch is plugged in. |
| **Windows** | ⚠️ experimental | Driverless WPD via PowerShell (`Shell.Application`). If it doesn't grab your watch, open the Fenix in Explorer (Internal Storage → `GARMIN`) and copy `Activity`/`Monitor`/`Sleep` `.fit` into the `FIT/` folder — they upload and vanish. |
| **macOS** | ✅* | Needs an MTP FUSE mount. |

## Commands

```
pulsevault-companion status   # config + probes the watch (device + folders it sees)
pulsevault-companion once     # one pull + drain, then exit
pulsevault-companion run      # run continuously on the poll interval (default)
```

Plug the watch in, then `... status` to confirm it's detected, or just `... run`.

## Configure

`config.toml` (next to the binary) — the web download pre-fills it:

```toml
server_url    = "https://pulsevault.example.com"
token         = "…"      # Settings → Device Sync
poll_interval = 60
fit_dir       = "FIT"    # inbox folder next to the app
auto_pull     = true     # copy new .fit off the watch automatically
```

## Run from source (development)

```bash
cd companion
pipx install .                 # or: pip install .
cp config.example.toml config.toml   # then set server_url + token
pulsevault-companion run
```

### Run as a service (Linux)

```bash
cp systemd/pulsevault-companion.service ~/.config/systemd/user/
systemctl --user enable --now pulsevault-companion
journalctl --user -u pulsevault-companion -f
```

## Building the binaries

The single-file binaries are built by GitHub Actions
([`.github/workflows/build-companion.yml`](../.github/workflows/build-companion.yml))
on native Linux + Windows runners with PyInstaller, then dropped into the server's
`companion-dist/` so the web UI can serve them.

## Notes / limitations

- The Fenix 7 is **MTP**, not a USB drive. On Linux your desktop auto-mounts it
  (gvfs); if not, mount with `jmtpfs`/`go-mtpfs`.
- Windows MTP `CopyHere` is asynchronous; the puller waits for each copy to finish
  before exiting. If a file times out it's logged and retried next cycle.
- FIT gives activities + all-day monitoring + sleep. Garmin-proprietary live metrics
  (Body Battery, stress) come from the on-watch **Vaultwrist** app instead.
- `pulsevault_companion/sources/ble.py` holds an **experimental**, not-yet-working
  Garmin GFDI-over-Bluetooth source; `pulsevault-companion ble-probe` dumps the GATT
  table to help bring it up.
