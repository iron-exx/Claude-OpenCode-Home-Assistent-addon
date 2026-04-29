#!/bin/sh
# Config direkt aus HA options.json lesen – kein bashio nötig
export ANTHROPIC_API_KEY=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('anthropic_api_key',''))" 2>/dev/null || echo "")
export MODEL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('model','claude-opus-4-5'))" 2>/dev/null || echo "claude-opus-4-5")

echo "[Claude] Starte... Modell: $MODEL"
exec python3 /app/main.py
