@echo off
title OpenCode Server fuer Home Assistant
echo ================================================
echo   OpenCode Big Pickle - Home Assistant Server
echo ================================================
echo.
echo Starte OpenCode Server auf Port 4096...
echo Erreichbar im Netzwerk unter: http://%COMPUTERNAME%:4096
echo.
echo Im HA Add-on eintragen: %COMPUTERNAME%:4096
echo (oder deine IP-Adresse statt %COMPUTERNAME%)
echo.
echo Fenster offen lassen solange HA zugreifen soll.
echo Mit Strg+C beenden.
echo ================================================
opencode serve --hostname 0.0.0.0 --port 4096
pause
