# Ubuntu 22.04 has the EOL WebKitGTK-4.0 / libsoup2 stack that Garmin's SDK
# Manager needs but Arch/CachyOS no longer ships. We use this image ONLY to run
# the SDK Manager GUI (to download the SDK + device). Building apps afterward is
# done natively on the host with monkeyc + your host JDK.
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwebkit2gtk-4.0-37 libjavascriptcoregtk-4.0-18 libsoup2.4-1 \
    libgtk-3-0 libgdk-pixbuf-2.0-0 libglib2.0-0 libnss3 libnspr4 \
    libx11-6 libxext6 libxrender1 libxtst6 libxi6 libxcomposite1 libxdamage1 \
    libxrandr2 libxfixes3 libxcursor1 libxinerama1 libxkbcommon0 libgl1 libegl1 \
    libpango-1.0-0 libcairo2 libatk1.0-0 libatk-bridge2.0-0 libepoxy0 \
    libsecret-1-0 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
    libcurl4 libsm6 libice6 \
    librsvg2-2 librsvg2-common libgdk-pixbuf2.0-bin shared-mime-info \
    adwaita-icon-theme hicolor-icon-theme gsettings-desktop-schemas \
    ca-certificates dbus-x11 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
