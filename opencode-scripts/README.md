# OpenCode Startup Scripts

## Installation OpenCode

```bash
npm install -g opencode-ai
```

## Windows

### Manuell starten
Doppelklick auf `start-opencode-windows.bat`

### Automatisch beim Start (als Administrator):
```powershell
.\start-opencode-autostart-windows.ps1
```

## Linux / macOS

```bash
chmod +x start-opencode-linux.sh
./start-opencode-linux.sh
```

### Autostart Linux (systemd):
```bash
sudo nano /etc/systemd/system/opencode-ha.service
```
Inhalt:
```
[Unit]
Description=OpenCode HA Server
After=network.target

[Service]
ExecStart=opencode serve --hostname 0.0.0.0 --port 4096
Restart=always
User=DEIN_USERNAME

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now opencode-ha
```

## Im HA Add-on eintragen

1. Add-on öffnen → ⚙ Einstellungen
2. Provider: **OpenCode Big Pickle** wählen
3. URL eintragen: `192.168.x.x:4096` (deine PC-IP)
