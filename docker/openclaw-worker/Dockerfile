FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install OpenClaw
RUN npm install -g openclaw@latest

# Git config defaults
RUN git config --system user.name "OpenVort AI" \
    && git config --system user.email "ai@openvort.dev"

# Config template (overridden at runtime via env vars)
RUN mkdir -p /root/.openclaw
COPY openclaw.json /root/.openclaw/openclaw.json

WORKDIR /workspace

EXPOSE 18789

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
