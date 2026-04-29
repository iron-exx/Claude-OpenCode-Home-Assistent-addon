#!/bin/sh
export ANTHROPIC_API_KEY=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('anthropic_api_key',''))" 2>/dev/null || echo "")
export MODEL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('model','claude-opus-4-5'))" 2>/dev/null || echo "claude-opus-4-5")
export PROVIDER=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('provider','anthropic'))" 2>/dev/null || echo "anthropic")
export OPENCODE_URL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('opencode_url',''))" 2>/dev/null || echo "")

echo "[Claude] Starte... Provider: $PROVIDER / Modell: $MODEL"
exec python3 /app/main.py
