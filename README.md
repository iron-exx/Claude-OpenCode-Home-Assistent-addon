# Claude AI Assistant – Home Assistant Add-on

Chat mit KI direkt in deinem Home Assistant Dashboard. Vollständiger Zugriff auf alle Geräte, Automationen, Template-Sensoren, Skripte und Szenen – per natürlicher Sprache.

Zwei KI-Anbieter werden unterstützt: **Anthropic Claude** (API-Key erforderlich) und **OpenCode Big Pickle** (kostenlos, läuft lokal auf einem Server/PC im Netzwerk).

---

## 🚀 Installation des Add-ons

### Schritt 1: Terminal Add-on installieren
In Home Assistant:
**Einstellungen → Add-ons → Add-on Store → „Terminal & SSH" → Installieren → Starten**

### Schritt 2: Install-Script ausführen
Im Terminal einmal einfügen und Enter drücken:

```bash
curl -fsSL https://raw.githubusercontent.com/iron-exx/Claude-Home-Assistent-addon/main/install.sh | bash
```

### Schritt 3: Add-on laden
**Add-on Store → drei Punkte oben rechts → Lokale Add-ons neu laden**
→ „Claude AI Assistant" erscheint unter **Lokal** → **Installieren**

### Schritt 4: Starten
→ Add-on **Starten** → erscheint in der HA-Sidebar als **„Claude AI"**
→ Im Add-on oben rechts auf **⚙ Einstellungen** klicken und KI-Anbieter wählen

### Updates einspielen
Script erneut ausführen und Add-on **Neu starten** – kein Rebuild nötig:
```bash
curl -fsSL https://raw.githubusercontent.com/iron-exx/Claude-Home-Assistent-addon/main/install.sh | bash
```

---

## 🤖 Anbieter 1: Anthropic Claude

Claude ist das KI-Modell von Anthropic. Benötigt einen API-Key und verbraucht Token (kostenpflichtig, aber sehr günstig).

