# PulseVault

A self-hosted, mobile-first **web dashboard** for your smartwatch data — a
Gadgetbridge-style experience you can open from an iPhone (or any browser),
running as a Docker stack.

Gadgetbridge itself is an **Android** app that talks to watches over Bluetooth.
It can't run on iOS, and a server has no Bluetooth link to a watch that lives
next to your phone. So PulseVault takes a different route: it **ingests your
own data** and owns the storage + UI.

## How data gets in

| Path | For | How |
|------|-----|-----|
| **Garmin Connect pull** | Garmin (e.g. Fenix 7) | The backend polls the Garmin cloud with [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect) on a schedule, and on demand via a **Sync now** button. Works from any browser because the sync happens server-side — no Bluetooth. |
| **FIT upload** | Any Garmin device | Drag-and-drop `.fit` files (or plug the watch in via USB and grab them from `GARMIN/ACTIVITY`) on the Settings page. Fully cloud-free. |

Both paths converge on one normalized schema and **merge idempotently** — re-syncing
never creates duplicates.

## Quick start

```bash
cp .env.example .env
# edit .env: set APP_PASSWORD, APP_SECRET_KEY (openssl rand -hex 32), POSTGRES_PASSWORD
docker compose up --build -d
```

Open **http://localhost:8080** (change the host port with `PROXY_PORT` in `.env`).

1. Sign in with `APP_USERNAME` / `APP_PASSWORD`.
2. Go to **Settings → Garmin Connect**, log in once (enter the MFA code if
   prompted). The password is only used to fetch an auto-refreshing token; it is
   never stored on disk.
3. Hit **Backfill 30 days**, then let the scheduler keep it fresh.
4. Optionally drop `.fit` files in **Settings → Upload FIT files**.

## Architecture

```
Browser ──▶ Caddy (proxy, :8080) ──▶ FastAPI backend ──▶ Postgres
                    │                        │
                    └── serves the React SPA │── python-garminconnect (cloud pull)
                                             └── fitdecode (FIT upload)
```

- `backend/` — FastAPI + SQLAlchemy. Ingesters live in `backend/app/ingest/`;
  each source (Garmin Connect, FIT, and a future Gadgetbridge-SQLite adapter)
  maps into the shared `IngestBundle` and is persisted by one idempotent upsert.
- `frontend/` — React + Vite, responsive for phone and desktop.
- Data model: `backend/app/models.py`.

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

## Updating the stack

```bash
git pull            # or pull new prebuilt images if you publish them
docker compose up --build -d
```

## Caveats

- `python-garminconnect` is an **unofficial** client; Garmin may rate-limit or
  change endpoints. Keep syncs infrequent (default every 3h).
- Body Battery and sleep scores come only from the Garmin Connect path (they're
  not in the public FIT profile).
- Single-user by design. Put it behind your own HTTPS/VPN if exposing it.

## Development (without Docker)

```bash
# backend
cd backend && pip install . && uvicorn app.main:app --reload   # needs a Postgres in DATABASE_URL
# frontend
cd frontend && npm install && npm run dev                      # proxies /api to :8000
```
