#!/bin/bash
set -e

# Inject API keys from environment variables into OpenClaw config
if [ -n "$ANTHROPIC_API_KEY" ]; then
    export ANTHROPIC_API_KEY
fi

if [ -n "$OPENAI_API_KEY" ]; then
    export OPENAI_API_KEY
fi

# Inject gateway token from env var into config
if [ -n "$GATEWAY_TOKEN" ]; then
    CONFIG=/root/.openclaw/openclaw.json
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, os
with open('$CONFIG') as f: cfg = json.load(f)
cfg.setdefault('gateway', {}).setdefault('auth', {})['token'] = os.environ['GATEWAY_TOKEN']
with open('$CONFIG', 'w') as f: json.dump(cfg, f, indent=2)
"
    else
        sed -i "s/__OPENVORT_GATEWAY_TOKEN__/$GATEWAY_TOKEN/" "$CONFIG"
    fi
fi

# Auto-fix config compatibility issues
openclaw doctor --fix 2>/dev/null || true

# Start the OpenClaw gateway
exec openclaw gateway --port 18789 --verbose --allow-unconfigured