### API-Key besorgen
1. Gehe zu **[console.anthropic.com](https://console.anthropic.com)**
2. Account erstellen oder einloggen
3. Links im Menü: **API Keys → Create Key**
4. Key kopieren – sieht so aus: `sk-ant-api03-...`
5. Guthaben aufladen unter **Billing** (min. $5 empfohlen)

### Im Add-on eintragen
1. Add-on öffnen → ⚙ Einstellungen
2. Tab **„Anthropic Claude"** wählen
3. API-Key einfügen
4. Modell auswählen:
   - **Claude Sonnet 4.6** – Empfohlen, schnell und günstig
   - **Claude Opus 4.5** – Leistungsstärker, teurer
   - **Claude Haiku 4.5** – Sehr günstig, für einfache Befehle

### Kosten
Für normalen Heimgebrauch (10–20 Befehle täglich) reichen **$5 für mehrere Monate**.

---

## 🥒 Anbieter 2: OpenCode Big Pickle (kostenlos)

OpenCode ist ein Open-Source KI-Tool das **lokal auf einem Server oder PC** läuft. Das Modell „Big Pickle" ist komplett **kostenlos** – kein API-Key, keine Limits, keine Kosten.

Das HA Add-on verbindet sich per Netzwerk mit dem OpenCode-Server. Der Server muss laufen und im selben Netzwerk wie Home Assistant sein.

### Schritt 1: Node.js installieren
**Voraussetzung:** Node.js muss installiert sein → [nodejs.org](https://nodejs.org)

### Schritt 2: OpenCode installieren
```bash
npm install -g opencode-ai
```
Installation testen:
```bash
opencode --version
```

### Schritt 3: OpenCode Server starten

#### Manuell (Terminal muss offen bleiben):
```bash
opencode serve --hostname 0.0.0.0 --port 4096
```

**Wichtig:** `--hostname 0.0.0.0` ist nötig damit das HA Add-on den Server aus dem Netzwerk erreichen kann.

#### Linux – Dauerhaft als Systemdienst (empfohlen):
So läuft OpenCode automatisch im Hintergrund – auch nach Neustart, Terminal kann geschlossen werden.

```bash
# Schritt 1: Richtigen Pfad ermitteln
which opencode
# Typische Ausgabe: /home/BENUTZER/.opencode/bin/opencode

# Schritt 2: Dienst anlegen (Pfad wird automatisch gesetzt)
OPENCODE_PATH=$(which opencode)
sudo bash -c "cat > /etc/systemd/system/opencode-ha.service << EOF
[Unit]
Description=OpenCode Big Pickle – Home Assistant Server
After=network.target

[Service]
ExecStart=$OPENCODE_PATH serve --hostname 0.0.0.0 --port 4096
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF"

# Schritt 3: Aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable --now opencode-ha
sudo systemctl status opencode-ha
```

✅ Bei Erfolg: `Active: active (running)`

> **Wichtig:** Nicht `/usr/local/bin/opencode` als Pfad hardcoden – OpenCode wird meist unter `~/.opencode/bin/opencode` installiert. Immer `which opencode` zur Überprüfung nutzen.

Nützliche Befehle:
```bash
sudo systemctl status opencode-ha    # Status prüfen
sudo journalctl -u opencode-ha -f    # Logs live ansehen
sudo systemctl restart opencode-ha   # Neustarten
sudo systemctl stop opencode-ha      # Stoppen
```

#### Windows – Manuell:
Doppelklick auf `opencode-scripts/start-opencode-windows.bat` aus diesem Repository. Das Fenster muss offen bleiben.

#### Windows – Autostart beim Login:
PowerShell als **Administrator** öffnen:
```powershell
$Action = New-ScheduledTaskAction -Execute "opencode" -Argument "serve --hostname 0.0.0.0 --port 4096"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "OpenCode HA Server" -Action $Action -Trigger $Trigger -Settings $Settings -Force
```

### Schritt 4: IP-Adresse herausfinden

**Linux:**
```bash
hostname -I
```
**Windows:**
```cmd
ipconfig
```
→ „IPv4-Adresse" z.B. `192.168.1.50`

### Schritt 5: Im Add-on eintragen
1. Add-on öffnen → ⚙ Einstellungen
2. Tab **„OpenCode Big Pickle"** wählen
3. URL eintragen: `192.168.1.50:4096` (deine Server-IP, kein `http://` nötig)
4. Fertig – kein Modell auswählen nötig, Big Pickle wird automatisch verwendet

---

## 💬 Was kann der Assistent tun?

- **Geräte steuern** – „Schalte alle Lichter im Wohnzimmer aus"
- **Automationen erstellen** – „Wenn ich nach Hause komme, schalte das Licht an"
- **Template-Sensoren erstellen** – „Erstelle einen Sensor der PV-Leistung und Balkonstrom addiert"
- **Skripte & Szenen** – „Erstelle ein Skript für den Filmabend"
- **Sensordaten abrufen** – „Zeige mir den Stromverbrauch der letzten Stunde"
- **Alles neu laden** – Änderungen werden direkt in HA übernommen ohne Neustart
- **Verlauf** – Chats werden gespeichert und können links in der Sidebar wieder geöffnet werden

---

## 📋 Verfügbare HA-Tools (Anthropic Claude)

| Tool | Beschreibung |
|------|-------------|
| `list_entities` | Alle Entitäten auflisten |
| `get_entity_state` | Zustand einer Entität abrufen |
| `call_service` | Beliebigen HA-Service aufrufen |
| `get_areas` | Bereiche/Räume auflisten |
| `create_automation` | Neue Automation in automations.yaml schreiben |
| `update_automation` | Automation bearbeiten |
| `delete_automation` | Automation löschen |
| `render_template` | Jinja2-Template rendern |
| `get_history` | Zustandsverlauf abrufen |
| `get_logbook` | Logbuch abrufen |
| `fire_event` | Event auslösen |
| `get_scripts` | Skripte auflisten |
| `get_scenes` | Szenen auflisten |

## 📋 Was OpenCode direkt in HA schreiben kann

| Aktion | Zieldatei |
|--------|-----------|
| Automation erstellen | `/config/automations.yaml` |
| Template-Sensor erstellen | `/config/template.yaml` |
| Skript erstellen | `/config/scripts.yaml` |
| Szene erstellen | `/config/scenes.yaml` |
| Gerät steuern | HA-Service direkt |
| Komponente neu laden | `automation/template/script/scene` |
| HA neu starten | `homeassistant.restart` |

---

## 🔒 Sicherheit

- Der Anthropic API-Key wird nur im Browser gespeichert (localStorage), nie auf dem Server
- Das Add-on nutzt den HA-Supervisor-Token – kein separates Long-Lived-Token nötig
- OpenCode läuft vollständig lokal – keine Daten verlassen dein Netzwerk
- Chats werden in `/data/sessions/` im Add-on gespeichert und bleiben nach Neustart erhalten
- Für OpenCode empfiehlt sich ein Passwort: `OPENCODE_SERVER_PASSWORD=geheim opencode serve --hostname 0.0.0.0 --port 4096`
