FROM python:3.11-slim

# Install Node.js and npm (for Claude Code and Codex CLI)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Install Codex CLI  
RUN npm install -g @openai/codex

# Install Aider (Python-based)
RUN pip install --no-cache-dir aider-chat

# Install Git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
CMD ["sleep", "infinity"]
