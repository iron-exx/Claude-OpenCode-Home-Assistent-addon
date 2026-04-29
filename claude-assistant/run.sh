#!/usr/bin/with-contenv bashio

bashio::log.info "Claude AI Assistant startet..."

# API-Key und Modell aus HA-Konfiguration lesen
export ANTHROPIC_API_KEY=$(bashio::config 'anthropic_api_key')
export MODEL=$(bashio::config 'model')

bashio::log.info "Modell: ${MODEL}"
bashio::log.info "API-Key gesetzt: $([ -n "$ANTHROPIC_API_KEY" ] && echo 'ja' || echo 'FEHLT!')"

exec python3 /app/main.py
