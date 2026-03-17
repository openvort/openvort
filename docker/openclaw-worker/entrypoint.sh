#!/bin/bash
set -e

CONFIG=/root/.openclaw/openclaw.json

# Apply all OpenVort-injected config in one pass
python3 -c "
import json, os

with open('$CONFIG') as f:
    cfg = json.load(f)

# Gateway token (auth + remote)
gt = os.environ.get('GATEWAY_TOKEN', '')
if gt:
    gw = cfg.setdefault('gateway', {})
    gw.setdefault('auth', {})['token'] = gt
    gw.setdefault('remote', {})['token'] = gt
    gw['mode'] = 'local'

# LLM provider from OpenVort DB config
provider = os.environ.get('OPENVORT_LLM_PROVIDER', '')
api_key = os.environ.get('OPENVORT_LLM_API_KEY', '')
api_base = os.environ.get('OPENVORT_LLM_API_BASE', '')
model = os.environ.get('OPENVORT_LLM_MODEL', '')

if api_key:
    # Map OpenVort provider name to OpenClaw model prefix
    prefix_map = {
        'anthropic': 'anthropic',
        'openai': 'openai',
        'deepseek': 'deepseek',
    }
    oc_prefix = prefix_map.get(provider, provider or 'anthropic')
    full_model = f'{oc_prefix}/{model}' if model and '/' not in model else (model or 'anthropic/claude-sonnet-4-20250514')

    # Set agent model
    cfg.setdefault('agents', {}).setdefault('defaults', {}).setdefault('model', {})['primary'] = full_model

    # Set custom provider if base URL is provided
    if api_base:
        api_type_map = {
            'anthropic': 'anthropic-messages',
            'openai': 'openai-completions',
            'deepseek': 'openai-completions',
        }
        cfg.setdefault('models', {})['providers'] = {
            oc_prefix: {
                'baseUrl': api_base,
                'apiKey': api_key,
                'api': api_type_map.get(provider, 'openai-completions'),
                'models': [],
            }
        }
    # Also export as env var for direct SDK usage
    if provider == 'anthropic':
        os.environ['ANTHROPIC_API_KEY'] = api_key
    elif provider == 'openai':
        os.environ['OPENAI_API_KEY'] = api_key

with open('$CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print(f'OpenClaw config applied: model={cfg.get(\"agents\",{}).get(\"defaults\",{}).get(\"model\",{}).get(\"primary\",\"?\")}')
"

# Auto-fix config compatibility issues
openclaw doctor --fix 2>/dev/null || true

# Start the OpenClaw gateway
exec openclaw gateway --port 18789 --verbose --allow-unconfigured
