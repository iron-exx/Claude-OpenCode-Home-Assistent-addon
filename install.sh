#!/bin/bash
set -e
BASE="/addons/local/claude-assistant"
echo "=== Claude HA Assistant – Update ==="
mkdir -p "$BASE/app/templates" "$BASE/app/static"

cat > "$BASE/config.yaml" << 'CLAUDE_EOF_CONFIG_YAML'
name: "Claude AI Assistant"
description: "Chat mit Claude AI – steuert dein Home Assistant vollständig per natürlicher Sprache."
version: "1.0.0"
slug: "claude_assistant"
url: "https://github.com/iron-exx/claude-ha-assistant"
arch:
  - aarch64
  - amd64
  - armhf
  - armv7
  - i386

ingress: true
ingress_port: 8099
panel_icon: "mdi:robot"
panel_title: "Claude AI"

# HA API Zugriff
homeassistant_api: true
hassio_api: true
hassio_role: manager

options:
  provider: "anthropic"
  anthropic_api_key: ""
  model: "claude-opus-4-5"
  opencode_url: "http://192.168.1.x:4096"
  log_level: "info"

schema:
  provider: list(anthropic|opencode)
  anthropic_api_key: str
  model: str
  opencode_url: str
  log_level: list(trace|debug|info|notice|warning|error|fatal)

map:
  - config:rw



CLAUDE_EOF_CONFIG_YAML

cat > "$BASE/build.yaml" << 'CLAUDE_EOF_BUILD_YAML'
build_from:
  aarch64: "ghcr.io/home-assistant/aarch64-base-python:3.11-alpine3.18"
  amd64: "ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18"
  armhf: "ghcr.io/home-assistant/armhf-base-python:3.11-alpine3.18"
  armv7: "ghcr.io/home-assistant/armv7-base-python:3.11-alpine3.18"
  i386: "ghcr.io/home-assistant/i386-base-python:3.11-alpine3.18"

CLAUDE_EOF_BUILD_YAML

cat > "$BASE/Dockerfile" << 'CLAUDE_EOF_DOCKERFILE'
ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache jq

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# run.sh direkt als PID 1 – kein s6-overlay
ENTRYPOINT ["/run.sh"]

CLAUDE_EOF_DOCKERFILE

cat > "$BASE/run.sh" << 'CLAUDE_EOF_RUN_SH'
#!/bin/sh
export ANTHROPIC_API_KEY=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('anthropic_api_key',''))" 2>/dev/null || echo "")
export MODEL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('model','claude-opus-4-5'))" 2>/dev/null || echo "claude-opus-4-5")
export PROVIDER=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('provider','anthropic'))" 2>/dev/null || echo "anthropic")
export OPENCODE_URL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('opencode_url',''))" 2>/dev/null || echo "")

echo "[Claude] Starte... Provider: $PROVIDER / Modell: $MODEL"
exec python3 /app/main.py

CLAUDE_EOF_RUN_SH

cat > "$BASE/app/requirements.txt" << 'CLAUDE_EOF_APP_REQUIREMENTS_TXT'
flask==3.0.3
anthropic>=0.49.0
requests==2.32.3
pyyaml>=6.0

CLAUDE_EOF_APP_REQUIREMENTS_TXT

cat > "$BASE/app/main.py" << 'CLAUDE_EOF_APP_MAIN_PY'
#!/usr/bin/env python3
"""
Claude AI Assistant for Home Assistant
Vollständiger HA-Zugriff via Anthropic API mit Tool Use
"""

import os
import json
import logging
import requests
from flask import Flask, request, jsonify, render_template

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")

@app.errorhandler(Exception)
def handle_exception(e):
    log.error(f"Unbehandelte Exception: {e}", exc_info=True)
    return jsonify({"error": f"Server-Fehler: {str(e)}"}), 500

# ─── HA API Konfiguration ─────────────────────────────────────────────────────
HA_TOKEN   = os.environ.get("SUPERVISOR_TOKEN", "")
HA_API     = "http://supervisor/core/api"
ADDON_API  = "http://supervisor"

DEFAULT_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL    = os.environ.get("MODEL", "claude-opus-4-5")
DEFAULT_PROVIDER = os.environ.get("PROVIDER", "anthropic")
DEFAULT_OPENCODE_URL = os.environ.get("OPENCODE_URL", "")

