# PulseVault Companion

A small desktop agent that pulls FIT files off your Garmin watch and pushes them
to your PulseVault server — **no vendor cloud involved**. Linux-first, built
to port cleanly to Windows/macOS.

## How it works

```
Watch ──USB(MTP)──▶ companion agent ──POST /api/ingest/fit (token)──▶ PulseVault
```

The agent stays dumb: it detects the watch, finds new `.fit` files, and uploads
the raw bytes. The server parses and dedupes, so re-running is always safe.

## Sync sources

| Source | What it does | OS |
|---|---|---|
| `mtp` (default) | Auto-detects the Fenix when plugged in and auto-mounted, reads `GARMIN/{Activity,Monitor,Sleep,Metrics}` | Linux (gvfs); macOS with an MTP FUSE mount |
| `folder` | Watches any directory tree for `.fit` files | Any (Windows: copy from Explorer; also Syncthing/Nextcloud folders) |
| `ble` | **Experimental.** Garmin GFDI over Bluetooth — not syncing yet; `ble-probe` helps bring it up | Linux/macOS/Windows (bleak) |

## Install

```bash
cd companion
pipx install .            # or: pip install .
# For the experimental Bluetooth probe:
pipx install '.[ble]'
```

## Configure

```bash
cp config.example.toml config.toml
# edit: set server_url and paste the token from the web UI (Settings → Device Sync)
```

## Run

```bash
pulsevault-companion status     # show config + whether the watch is currently detected
pulsevault-companion once       # one sync pass, then exit
pulsevault-companion run        # run continuously on the poll interval
```

Plug the Fenix in (let your desktop mount it), then `pulsevault-companion once`. New
activities/monitoring files upload; open the web UI to see them.

### Run as a service (Linux)

```bash
cp systemd/pulsevault-companion.service ~/.config/systemd/user/
systemctl --user enable --now pulsevault-companion
journalctl --user -u pulsevault-companion -f
```

## Bluetooth (experimental)

Full activity/health sync over BLE means speaking Garmin's proprietary GFDI
protocol — a reverse-engineering effort that has to be brought up against a real
watch. First step is dumping the watch's Bluetooth services:

```bash
pulsevault-companion ble-probe            # scans, connects, prints the GATT table
```

Share that output to help implement the real client in `pulsevault_companion/sources/ble.py`.
Make sure the watch is in Bluetooth range and **not connected to a phone**.

## Notes / limitations

- The Fenix 7 is **MTP**, not a USB drive. On Linux your desktop auto-mounts it
  (gvfs); if not, mount with `jmtpfs`/`go-mtpfs` and set `mount_globs`.
- FIT gives activities + daily monitoring + sleep. Garmin-proprietary metrics
  (Body Battery, stress, training status) are only partly in FIT — a future
  on-watch Connect IQ app (pushing to `/api/ingest/metrics`) is the planned way
  to get those cloud-free.
