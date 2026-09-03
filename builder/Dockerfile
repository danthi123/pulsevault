# PulseVault watch-app builder: compiles Vaultwrist .prg files on demand with a
# user's server URL + ingest token baked in (so self-hosters can sideload a
# ready-configured app without the Garmin phone app).
#
# The build CONTEXT must be assembled first (SDK is large + licensed, so it is
# NOT committed). See build.sh, which copies the Connect IQ SDK and the full
# device library into the context.
#
# The image holds only the STABLE bits (SDK + devices + server.py). The watchapp
# source and the signing key are BIND-MOUNTED at runtime (see the server's
# docker-compose.override.yml and the CI workflow), so app/manifest/device-list
# changes are a plain rsync — no image rebuild or multi-hundred-MB transfer. The
# image is rebuilt only when the SDK itself is updated.
FROM eclipse-temurin:17-jre
ENV HOME=/root DEBIAN_FRONTEND=noninteractive \
    MONKEYC=/root/.Garmin/ConnectIQ/Sdks/current/bin/monkeyc
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*

# Replicate the local ~/.Garmin layout so monkeyc + device DB resolve normally.
COPY sdk     /root/.Garmin/ConnectIQ/Sdks/current
COPY devices /root/.Garmin/ConnectIQ/Devices

COPY server.py /app/server.py
# Mount points for the bind-mounted app source + signing key (shadowed at run).
RUN mkdir -p /app/watchapp

EXPOSE 8080
CMD ["python3", "/app/server.py"]
