# Privacy Policy — PulseVault & Vaultwrist

_Last updated: 2026-09-03_

PulseVault is self-hosted, open-source software. **Vaultwrist** is its Connect IQ
watch app. Neither the software nor its author operates a hosted service or
collects any data centrally.

## What data is involved
The Vaultwrist watch app reads recent on-device wellness metrics from your Garmin
watch — heart rate, stress, Body Battery, SpO₂, respiration, and today's steps,
calories, and distance — and transmits them **only to the server address that you
configure** (your own PulseVault instance). The PulseVault server stores that data
on infrastructure **you** own and control.

## Where your data goes
- Data is sent over HTTPS to **your** configured server, authenticated with a
  token **you** provide.
- Requests are relayed through your phone's Garmin Connect Mobile connection or
  your watch's Wi-Fi.
- **No data is ever sent to the author of this software or to any third party.**
  There is no analytics, tracking, telemetry, or hosted backend operated by us.

## Who controls the data
You do. Because you host the PulseVault server, you are the sole controller and
processor of any data these apps handle. Retention, deletion, backups, and access
are entirely determined by your own deployment.

## Contact
Questions or issues: https://github.com/danthi123/pulsevault/issues