# ─── Tool-Definitionen ────────────────────────────────────────────────────────
HA_TOOLS = [
    {
        "name": "list_entities",
        "description": (
            "Listet alle Home Assistant Entitäten mit aktuellem Zustand auf. "
            "Kann nach Domain gefiltert werden (z.B. 'light', 'switch', 'sensor', "
            "'climate', 'automation', 'cover', 'media_player', 'person')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Optionale Domain zum Filtern, z.B. 'light' oder 'switch'"
                },
                "area": {
                    "type": "string",
                    "description": "Optionaler Bereich/Raum zum Filtern"
                }
            }
        }
    },
    {
        "name": "get_entity_state",
        "description": "Gibt den aktuellen Zustand und alle Attribute einer bestimmten Entität zurück.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Die Entity-ID, z.B. 'light.wohnzimmer' oder 'sensor.temperatur_aussen'"
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "call_service",
        "description": (
            "Ruft einen Home Assistant Service auf, um Geräte zu steuern oder Aktionen auszulösen. "
            "Beispiele: Lichter ein-/ausschalten, Temperatur setzen, Automationen auslösen, "
            "Szenen aktivieren, Rollläden steuern, Musik abspielen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Service-Domain, z.B. 'light', 'switch', 'climate', 'automation', 'media_player', 'cover'"
                },
                "service": {
                    "type": "string",
                    "description": "Service-Name, z.B. 'turn_on', 'turn_off', 'toggle', 'set_temperature', 'play_media'"
                },
                "service_data": {
                    "type": "object",
                    "description": (
                        "Service-Daten/Parameter als Objekt. "
                        "Beispiel: {\"entity_id\": \"light.wohnzimmer\", \"brightness\": 200, \"color_temp\": 4000}"
                    )
                }
            },
            "required": ["domain", "service"]
        }
    },
    {
        "name": "get_areas",
        "description": "Listet alle definierten Bereiche/Räume in Home Assistant auf.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_devices",
        "description": "Listet alle registrierten Geräte/Devices in Home Assistant auf.",
        "input_schema": {
            "type": "object",
            "properties": {
                "area_id": {
                    "type": "string",
                    "description": "Optionale Area-ID zum Filtern"
                }
            }
        }
    },
    {
        "name": "create_automation",
        "description": (
            "Erstellt eine neue Automation in Home Assistant. "
            "Trigger, Bedingungen und Aktionen werden als strukturierte Daten übergeben."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alias": {
                    "type": "string",
                    "description": "Name der Automation"
                },
                "description": {
                    "type": "string",
                    "description": "Beschreibung der Automation"
                },
                "mode": {
                    "type": "string",
                    "description": "Ausführungsmodus: 'single', 'restart', 'queued', 'parallel'"
                },
                "trigger": {
                    "type": "array",
                    "description": "Liste von Triggern als HA-konforme Objekte"
                },
                "condition": {
                    "type": "array",
                    "description": "Optionale Liste von Bedingungen"
                },
                "action": {
                    "type": "array",
                    "description": "Liste von Aktionen"
                }
            },
            "required": ["alias", "trigger", "action"]
        }
    },
    {
        "name": "update_automation",
        "description": "Aktualisiert eine bestehende Automation anhand ihrer ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "automation_id": {
                    "type": "string",
                    "description": "Die ID der Automation (aus create_automation oder get_automations)"
                },
                "alias": {"type": "string"},
                "description": {"type": "string"},
                "trigger": {"type": "array"},
                "condition": {"type": "array"},
                "action": {"type": "array"},
                "mode": {"type": "string"}
            },
            "required": ["automation_id"]
        }
    },
    {
        "name": "delete_automation",
        "description": "Löscht eine Automation anhand ihrer ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "automation_id": {
                    "type": "string",
                    "description": "Die ID der zu löschenden Automation"
                }
            },
            "required": ["automation_id"]
        }
    },
    {
        "name": "render_template",
        "description": "Rendert ein Home Assistant Jinja2-Template und gibt das Ergebnis zurück. Nützlich für berechnete Werte.",
        "input_schema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "description": "Das Jinja2-Template, z.B. '{{ states(\"sensor.temperatur\") }}'"
                }
            },
            "required": ["template"]
        }
    },
    {
        "name": "get_history",
        "description": "Gibt den Zustandsverlauf einer Entität zurück (max. letzte 24 Stunden).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Die Entity-ID"
                },
                "hours": {
                    "type": "number",
                    "description": "Anzahl der Stunden zurück (Standard: 1, max: 24)"
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "get_logbook",
        "description": "Gibt Logbuch-Einträge zurück (Ereignisse, Zustandsänderungen).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Optionale Entity-ID zum Filtern"
                },
                "hours": {
                    "type": "number",
                    "description": "Stunden zurück (Standard: 1)"
                }
            }
        }
    },
    {
        "name": "get_config",
        "description": "Gibt die Home Assistant Systemkonfiguration zurück (Version, Standort, Zeitzone, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fire_event",
        "description": "Löst ein benutzerdefiniertes Home Assistant Ereignis aus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "Der Event-Typ, z.B. 'custom_button_pressed'"
                },
                "event_data": {
                    "type": "object",
                    "description": "Optionale Event-Daten"
                }
            },
            "required": ["event_type"]
        }
    },
    {
        "name": "get_scripts",
        "description": "Listet alle Skripte in Home Assistant auf.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_scenes",
        "description": "Listet alle Szenen in Home Assistant auf.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_notifications",
        "description": "Gibt die letzten persistenten Benachrichtigungen zurück.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]


# ─── HA API Helfer ────────────────────────────────────────────────────────────
def _ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }


def ha_get(endpoint: str) -> dict | list:
    url = f"{HA_API}{endpoint}"
    r = requests.get(url, headers=_ha_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def ha_post(endpoint: str, data: dict = None) -> dict | list:
    url = f"{HA_API}{endpoint}"
    r = requests.post(url, headers=_ha_headers(), json=data or {}, timeout=15)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}


def ha_delete(endpoint: str) -> dict:
    url = f"{HA_API}{endpoint}"
    r = requests.delete(url, headers=_ha_headers(), timeout=15)
    r.raise_for_status()
    return {"deleted": True}


