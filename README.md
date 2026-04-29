# Claude AI Assistant – Home Assistant Add-on

Ein Home Assistant Add-on das Claude AI vollständigen Zugriff auf dein Smart Home gibt.
Du chattest direkt im HA-Dashboard und Claude kann alle Geräte steuern, Automationen erstellen und vieles mehr.

---

## 🚀 Installation

### Schritt 1: GitHub Repository erstellen

1. Neues GitHub-Repository erstellen (z.B. `claude-ha-assistant`)
2. Den gesamten Inhalt dieses Ordners hochladen
3. In `claude-assistant/config.yaml` alle Vorkommen von `iron-exx` durch deinen echten GitHub-Username ersetzen
4. In `repository.yaml` ebenfalls anpassen

### Schritt 2: Add-on in Home Assistant hinzufügen

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store**
2. Oben rechts auf die **drei Punkte** → **Repositories**
3. GitHub-URL einfügen: `https://github.com/iron-exx/claude-ha-assistant`
4. **Hinzufügen** → Seite neu laden
5. Das Add-on **"Claude AI Assistant"** erscheint im Store → **Installieren**

### Schritt 3: Konfigurieren

Im Add-on unter **Konfiguration**:
```yaml
anthropic_api_key: "sk-ant-api03-..."  # Dein Anthropic API-Key
model: "claude-opus-4-5"               # Oder claude-sonnet-4-6 für schnellere Antworten
log_level: "info"
```

### Schritt 4: Starten & Öffnen

1. Add-on **Starten**
2. **Im Sidebar öffnen** (erscheint automatisch als "Claude AI" Panel)
3. Fertig! 🎉

---

## 💬 Was kann Claude tun?

### Geräte steuern
- „Schalte alle Lichter im Wohnzimmer aus"
- „Stelle die Heizung auf 21 Grad"
- „Schließe alle Rollläden"
- „Spiele Spotify im Wohnzimmer ab"

### Informationen abrufen
- „Welche Sensoren haben hohe Werte?"
- „Zeige mir den Stromverbrauch der letzten Stunde"
- „Ist jemand zuhause?"

### Automationen erstellen
- „Erstelle eine Automation: Wenn ich nach Hause komme, schalte das Licht an"
- „Mache eine Routine: Jeden Morgen um 7 Uhr Rollläden hoch und Kaffeemaschine an"
- „Wenn Fensterkontakt offen und Temperatur unter 18°C, Heizung ausschalten"

### Szenen & Skripte
- „Aktiviere die Szene 'Filmabend'"
- „Führe das Skript 'Guten Morgen' aus"

---

## 🔧 Manuell ohne GitHub (lokale Installation)

Wenn du kein GitHub nutzen willst, kannst du das Add-on auch lokal installieren:

1. Den Ordner `claude-assistant` auf deinen HA-Host kopieren:
   ```
   /usr/share/hassio/addons/local/claude-assistant/
   ```
2. In HA: **Einstellungen → Add-ons → Add-on Store → Lokale Add-ons neu laden** (drei Punkte oben rechts)
3. Das Add-on erscheint unter "Lokal" → Installieren

---

## 🔒 Sicherheit

- Das Add-on nutzt den **Supervisor-Token** für HA-Zugriff (kein separates Long-Lived-Token nötig)
- Der Anthropic API-Key wird **lokal gespeichert** (in HA-Config oder Browser-LocalStorage)
- Claude läuft **innerhalb** deines HA-Netzwerks, Anfragen gehen nur an `api.anthropic.com`
- Voller Schreibzugriff: Claude kann alles ändern was du auch per UI ändern könntest

---

## 🐋 TrueNAS / Docker (Zukunft)

Für TrueNAS Scale oder normales Docker:

```bash
docker run -d \
  --name claude-ha-assistant \
  -p 8099:8099 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e HA_URL="http://192.168.1.x:8123" \
  -e HA_TOKEN="dein_long_lived_token" \
  ghcr.io/iron-exx/claude-ha-assistant/claude-assistant-amd64:latest
```

*Für TrueNAS müssen `HA_URL` und `HA_TOKEN` als Umgebungsvariablen gesetzt werden,*
*da kein Supervisor-Token verfügbar ist.*

---

## 🛠 Entwicklung / Lokaler Build

```bash
# Docker-Image lokal bauen
cd claude-assistant
docker build -t claude-ha-assistant .

# Testen
docker run -p 8099:8099 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e SUPERVISOR_TOKEN="test" \
  claude-ha-assistant
```

---

## 📋 Verfügbare Tools (was Claude nutzen kann)

| Tool | Beschreibung |
|------|-------------|
| `list_entities` | Alle Entitäten auflisten (filterbar nach Domain) |
| `get_entity_state` | Zustand einer Entität abrufen |
| `call_service` | Beliebigen HA-Service aufrufen |
| `get_areas` | Alle Bereiche/Räume auflisten |
| `create_automation` | Neue Automation erstellen |
| `update_automation` | Bestehende Automation bearbeiten |
| `delete_automation` | Automation löschen |
| `render_template` | Jinja2-Template rendern |
| `get_history` | Verlauf einer Entität abrufen |
| `get_logbook` | Logbuch-Einträge abrufen |
| `get_config` | HA-Systemkonfiguration |
| `fire_event` | Event auslösen |
| `get_scripts` | Skripte auflisten |
| `get_scenes` | Szenen auflisten |
| `get_notifications` | Persistente Benachrichtigungen |
