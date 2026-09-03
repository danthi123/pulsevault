# How watch data reaches PulseVault

PulseVault never talks to a watch directly (a server has no Bluetooth link to a
watch that lives next to your phone). Instead it **ingests your own data** through
several complementary paths, each of which maps into one normalized
[`IngestBundle`](../backend/app/ingest/base.py) and is persisted by a single
**idempotent** upsert — so re-running any path never creates duplicates.

No single path captures everything. This document is the map of what each path
covers, and — importantly — the limits of each, especially for someone who wants
to stop using Garmin's phone app entirely.

## The paths

| Path | Adapter | Covers | Needs |
|---|---|---|---|
| **Garmin Connect pull** | [`ingest/garmin_connect.py`](../backend/app/ingest/garmin_connect.py) | Everything Garmin computes (incl. **sleep**, Body Battery, HRV) as intraday series + daily summaries | A working Garmin Connect login (currently Cloudflare-blocked from the server; token-import is the workaround) |
| **Garmin account export** | [`ingest/garmin_export.py`](../backend/app/ingest/garmin_export.py) | Complete **history** — sleep (with stages) + daily summaries, plus any activity `.fit` inside | A one-time "Export Your Data" zip from garmin.com, uploaded in Settings |
| **FIT upload** | [`ingest/fit.py`](../backend/app/ingest/fit.py) | Activities, and all-day **Monitor** wellness (HR/steps/stress/SpO₂/respiration) + sleep files | You drag `.fit` files into Settings |
| **USB companion** | [`companion/`](../companion) → FIT upload | Same as FIT upload, but **auto-pulled** off the watch over USB and drained to the server | The companion app running on a desktop, watch plugged in |
| **On-watch app (Vaultwrist)** | [`watchapp/`](../watchapp) → [`ingest/metrics.py`](../backend/app/ingest/metrics.py) | Near-real-time HR / stress / Body Battery / SpO₂ / respiration + today's totals | The Connect IQ app sideloaded; a relay (phone **or** WiFi) |

### Coverage at a glance

| Data | Connect pull | Export | FIT / USB companion | On-watch app |
|---|:--:|:--:|:--:|:--:|
| Activities (workouts, GPS) | ✅ | ✅ (if included) | ✅ | ❌ |
| All-day HR / stress / SpO₂ / respiration | ✅ | daily only | ✅ | ✅ (live) |
| Body Battery | ✅ | daily only | partial | ✅ (live) |
| Steps history | ✅ | daily totals | ✅ | today's total only |
| **Sleep (stages)** | ✅ | ✅ | ✅ | ❌ **(impossible on-watch)** |
| Daily summaries (RHR, stress avg…) | ✅ | ✅ | partial | ❌ |

## Going phone-app-free

A core goal is letting someone drop the Garmin phone app and still get near-complete
data into PulseVault. That works, through **two complementary paths** — but it's not
one automatic pipe, and there is one structural gap. The details matter:

### 1. The on-watch app + outbox (wireless)

Covers the five `SensorHistory` metrics (HR, stress, Body Battery, SpO₂, respiration).
With no phone, `makeWebRequest` can't relay through Garmin Connect Mobile, so it goes
out over the **watch's own WiFi**. The app keeps a **persistent outbox** in
Application.Storage: every run it captures new samples into the outbox, and only
*drains* them on a confirmed (HTTP 200) push. So offline stretches **accumulate**
locally instead of rolling off the short `SensorHistory` buffer, and sync when WiFi
returns — with loss bounded only if you exceed the per-metric cap
([`Collector.mc`](../watchapp/source/Collector.mc), `MAX_OUTBOX`).

The app's foreground screen shows **last successful sync** ("5m ago" / "never") and
the **queued** sample count, so a phone-free user can see whether wireless sync is
actually reaching the server.

**Caveat — WiFi reliability.** WiFi is power-hungry, so the watch brings it up
opportunistically; an unattended background push may not reliably wake WiFi. In
practice the outbox drains best when the watch is on known WiFi and/or the app is
opened. The outbox bounds worst-case loss, but "continuous unattended wireless sync
with no phone" is the part to verify on real hardware.

### 2. FIT files + companion (USB)

Covers everything the app can't — activities, all-day Monitor wellness, and **sleep**.

The key fact: the watch prunes local `.fit` files only **after they successfully sync
to Garmin Connect**. So:

- **Purge stops when *all* Garmin sync stops** — not merely when the phone app is
  gone. The Fenix can also sync directly over WiFi if it's tied to a Garmin account.
  For a user with no Garmin ecosystem at all, nothing syncs, so files **accumulate**
  and the companion can backfill a long history on the next plug-in.
- **The companion is USB — manual.** Data lands on a plug-in cadence, not continuously.
- **Retention isn't provably unlimited.** Files persist far longer un-synced, but the
  `Monitor/` folder rotates by count on some firmwares — don't assume infinite backfill.

The companion itself is an **inbox** model: it auto-pulls new `.fit` off the watch into
a `FIT/` folder next to the executable, uploads each, and **deletes it on success**
(keeps it if the server rejected it; retries when offline). Files dropped into `FIT/`
by hand are treated identically. See [companion/README.md](../companion/README.md).

### 3. The structural gap: sleep, wirelessly

Connect IQ has **no API for the watch's computed sleep**, so the on-watch app can
never send sleep. Wirelessly, sleep never reaches the vault. Sleep only ever arrives
via **FIT files (USB companion)** or **Garmin Connect (pull/export)**. A user who only
runs the app and never plugs in — or never imports from Garmin — gets everything
*except* sleep.

### Net

For a **sideloaded-app + occasional-USB** user, coverage is near-complete: the wireless
path keeps live sensor metrics flowing, and the un-purged FIT files let a USB plug-in
backfill everything including sleep. The two things not to over-promise are
**unattended wireless sync** (WiFi-dependent) and **wireless sleep** (structurally
impossible) — sleep always wants a USB pull or Garmin Connect.

## Why it's safe to combine paths

Every path converges on `IngestBundle` and is persisted with upserts keyed on natural
constraints (`(user_id, ts)` for samples, `(user_id, start_ts)` for workouts,
`(user_id, day)` for daily summaries and sleep). Running two paths that overlap — say
the on-watch app and a USB pull for the same afternoon — just upserts the same rows.
Re-importing the same Garmin export is a no-op. So you can layer paths freely to
maximize coverage without fear of duplicates.