# ─── Tool-Ausführung ──────────────────────────────────────────────────────────
def execute_tool(name: str, inp: dict) -> str:
    log.info(f"Executing tool: {name} | input: {json.dumps(inp)[:200]}")
    try:
        # ── list_entities ────────────────────────────────────────────────────
        if name == "list_entities":
            states = ha_get("/states")
            domain = inp.get("domain")
            if domain:
                states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
            result = [
                f"{s['entity_id']}={s['state']} ({s['attributes'].get('friendly_name','')})"
                for s in states
            ]
            return json.dumps(result[:60], ensure_ascii=False)

        # ── get_entity_state ─────────────────────────────────────────────────
        elif name == "get_entity_state":
            entity_id = inp["entity_id"]
            state = ha_get(f"/states/{entity_id}")
            return json.dumps(state, ensure_ascii=False)

        # ── call_service ─────────────────────────────────────────────────────
        elif name == "call_service":
            domain = inp["domain"]
            service = inp["service"]
            service_data = inp.get("service_data", {})
            result = ha_post(f"/services/{domain}/{service}", service_data)
            return json.dumps({"success": True, "changed_states": len(result) if isinstance(result, list) else 0}, ensure_ascii=False)

        # ── get_areas ────────────────────────────────────────────────────────
        elif name == "get_areas":
            try:
                result = ha_post("/template", {"template": "{{ areas() | tojson }}"})
                if isinstance(result, str):
                    areas = json.loads(result)
                else:
                    areas = result
                enriched = []
                for area_id in areas:
                    area_name = ha_post("/template", {"template": f"{{{{ area_name('{area_id}') }}}}"})
                    enriched.append({"id": area_id, "name": area_name if isinstance(area_name, str) else area_id})
                return json.dumps(enriched, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)})

        # ── get_devices ──────────────────────────────────────────────────────
        elif name == "get_devices":
            # Use template to get device registry info
            template = "{{ device_attr(d, 'name') ~ '|' ~ d for d in integration_entities('homeassistant') }}"
            states = ha_get("/states")
            devices_seen = {}
            for s in states:
                name_attr = s["attributes"].get("friendly_name", s["entity_id"])
                domain = s["entity_id"].split(".")[0]
                if domain not in devices_seen:
                    devices_seen[domain] = []
                devices_seen[domain].append(s["entity_id"])
            return json.dumps(devices_seen, ensure_ascii=False)

        # ── create_automation ────────────────────────────────────────────────
        elif name == "create_automation":
            import yaml as _yaml
            import time as _time
            automation = {
                "alias": inp["alias"],
                "description": inp.get("description", ""),
                "mode": inp.get("mode", "single"),
                "trigger": inp["trigger"],
                "action": inp["action"],
            }
            if "condition" in inp:
                automation["condition"] = inp["condition"]
            # In /homeassistant/automations.yaml anhängen
            automations_file = "/config/automations.yaml"
            # Bestehende Automationen lesen
            existing = []
            if os.path.exists(automations_file):
                with open(automations_file, "r", encoding="utf-8") as f:
                    existing = _yaml.safe_load(f) or []
            if not isinstance(existing, list):
                existing = []
            existing.append(automation)
            with open(automations_file, "w", encoding="utf-8") as f:
                _yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)
            # Automationen neu laden
            ha_post("/services/automation/reload", {})
            return json.dumps({"success": True, "file": automations_file, "message": f"Automation '{inp['alias']}' in automations.yaml geschrieben und geladen."}, ensure_ascii=False)

        # ── update_automation ────────────────────────────────────────────────
        elif name == "update_automation":
            auto_id = inp.pop("automation_id")
            # Try REST API first, fallback message if not available
            try:
                result = ha_post(f"/config/automation/config/{auto_id}", inp)
                return json.dumps({"success": True, "result": result}, ensure_ascii=False)
            except Exception:
                return json.dumps({"error": "Update via ID nicht möglich. Bitte Automation löschen und neu erstellen."}, ensure_ascii=False)

        # ── delete_automation ────────────────────────────────────────────────
        elif name == "delete_automation":
            auto_id = inp["automation_id"]
            result = ha_delete(f"/config/automation/config/{auto_id}")
            return json.dumps({"success": True, "message": f"Automation {auto_id} gelöscht."}, ensure_ascii=False)

        # ── render_template ──────────────────────────────────────────────────
        elif name == "render_template":
            result = ha_post("/template", {"template": inp["template"]})
            return str(result)

        # ── get_history ──────────────────────────────────────────────────────
        elif name == "get_history":
            from datetime import datetime, timedelta
            hours = min(float(inp.get("hours", 1)), 24)
            start = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            entity_id = inp["entity_id"]
            result = ha_get(f"/history/period/{start}?filter_entity_id={entity_id}&minimal_response=true&no_attributes=true")
            if isinstance(result, list) and len(result) > 0:
                history = result[0][:50]  # max 50 Einträge
                return json.dumps(history, ensure_ascii=False)
            return json.dumps([])

        # ── get_logbook ──────────────────────────────────────────────────────
        elif name == "get_logbook":
            from datetime import datetime, timedelta
            hours = min(float(inp.get("hours", 1)), 6)
            start = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            entity_id = inp.get("entity_id")
            url = f"/logbook/{start}"
            if entity_id:
                url += f"?entity={entity_id}"
            result = ha_get(url)
            return json.dumps(result[:30] if isinstance(result, list) else result, ensure_ascii=False)

        # ── get_config ───────────────────────────────────────────────────────
        elif name == "get_config":
            result = ha_get("/config")
            return json.dumps(result, ensure_ascii=False)

        # ── fire_event ───────────────────────────────────────────────────────
        elif name == "fire_event":
            event_type = inp["event_type"]
            event_data = inp.get("event_data", {})
            ha_post(f"/events/{event_type}", event_data)
            return json.dumps({"success": True, "fired": event_type})

        # ── get_scripts ──────────────────────────────────────────────────────
        elif name == "get_scripts":
            states = ha_get("/states")
            scripts = [
                {"entity_id": s["entity_id"], "name": s["attributes"].get("friendly_name", s["entity_id"]), "state": s["state"]}
                for s in states if s["entity_id"].startswith("script.")
            ]
            return json.dumps(scripts, ensure_ascii=False)

        # ── get_scenes ───────────────────────────────────────────────────────
        elif name == "get_scenes":
            states = ha_get("/states")
            scenes = [
                {"entity_id": s["entity_id"], "name": s["attributes"].get("friendly_name", s["entity_id"])}
                for s in states if s["entity_id"].startswith("scene.")
            ]
            return json.dumps(scenes, ensure_ascii=False)

        # ── get_notifications ────────────────────────────────────────────────
        elif name == "get_notifications":
            result = ha_get("/persistent_notification")
            return json.dumps(result, ensure_ascii=False)

        else:
            return json.dumps({"error": f"Unbekanntes Tool: {name}"})

    except requests.HTTPError as e:
        log.error(f"HA API HTTP error in {name}: {e}")
        return json.dumps({"error": f"HA API Fehler: {e.response.status_code} – {e.response.text[:300]}"})
    except Exception as e:
        log.error(f"Tool {name} error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


# ─── System-Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Du bist ein Home Assistant KI-Assistent mit vollem Zugriff. Antworte kurz und direkt. Führe Aktionen sofort aus. Antworte auf Deutsch oder Englisch je nach Nutzer. Nur bei destruktiven Massenaktionen kurz nachfragen."""



# ─── OpenCode Provider ────────────────────────────────────────────────────────
def chat_with_opencode(messages: list, opencode_url: str) -> dict:
    """Chat via OpenCode local server API"""
    opencode_url = opencode_url.strip().rstrip("/.").rstrip("/")
    if not opencode_url.startswith("http"):
        opencode_url = "http://" + opencode_url
    base = opencode_url
    
    # 1. Neue Session erstellen
    r = requests.post(f"{base}/session", json={}, timeout=10)
    r.raise_for_status()
    session_id = r.json()["id"]
    log.info(f"OpenCode Session: {session_id}")
    
    # 2. Letzten User-Message extrahieren
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            user_text = msg["content"]
            break
    
    # Bisherige Konversation als Kontext einbauen
    history_text = ""
    for msg in messages[:-1]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            history_text += f"{role.upper()}: {content}\n"
    
    # System-Kontext an User-Message anhängen wenn History vorhanden
    full_prompt = user_text
    if history_text:
        full_prompt = f"[Bisheriger Verlauf:]\n{history_text}\n[Aktuelle Frage:] {user_text}"
    
    # 3. Nachricht senden mit HA-System-Prompt
    ha_system = f"""{SYSTEM_PROMPT}

WICHTIG: Wenn du HA-Aktionen ausführen willst, schreibe sie als JSON-Block so:
<ha_action>
{{"domain": "light", "service": "turn_on", "data": {{"entity_id": "light.beispiel"}}}}
</ha_action>

Für mehrere Aktionen mehrere solche Blöcke. Für Automationen:
<ha_automation>
{{"alias": "Name", "trigger": [...], "action": [...]}}
</ha_automation>"""

    payload = {
        "parts": [
            {"type": "text", "text": ha_system + "\n\n" + full_prompt}
        ],
        "model": {"providerID": "opencode", "modelID": "big-pickle"}
    }
    
    r = requests.post(f"{base}/session/{session_id}/message", json=payload, timeout=180)
    r.raise_for_status()
    response_data = r.json()
    
    # 4. Text aus Response-Parts extrahieren
    response_text = ""
    for part in response_data.get("parts", []):
        if part.get("type") == "text":
            response_text += part.get("text", "")
        elif isinstance(part.get("content"), str):
            response_text += part["content"]
    
    # 5. HA-Aktionen aus Response parsen und ausführen
    import re
    tool_calls = []
    
    # Parse <ha_action> blocks
    for match in re.finditer(r'<ha_action>(.*?)</ha_action>', response_text, re.DOTALL):
        try:
            action = json.loads(match.group(1).strip())
            result = execute_tool("call_service", {
                "domain": action["domain"],
                "service": action["service"],
                "service_data": action.get("data", {})
            })
            tool_calls.append({"tool": f"{action['domain']}.{action['service']}"})
            log.info(f"OpenCode HA-Aktion: {action['domain']}.{action['service']}")
        except Exception as e:
            log.error(f"OpenCode HA-Aktion Fehler: {e}")
    
    # Parse <ha_automation> blocks
    for match in re.finditer(r'<ha_automation>(.*?)</ha_automation>', response_text, re.DOTALL):
        try:
            automation = json.loads(match.group(1).strip())
            result = execute_tool("create_automation", automation)
            tool_calls.append({"tool": "create_automation"})
            log.info(f"OpenCode Automation: {automation.get('alias','?')}")
        except Exception as e:
            log.error(f"OpenCode Automation Fehler: {e}")
    
    # Aktions-Blöcke aus sichtbarem Text entfernen
    clean_text = re.sub(r'<ha_action>.*?</ha_action>', '', response_text, flags=re.DOTALL)
    clean_text = re.sub(r'<ha_automation>.*?</ha_automation>', '', clean_text, flags=re.DOTALL)
    clean_text = clean_text.strip()
    
    # Session aufräumen
    try:
        requests.delete(f"{base}/session/{session_id}", timeout=5)
    except Exception:
        pass
    
    updated_messages = messages + [{"role": "assistant", "content": clean_text}]
    return {"response": clean_text, "messages": updated_messages, "tool_calls": tool_calls}


# ─── API Endpunkte ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", default_model=DEFAULT_MODEL, has_api_key=bool(DEFAULT_API_KEY))


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    provider = data.get("provider") or DEFAULT_PROVIDER
    api_key = data.get("api_key") or DEFAULT_API_KEY
    opencode_url = data.get("opencode_url") or DEFAULT_OPENCODE_URL
    model = data.get("model", DEFAULT_MODEL)

    log.info(f"Chat-Request: {len(messages)} Nachrichten, provider={provider}, model={model}")

    if not messages:
        return jsonify({"error": "Keine Nachricht übergeben."}), 400

    # ── OpenCode Provider ─────────────────────────────────────────────────────
    if provider == "opencode":
        if not opencode_url:
            return jsonify({"error": "Keine OpenCode URL konfiguriert. Bitte in den Einstellungen eintragen (z.B. http://192.168.1.100:4096)"}), 400
        try:
            result = chat_with_opencode(messages, opencode_url)
            return jsonify(result)
        except requests.ConnectionError:
            return jsonify({"error": f"Kann OpenCode Server nicht erreichen: {opencode_url} – Läuft 'opencode serve' auf deinem PC?"}), 503
        except Exception as e:
            log.error(f"OpenCode Fehler: {e}", exc_info=True)
            return jsonify({"error": f"OpenCode Fehler: {str(e)}"}), 500

    # ── Anthropic Provider ────────────────────────────────────────────────────
    if not api_key:
        return jsonify({"error": "Kein Anthropic API-Key konfiguriert."}), 400

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        return jsonify({"error": f"Anthropic Client Fehler: {e}"}), 500

    # Agentischer Loop: Claude kann mehrfach Tools aufrufen
    current_messages = messages.copy()
    tool_calls_log = []
    MAX_ITERATIONS = 10

    for iteration in range(MAX_ITERATIONS):
        try:
            # Tool-Ergebnisse in älteren Nachrichten kürzen um Tokens zu sparen
            trimmed_messages = []
            for i, msg in enumerate(current_messages):
                if isinstance(msg.get("content"), list):
                    new_content = []
                    for block in msg["content"]:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            # Nur in älteren Nachrichten kürzen (nicht die letzte)
                            if i < len(current_messages) - 1 and len(str(block.get("content", ""))) > 500:
                                new_content.append({**block, "content": str(block.get("content",""))[:300] + "... [gekürzt]"})
                            else:
                                new_content.append(block)
                        else:
                            new_content.append(block)
                    trimmed_messages.append({**msg, "content": new_content})
                else:
                    trimmed_messages.append(msg)

            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=HA_TOOLS,
                messages=trimmed_messages
            )
        except Exception as e:
            log.error(f"Anthropic API Fehler: {e}")
            return jsonify({"error": f"Claude API Fehler: {str(e)}"}), 500

        log.info(f"Iteration {iteration+1}: stop_reason={response.stop_reason}, content_blocks={len(response.content)}")

        if response.stop_reason == "tool_use":
            # Assistent-Nachricht – safe serialisiert
            assistant_content = []
            for block in response.content:
                try:
                    assistant_content.append(json.loads(json.dumps(block.model_dump(), default=str)))
                except Exception:
                    pass
            current_messages.append({"role": "assistant", "content": assistant_content})

            # Tool-Calls ausführen
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    log.info(f"Tool-Call: {block.name}")
                    result = execute_tool(block.name, block.input)
                    tool_calls_log.append({"tool": block.name})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            current_messages.append({"role": "user", "content": tool_results})

        else:
            # Finale Antwort
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            # History sicher serialisieren für nächste Runde
            safe_messages = []
            for msg in current_messages:
                try:
                    safe_messages.append(json.loads(json.dumps(msg, default=str)))
                except Exception:
                    pass
            safe_messages.append({"role": "assistant", "content": text})

            try:
                return jsonify({"response": text, "messages": safe_messages, "tool_calls": tool_calls_log})
            except Exception as e:
                log.error(f"Serialisierungsfehler: {e}")
                return jsonify({"response": text, "messages": [], "tool_calls": []})

    return jsonify({"error": "Maximale Iterations-Anzahl erreicht."})


