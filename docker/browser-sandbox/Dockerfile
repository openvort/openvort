FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV VNC_PORT=5900
ENV NOVNC_PORT=6080

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    x11-apps \
    novnc \
    websockify \
    fonts-noto-cjk \
    fonts-liberation \
    dbus-x11 \
    supervisor \
    curl \
    git \
    python3 \
    python3-pip \
    && pip3 install --break-system-packages playwright \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

RUN CHROME_PATH=$(find /root/.cache/ms-playwright -name "chrome" -path "*/chrome-linux*/chrome" | head -1) \
    && printf '#!/bin/sh\nexec %s "$@"\n' "$CHROME_PATH" > /usr/local/bin/chromium-launcher \
    && chmod +x /usr/local/bin/chromium-launcher

RUN mkdir -p /workspace

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 5900 6080 9222

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
