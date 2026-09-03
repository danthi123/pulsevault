# PulseVault watch-app builder: compiles Vaultwrist .prg files on demand with a
# user's server URL + ingest token baked in (so self-hosters can sideload a
# ready-configured app without the Garmin phone app).
#
# The build CONTEXT must be assembled first (SDK is large + licensed, so it is
# NOT committed). See build.sh, which copies the Connect IQ SDK, the Fenix 7
# device files, the watchapp source, and a signing key into the context.
FROM eclipse-temurin:17-jre
ENV HOME=/root DEBIAN_FRONTEND=noninteractive \
    MONKEYC=/root/.Garmin/ConnectIQ/Sdks/current/bin/monkeyc
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*

# Replicate the local ~/.Garmin layout so monkeyc + device DB resolve normally.
COPY sdk     /root/.Garmin/ConnectIQ/Sdks/current
COPY devices /root/.Garmin/ConnectIQ/Devices

COPY watchapp           /app/watchapp
COPY developer_key.der  /app/developer_key.der
COPY server.py          /app/server.py

EXPOSE 8080
CMD ["python3", "/app/server.py"]
