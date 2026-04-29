# Claude AI Assistant – Home Assistant Add-on

Chat mit KI direkt in deinem Home Assistant Dashboard. Vollständiger Zugriff auf alle Geräte, Automationen und Einstellungen – per natürlicher Sprache.

Zwei KI-Anbieter werden unterstützt: **Anthropic Claude** (API-Key erforderlich) und **OpenCode Big Pickle** (kostenlos, läuft lokal auf deinem PC).

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
Bei neuer Version einfach Script erneut ausführen und Add-on **Neu starten**:
```bash
curl -fsSL https://raw.githubusercontent.com/iron-exx/Claude-Home-Assistent-addon/main/install.sh | bash
```

---

## 🤖 Anbieter 1: Anthropic Claude

Claude ist das KI-Modell von Anthropic. Es benötigt einen API-Key und verbraucht Token (kostenpflichtig, aber sehr günstig).

### API-Key besorgen
1. Gehe zu **[console.anthropic.com](https://console.anthropic.com)**
2. Account erstellen oder einloggen
3. Links im Menü: **API Keys → Create Key**
4. Key kopieren – er sieht so aus: `sk-ant-api03-...`
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

OpenCode ist ein Open-Source KI-Tool das **lokal auf deinem PC** läuft. Das Modell „Big Pickle" ist komplett **kostenlos** – kein API-Key, keine Limits, keine Kosten.

Das HA Add-on verbindet sich per Netzwerk mit dem OpenCode-Server auf deinem PC. Der PC muss laufen und im selben Netzwerk sein solange du den Assistenten nutzen willst.

### Schritt 1: OpenCode installieren

**Voraussetzung:** Node.js muss installiert sein → [nodejs.org](https://nodejs.org)

**Windows / macOS / Linux:**
```bash
npm install -g opencode-ai
```

Installation testen:
```bash
opencode --version
```

### Schritt 2: OpenCode Server starten

#### Windows – Einfachste Methode:
Die Datei **`opencode-scripts/start-opencode-windows.bat`** aus diesem Repository herunterladen und **doppelklicken**. Das Fenster muss offen bleiben.

#### Windows – Manuell im Terminal:
```cmd
opencode serve --hostname 0.0.0.0 --port 4096
```

#### Linux / macOS:
```bash
opencode serve --hostname 0.0.0.0 --port 4096
```

Du siehst dann:
```
Server listening on http://0.0.0.0:4096
```

**Wichtig:** `--hostname 0.0.0.0` ist nötig damit das HA Add-on den Server aus dem Netzwerk erreichen kann. Ohne diese Option ist der Server nur lokal auf dem PC erreichbar.

### Schritt 3: IP-Adresse des PCs herausfinden

**Windows:**
```cmd
ipconfig
```
→ Suche nach „IPv4-Adresse" z.B. `192.168.1.50`

**Linux / macOS:**
```bash
hostname -I
```

### Schritt 4: Im Add-on eintragen
1. Add-on öffnen → ⚙ Einstellungen
2. Tab **„OpenCode Big Pickle"** wählen
3. URL eintragen: `192.168.1.50:4096` (deine PC-IP, kein http:// nötig)
4. Fertig – kein Modell auswählen nötig, Big Pickle wird automatisch verwendet

### OpenCode automatisch beim PC-Start starten

#### Windows (empfohlen):
PowerShell als **Administrator** öffnen und ausführen:
```powershell
# Aus dem opencode-scripts Ordner dieses Repos:
.\start-opencode-autostart-windows.ps1
```
Oder manuell:
```powershell
$Action = New-ScheduledTaskAction -Execute "opencode" -Argument "serve --hostname 0.0.0.0 --port 4096"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "OpenCode HA Server" -Action $Action -Trigger $Trigger -Settings $Settings -Force
```

#### Linux (systemd):
```bash
sudo nano /etc/systemd/system/opencode-ha.service
```
Inhalt:
```ini
[Unit]
Description=OpenCode Big Pickle – Home Assistant Server
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

---

## 💬 Was kann der Assistent tun?

- **Geräte steuern** – „Schalte alle Lichter im Wohnzimmer aus"
- **Automationen erstellen** – „Wenn ich nach Hause komme, schalte das Licht an"
- **Sensordaten** – „Zeige mir den Stromverbrauch der letzten Stunde"
- **Szenen & Skripte** – „Aktiviere die Szene Filmabend"
- **Status abfragen** – „Welche Geräte sind gerade eingeschaltet?"
- **Alles kombinieren** – „Erstelle eine Automation: Rollläden auf bei Sonnenaufgang, aber nur wenn wir zuhause sind"

---

## 📋 Verfügbare HA-Tools

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

---

## 🔒 Sicherheit

- Der Anthropic API-Key wird nur im Browser gespeichert (localStorage), nie auf dem Server
- Das Add-on nutzt den HA-Supervisor-Token für API-Zugriff – kein separates Token nötig
- OpenCode läuft vollständig lokal – keine Daten verlassen dein Netzwerk
- Für OpenCode empfiehlt sich ein Passwort: `OPENCODE_SERVER_PASSWORD=geheim opencode serve --hostname 0.0.0.0 --port 4096`
