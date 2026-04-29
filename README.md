# Claude AI Assistant – Home Assistant Add-on

Chat mit Claude AI direkt in deinem Home Assistant Dashboard. Claude hat vollen Zugriff auf alle Geräte, Automationen und Einstellungen.

---

## 🚀 Installation (lokal, empfohlen)

### Schritt 1: Terminal Add-on installieren
→ **Add-on Store → „Terminal & SSH" → Installieren → Starten**

### Schritt 2: Install-Script ausführen
Im Terminal einmal einfügen:

```bash
curl -fsSL https://raw.githubusercontent.com/iron-exx/Claude-Home-Assistent-addon/main/install.sh | bash
```

### Schritt 3: Add-on laden
→ **Add-on Store → drei Punkte → Lokale Add-ons neu laden**
→ „Claude AI Assistant" erscheint unter **Lokal** → **Installieren**

### Schritt 4: API-Key eintragen & starten
→ Add-on → **Konfiguration** → `anthropic_api_key` eintragen
→ **Starten** → erscheint in der Sidebar als **„Claude AI"**

---

## 💬 Was kann Claude tun?

- **Geräte steuern** – „Schalte alle Lichter im Wohnzimmer aus"
- **Automationen erstellen** – „Wenn ich nach Hause komme, schalte das Licht an"
- **Sensordaten abrufen** – „Zeige mir den Stromverbrauch der letzten Stunde"
- **Szenen & Skripte** – „Aktiviere die Szene Filmabend"
- **Alles ändern** – vollständiger Schreib- und Lesezugriff

---

## 🔑 Anthropic API-Key

Erhältlich unter: https://console.anthropic.com

---

## 🔄 Update

Bei neuer Version einfach das Script erneut ausführen und **Rebuild** klicken:

```bash
curl -fsSL https://raw.githubusercontent.com/iron-exx/Claude-Home-Assistent-addon/main/install.sh | bash
```

---

## 📋 Verfügbare Tools

| Tool | Beschreibung |
|------|-------------|
| `list_entities` | Alle Entitäten auflisten |
| `get_entity_state` | Zustand einer Entität abrufen |
| `call_service` | Beliebigen HA-Service aufrufen |
| `get_areas` | Bereiche/Räume auflisten |
| `create_automation` | Neue Automation erstellen |
| `update_automation` | Automation bearbeiten |
| `delete_automation` | Automation löschen |
| `render_template` | Jinja2-Template rendern |
| `get_history` | Verlauf abrufen |
| `get_logbook` | Logbuch abrufen |
| `fire_event` | Event auslösen |
| `get_scripts` | Skripte auflisten |
| `get_scenes` | Szenen auflisten |
