#!/bin/bash
set -e

# Read options from HA config
CONFIG_PATH=/data/options.json

ANTHROPIC_API_KEY=$(jq --raw-output '.anthropic_api_key' $CONFIG_PATH)
MODEL=$(jq --raw-output '.model // "claude-opus-4-5"' $CONFIG_PATH)

export ANTHROPIC_API_KEY
export MODEL

echo "[Claude Assistant] Starting..."
echo "[Claude Assistant] Model: $MODEL"

exec python3 /app/main.py
