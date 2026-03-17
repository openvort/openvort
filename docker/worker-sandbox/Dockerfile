FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Aider
RUN pip install --no-cache-dir aider-chat

# Git config defaults
RUN git config --system user.name "OpenVort AI" \
    && git config --system user.email "ai@openvort.dev"

WORKDIR /workspace
CMD ["sleep", "infinity"]
