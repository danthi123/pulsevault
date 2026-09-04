# PulseVault

A self-hosted, mobile-first **web dashboard** for your smartwatch data — a
Gadgetbridge-style experience you can open from an iPhone (or any browser),
running as a Docker stack.

Gadgetbridge itself is an **Android** app that talks to watches over Bluetooth.
It can't run on iOS, and a server has no Bluetooth link to a watch that lives
next to your phone. So PulseVault takes a different route: it **ingests your
own data** and owns the storage + UI.

## How data gets in

PulseVault ingests your own data through several complementary paths — no single
one captures everything, so you layer whichever fit your setup:

| Path | For | How |
|------|-----|-----|
| **Garmin Connect pull** | Complete history incl. sleep | The backend polls the Garmin cloud with [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect) on a schedule / on demand. (Garmin's Cloudflare bot-protection can block logins from some server IPs; if so, use the account-export path below.) |
| **Garmin account export** | One-time full backfill incl. sleep | Upload a "Export Your Data" zip from garmin.com in **Settings → Import Garmin Connect export**. |
| **FIT upload** | Cloud-free, any Garmin device | Drag `.fit` files (from `GARMIN/{Activity,Monitor,Sleep}`) onto the Settings page. |
| **USB companion** | Automatic cloud-free backfill | A small desktop app ([`companion/`](companion)) auto-pulls `.fit` off the watch over USB and uploads them. |
| **On-watch app (Vaultwrist)** | Near-real-time, no phone needed | A Connect IQ app ([`watchapp/`](watchapp)) pushes HR / stress / Body Battery / SpO₂ / respiration straight from the watch over the phone relay **or WiFi**. |

Every path converges on one normalized schema and **merges idempotently** — re-syncing
or overlapping paths never creates duplicates.

**→ See [docs/DATA-FLOW.md](docs/DATA-FLOW.md)** for the full coverage matrix, and the
detail on going **phone-app-free** (what the app + USB combination does and doesn't
capture, why sleep can't come from the watch app, and how file-pruning works).

## Quick start

```bash
git clone https://github.com/danthi123/pulsevault.git && cd pulsevault
cp .env.example .env
# edit .env: set APP_PASSWORD, POSTGRES_PASSWORD, and APP_SECRET_KEY (openssl rand -hex 32)
docker compose up -d          # builds the images on first run
```

Open **http://localhost:8080** (change the host port with `PROXY_PORT` in `.env`),
then sign in with `APP_USERNAME` / `APP_PASSWORD`.

That's the whole install. **No Garmin account is required** — you can immediately
drop `.fit` files or a Garmin export into **Settings**. To pull from the cloud:

1. **Settings → Garmin Connect**, log in once (enter the MFA code if prompted).
   The password only seeds an auto-refreshing token; it is never stored on disk.
2. Hit **Backfill 30 days**, then let the scheduler keep it fresh.

## Architecture

```
Browser ─▶ frontend  ─▶ FastAPI backend ─▶ Postgres
           (Caddy:        │
            SPA + /api     ├─ python-garminconnect  (Garmin pull / export)
            reverse-proxy) └─ fitdecode             (FIT upload / USB companion / watch app)
```

- `frontend/` — React + Vite SPA, served by a tiny Caddy that also reverse-proxies
  `/api` to the backend, so it's the single web entrypoint (behind your own TLS).
- `backend/` — FastAPI + SQLAlchemy. Ingesters in `backend/app/ingest/` each map a
  source (Garmin Connect JSON, Garmin export, FIT, on-watch metrics) into the shared
  `IngestBundle`, persisted by one idempotent upsert. Data model: `backend/app/models.py`.
- `watchapp/` — the Vaultwrist Connect IQ app. `companion/` — the desktop USB agent.

## Following Gadgetbridge upstream

This project deliberately does **not** fork Gadgetbridge's Android/Java code
(none of it compiles to a web app, and its value is the on-device Bluetooth
work we replace with cloud/FIT ingestion). Instead:

- The **schema and screens** are modeled on Gadgetbridge as a reference.
- Anything derived from a specific data source's quirks is isolated in one
  adapter file (`ingest/garmin_connect.py`, `ingest/fit.py`), so a payload
  change upstream is a contained, mechanical patch — not a rewrite.
- To ingest data from an Android phone running the real Gadgetbridge later, add
  `ingest/gadgetbridge.py` that reads its SQLite export into an `IngestBundle`.
  No schema or UI changes required.

## Optional: companion agent & watch app

Both are optional extras on top of the core dashboard:

- **USB companion** ([`companion/`](companion)) — the backend image **automatically
  downloads** the prebuilt Linux/Windows binaries from the latest
  [GitHub Release](https://github.com/danthi123/pulsevault/releases) at build time
  (CI builds + attaches them via [`build-companion.yml`](.github/workflows/build-companion.yml)),
  so the in-app **Download for Linux/Windows** buttons work out of the box after
  `compose up`. To refresh after a new release: `docker compose build --no-cache backend`.
  You can also run it from source (`pipx install ./companion`). See
  [companion/README.md](companion/README.md).
- **Vaultwrist watch app** ([`watchapp/`](watchapp)) — build the `.prg` with the Garmin
  Connect IQ SDK and sideload it, or wire up the in-repo builder service. See
  [watchapp/README.md](watchapp/README.md).

Neither is needed for the Garmin-cloud, export, or FIT-upload paths.

## Updating the stack

```bash
git pull            # or pull new prebuilt images if you publish them
docker compose up --build -d
```

## Caveats

- `python-garminconnect` is an **unofficial** client; Garmin may rate-limit or
  change endpoints. Keep syncs infrequent (default every 3h).
- **Sleep** is never available from the on-watch app (Connect IQ has no sleep
  API) — it comes from FIT files (USB companion), the Garmin account export, or
  the Garmin Connect pull. Body Battery / stress are Garmin-proprietary and come
  from the on-watch app or Garmin Connect (only partly in FIT). See
  [docs/DATA-FLOW.md](docs/DATA-FLOW.md).
- Single-user by design. Put it behind your own HTTPS/VPN if exposing it.

## Development (without Docker)

```bash
# backend
cd backend && pip install . && uvicorn app.main:app --reload   # needs a Postgres in DATABASE_URL
# frontend
cd frontend && npm install && npm run dev                      # proxies /api to :8000
```