@app.route("/api/status", methods=["GET"])
def status():
    """Prüft Verbindung zu HA und gibt Basisinfos zurück."""
    try:
        config = ha_get("/config")
        return jsonify({
            "ha_connected": True,
            "ha_version": config.get("version", "?"),
            "location": config.get("location_name", "Home"),
            "addon_configured": bool(DEFAULT_API_KEY),
        })
    except Exception as e:
        return jsonify({"ha_connected": False, "error": str(e)})


# ─── Start ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Claude HA Assistant startet auf Port 8099")
    app.run(host="0.0.0.0", port=8099, debug=False, threaded=True)

CLAUDE_EOF_APP_MAIN_PY

cat > "$BASE/app/templates/index.html" << 'CLAUDE_EOF_APP_TEMPLATES_INDEX_HTML'
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Claude AI – Home Assistant</title>
  <style>
    :root {
      --bg: #111318; --surface: #1c1f2b; --surface2: #252836;
      --border: #2e3347; --accent: #5865f2; --accent2: #7c8cf8;
      --claude: #d97757; --opencode: #22c55e;
      --text: #e8eaf0; --text-muted: #8b90a8;
      --green: #4ade80; --red: #f87171; --radius: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

    /* Header */
    header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0 16px; height: 54px; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
    .header-icon { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; transition: background .3s; }
    .header-icon.anthropic { background: linear-gradient(135deg, var(--claude), #e8925a); }
    .header-icon.opencode  { background: linear-gradient(135deg, #16a34a, #22c55e); }
    header h1 { font-size: 15px; font-weight: 600; flex: 1; }
    header h1 span { display: block; font-size: 11px; font-weight: 400; color: var(--text-muted); }
    #ha-status { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-muted); }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); }
    .status-dot.ok { background: var(--green); }
    .status-dot.error { background: var(--red); }
    #settings-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); border-radius: 8px; padding: 4px 10px; font-size: 12px; cursor: pointer; transition: all .15s; }
    #settings-btn:hover { border-color: var(--accent); color: var(--text); }

    /* Settings Panel */
    #settings-panel { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px; display: none; flex-direction: column; gap: 14px; }
    #settings-panel.open { display: flex; }

    .provider-tabs { display: flex; gap: 8px; }
    .provider-tab { flex: 1; padding: 10px; border-radius: 10px; border: 2px solid var(--border); cursor: pointer; text-align: center; transition: all .2s; background: var(--surface2); }
    .provider-tab .tab-icon { font-size: 20px; margin-bottom: 4px; }
    .provider-tab .tab-name { font-size: 13px; font-weight: 600; }
    .provider-tab .tab-desc { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
    .provider-tab.active.anthropic { border-color: var(--claude); background: rgba(217,119,87,.1); }
    .provider-tab.active.opencode  { border-color: var(--opencode); background: rgba(34,197,94,.1); }

    .provider-fields { display: none; flex-direction: column; gap: 10px; padding: 12px; background: var(--surface2); border-radius: 10px; border: 1px solid var(--border); }
    .provider-fields.active { display: flex; }

    .field-row { display: flex; flex-direction: column; gap: 4px; }
    .field-row label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .5px; }
    .field-row input, .field-row select {
      background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
      color: var(--text); padding: 8px 10px; font-size: 13px; outline: none; transition: border-color .15s;
    }
    .field-row input:focus, .field-row select:focus { border-color: var(--accent); }
    .field-hint { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    .field-hint a { color: var(--accent2); text-decoration: none; }

    /* Messages */
    #messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }
    #messages::-webkit-scrollbar { width: 4px; }
    #messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

    .message { display: flex; gap: 10px; max-width: 780px; animation: fadein .25s ease; }
    @keyframes fadein { from { opacity:0; transform: translateY(6px); } to { opacity:1; transform:none; } }
    .message.user { align-self: flex-end; flex-direction: row-reverse; }
    .avatar { width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; margin-top: 2px; }
    .message.assistant .avatar { background: linear-gradient(135deg, var(--claude), #e8925a); }
    .message.assistant.opencode-msg .avatar { background: linear-gradient(135deg, #16a34a, #22c55e); }
    .message.user .avatar { background: var(--accent); }
    .bubble { padding: 10px 14px; border-radius: var(--radius); font-size: 14px; line-height: 1.6; max-width: 100%; word-break: break-word; }
    .message.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-top-left-radius: 4px; }
    .message.user .bubble { background: var(--accent); color: white; border-top-right-radius: 4px; }
    .bubble p { margin-bottom: 8px; } .bubble p:last-child { margin-bottom: 0; }
    .bubble code { background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }
    .bubble pre { background: rgba(0,0,0,.3); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; overflow-x: auto; margin: 8px 0; font-size: 12px; font-family: monospace; line-height: 1.5; }
    .bubble pre code { background: none; padding: 0; }
    .bubble ul, .bubble ol { padding-left: 18px; margin: 6px 0; }
    .bubble strong { color: var(--accent2); }
    .tool-calls { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
    .tool-badge { background: rgba(88,101,242,.15); border: 1px solid rgba(88,101,242,.3); color: var(--accent2); padding: 2px 8px; border-radius: 20px; font-size: 11px; }
    .typing-indicator { display: flex; gap: 4px; padding: 4px 0; align-items: center; }
    .typing-indicator span { width: 6px; height: 6px; background: var(--text-muted); border-radius: 50%; animation: bounce 1.2s infinite; }
    .typing-indicator span:nth-child(2) { animation-delay: .2s; }
    .typing-indicator span:nth-child(3) { animation-delay: .4s; }
    @keyframes bounce { 0%,60%,100%{transform:none} 30%{transform:translateY(-5px)} }

    /* Input */
    #input-area { background: var(--surface); border-top: 1px solid var(--border); padding: 12px 16px; flex-shrink: 0; }
    #quick-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
    .chip { background: var(--surface2); border: 1px solid var(--border); color: var(--text-muted); padding: 4px 10px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: all .15s; white-space: nowrap; }
    .chip:hover { border-color: var(--accent); color: var(--text); }
    #input-wrapper { display: flex; align-items: flex-end; gap: 8px; background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius); padding: 8px 8px 8px 14px; transition: border-color .15s; }
    #input-wrapper:focus-within { border-color: var(--accent); }
    #user-input { flex: 1; background: none; border: none; outline: none; color: var(--text); font-size: 14px; line-height: 1.5; resize: none; max-height: 150px; min-height: 24px; font-family: inherit; padding: 2px 0; }
    #user-input::placeholder { color: var(--text-muted); }
    #send-btn { width: 34px; height: 34px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all .15s; }
    #send-btn:hover { background: var(--accent2); }
    #send-btn:disabled { background: var(--border); cursor: not-allowed; }
    .input-hint { font-size: 11px; color: var(--text-muted); margin-top: 6px; text-align: center; }

    /* Welcome */
    #welcome { margin: auto; text-align: center; padding: 32px 20px; max-width: 480px; }
    #welcome .big-icon { font-size: 48px; margin-bottom: 16px; }
    #welcome h2 { font-size: 20px; font-weight: 600; margin-bottom: 8px; }
    #welcome p { font-size: 14px; color: var(--text-muted); line-height: 1.6; }
  </style>
</head>
<body>

<header>
  <div class="header-icon anthropic" id="header-icon">🤖</div>
  <h1>Claude AI Assistant <span id="provider-label">Anthropic Claude</span></h1>
  <div id="ha-status"><div class="status-dot" id="status-dot"></div><span id="status-text">Verbinde...</span></div>
  <button id="settings-btn" onclick="toggleSettings()">⚙ Einstellungen</button>
</header>

<div id="settings-panel">
  <!-- Provider Auswahl -->
  <div>
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px">KI-Anbieter wählen</div>
    <div class="provider-tabs">
      <div class="provider-tab anthropic active" id="tab-anthropic" onclick="selectProvider('anthropic')">
        <div class="tab-icon">🤖</div>
        <div class="tab-name">Anthropic Claude</div>
        <div class="tab-desc">API-Key erforderlich</div>
      </div>
      <div class="provider-tab opencode" id="tab-opencode" onclick="selectProvider('opencode')">
        <div class="tab-icon">🥒</div>
        <div class="tab-name">OpenCode Big Pickle</div>
        <div class="tab-desc">Kostenlos · Lokal</div>
      </div>
    </div>
  </div>

  <!-- Anthropic Felder -->
  <div class="provider-fields active" id="fields-anthropic">
    <div class="field-row">
      <label>Anthropic API-Key</label>
      <input type="password" id="api-key-input" placeholder="sk-ant-api03-..." />
      <div class="field-hint">Erhältlich unter <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a></div>
    </div>
    <div class="field-row">
      <label>Claude Modell</label>
      <select id="model-select">
        <option value="claude-sonnet-4-6">Claude Sonnet 4.6 – Schnell &amp; günstig ✓</option>
        <option value="claude-opus-4-5">Claude Opus 4.5 – Leistungsstark</option>
        <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 – Sehr günstig</option>
      </select>
    </div>
  </div>

  <!-- OpenCode Felder -->
  <div class="provider-fields" id="fields-opencode">
    <div class="field-row">
      <label>OpenCode Server URL</label>
      <input type="text" id="opencode-url-input" placeholder="192.168.1.100:4096" />
      <div class="field-hint">
        Starte OpenCode auf deinem PC: <code>opencode serve --hostname 0.0.0.0 --port 4096</code><br>
        Modell: <strong>Big Pickle</strong> (kostenlos, wird automatisch verwendet)
      </div>
    </div>
  </div>
</div>

<div id="messages">
  <div id="welcome">
    <div class="big-icon">🏠</div>
    <h2>Hallo! Wie kann ich helfen?</h2>
    <p>Ich habe vollen Zugriff auf dein Home Assistant und kann Geräte steuern, Automationen erstellen und vieles mehr.</p>
  </div>
</div>

<div id="input-area">
  <div id="quick-actions">
    <div class="chip" onclick="sendQuick('Was sind die aktuellen Zustände aller Lichter?')">💡 Lichter</div>
    <div class="chip" onclick="sendQuick('Welche Automationen habe ich?')">⚡ Automationen</div>
    <div class="chip" onclick="sendQuick('Zeige mir alle Sensoren und ihre Werte')">📊 Sensoren</div>
    <div class="chip" onclick="sendQuick('Welche Geräte sind gerade eingeschaltet?')">🔌 Status</div>
  </div>
  <div id="input-wrapper">
    <textarea id="user-input" placeholder="Nachricht schreiben... (z.B. 'Schalte alle Lichter aus')" rows="1"></textarea>
    <button id="send-btn" onclick="sendMessage()">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    </button>
  </div>
  <div class="input-hint">Enter = Senden &nbsp;·&nbsp; Shift+Enter = Zeilenumbruch</div>
</div>

<script>
const BASE = window.location.pathname.replace(/\/+$/, '');
let messageHistory = [];
let isLoading = false;
let currentProvider = 'anthropic';

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  checkStatus();
  const ta = document.getElementById('user-input');
  ta.addEventListener('input', () => { ta.style.height='auto'; ta.style.height=Math.min(ta.scrollHeight,150)+'px'; });
  ta.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} });
  document.getElementById('api-key-input').addEventListener('change', saveSettings);
  document.getElementById('model-select').addEventListener('change', saveSettings);
  document.getElementById('opencode-url-input').addEventListener('change', saveSettings);
});

function selectProvider(p) {
  currentProvider = p;
  document.getElementById('tab-anthropic').classList.toggle('active', p==='anthropic');
  document.getElementById('tab-opencode').classList.toggle('active', p==='opencode');
  document.getElementById('fields-anthropic').classList.toggle('active', p==='anthropic');
  document.getElementById('fields-opencode').classList.toggle('active', p==='opencode');
  const icon = document.getElementById('header-icon');
  icon.className = 'header-icon ' + p;
  icon.textContent = p==='opencode' ? '🥒' : '🤖';
  document.getElementById('provider-label').textContent = p==='opencode' ? 'OpenCode · Big Pickle' : 'Anthropic Claude';
  saveSettings();
}

function toggleSettings() {
  document.getElementById('settings-panel').classList.toggle('open');
}

function loadSettings() {
  document.getElementById('api-key-input').value = localStorage.getItem('claude_api_key') || '';
  document.getElementById('model-select').value = localStorage.getItem('claude_model') || 'claude-sonnet-4-6';
  document.getElementById('opencode-url-input').value = localStorage.getItem('opencode_url') || '';
  const p = localStorage.getItem('claude_provider') || 'anthropic';
  selectProvider(p);
}

function saveSettings() {
  localStorage.setItem('claude_api_key', document.getElementById('api-key-input').value);
  localStorage.setItem('claude_model', document.getElementById('model-select').value);
  localStorage.setItem('opencode_url', document.getElementById('opencode-url-input').value);
  localStorage.setItem('claude_provider', currentProvider);
}

function getSettings() {
  return {
    provider: currentProvider,
    api_key: document.getElementById('api-key-input').value || undefined,
    model: document.getElementById('model-select').value,
    opencode_url: document.getElementById('opencode-url-input').value || undefined,
  };
}

async function checkStatus() {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  try {
    const r = await fetch(BASE + '/api/status');
    const d = await r.json();
    dot.className = 'status-dot ' + (d.ha_connected ? 'ok' : 'error');
    txt.textContent = d.ha_connected ? `HA ${d.ha_version} · ${d.location}` : 'HA nicht erreichbar';
  } catch { dot.className='status-dot error'; txt.textContent='Verbindungsfehler'; }
}

function renderMarkdown(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>`<pre><code>${c.trim()}</code></pre>`)
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/^#{1,3} (.+)$/gm,'<strong>$1</strong>')
    .replace(/^[-*] (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g,m=>`<ul>${m}</ul>`)
    .replace(/\n\n/g,'</p><p>').replace(/\n/g,'<br>');
}

function addMessage(role, content, toolCalls, provider) {
  document.getElementById('welcome')?.remove();
  const wrap = document.createElement('div');
  wrap.className = `message ${role}` + (provider==='opencode'?' opencode-msg':'');
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role==='user' ? '👤' : (provider==='opencode'?'🥒':'🤖');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if(toolCalls?.length) {
    const badges = document.createElement('div');
    badges.className = 'tool-calls';
    toolCalls.forEach(tc => { const b=document.createElement('span'); b.className='tool-badge'; b.textContent='⚡ '+tc.tool; badges.appendChild(b); });
    bubble.appendChild(badges);
  }
  const txt = document.createElement('div');
  txt.innerHTML = renderMarkdown(content);
  bubble.appendChild(txt);
  wrap.appendChild(avatar); wrap.appendChild(bubble);
  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

function addTyping() {
  document.getElementById('welcome')?.remove();
  const wrap = document.createElement('div');
  wrap.className = 'message assistant'; wrap.id = 'typing-msg';
  const avatar = document.createElement('div'); avatar.className='avatar'; avatar.textContent='⏳';
  const bubble = document.createElement('div'); bubble.className='bubble';
  bubble.innerHTML='<div class="typing-indicator"><span></span><span></span><span></span></div>';
  wrap.appendChild(avatar); wrap.appendChild(bubble);
  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

function sendQuick(text) { document.getElementById('user-input').value=text; sendMessage(); }

async function sendMessage() {
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if(!text || isLoading) return;
  isLoading = true;
  document.getElementById('send-btn').disabled = true;
  input.value = ''; input.style.height = 'auto';
  addMessage('user', text);
  messageHistory.push({role:'user', content:text});
  addTyping();
  const settings = getSettings();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 180000); // 3 Minuten
    const res = await fetch(BASE + '/api/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({messages:messageHistory, ...settings}),
      signal: controller.signal
    });
    clearTimeout(timeout);
    document.getElementById('typing-msg')?.remove();
    const data = await res.json();
    if(data.error) {
      addMessage('assistant', '❌ ' + data.error);
    } else {
      addMessage('assistant', data.response, data.tool_calls, settings.provider);
      messageHistory = data.messages || messageHistory;
      if(!data.messages) messageHistory.push({role:'assistant', content:data.response});
    }
  } catch(err) {
    document.getElementById('typing-msg')?.remove();
    const msg = err.name==='AbortError' ? '⏱ Zeitüberschreitung – OpenCode braucht zu lange. Bitte nochmal versuchen.' : '❌ Netzwerkfehler: ' + err.message;
    addMessage('assistant', msg);
  } finally {
    isLoading = false;
    document.getElementById('send-btn').disabled = false;
    input.focus();
    checkStatus();
  }
}
</script>
</body>
</html>

CLAUDE_EOF_APP_TEMPLATES_INDEX_HTML

chmod +x "$BASE/run.sh"
echo "✅ Update fertig!"