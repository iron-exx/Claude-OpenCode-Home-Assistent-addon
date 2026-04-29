#!/bin/bash
echo "================================================"
echo "  OpenCode Big Pickle - Home Assistant Server"
echo "================================================"
echo ""
IP=$(hostname -I | awk '{print $1}')
echo "Starte OpenCode Server auf Port 4096..."
echo "Erreichbar unter: http://$IP:4096"
echo ""
echo "Im HA Add-on eintragen: $IP:4096"
echo ""
echo "Mit Strg+C beenden."
echo "================================================"
opencode serve --hostname 0.0.0.0 --port 4096
