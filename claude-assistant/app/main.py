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

import threading
import uuid
import time

# ─── App ──────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")

# ─── Async Job Store ─────────────────────────────────────────────────────────
_jobs = {}  # job_id -> {"status": "pending/done/error", "result": {...}}

def run_chat_job(job_id: str, messages: list, provider: str, api_key: str, model: str, opencode_url: str, session_id: str = ""):
    try:
        if provider == "opencode":
            result = chat_with_opencode(messages, opencode_url)
        else:
            result = chat_with_anthropic(messages, api_key, model)
        # Session speichern
        if session_id and result.get("messages"):
            title = make_title(result["messages"])
            session_save(session_id, title, result["messages"], provider)
        _jobs[job_id] = {"status": "done", "result": {**result, "session_id": session_id}}
    except Exception as e:
        log.error(f"Job {job_id} failed: {e}", exc_info=True)
        _jobs[job_id] = {"status": "error", "result": {"error": str(e)}}


# ─── Session Storage ─────────────────────────────────────────────────────────
SESSIONS_DIR = "/data/sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

def session_list():
    sessions = []
    try:
        for f in os.listdir(SESSIONS_DIR):
            if not f.endswith(".json"):
                continue
            path = os.path.join(SESSIONS_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    s = json.load(fh)
                sessions.append({
                    "id": s["id"],
                    "title": s.get("title", "Chat"),
                    "provider": s.get("provider", "anthropic"),
                    "updated_at": s.get("updated_at", ""),
                    "message_count": len([m for m in s.get("messages", []) if m.get("role") == "user"])
                })
            except Exception as e:
                log.warning(f"Could not load session {f}: {e}")
    except Exception as e:
        log.error(f"session_list error: {e}")
    # Neueste zuerst
    sessions.sort(key=lambda x: x.get("updated_at",""), reverse=True)
    return sessions


def session_save(session_id: str, title: str, messages: list, provider: str):
    import time
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "id": session_id,
            "title": title,
            "provider": provider,
            "messages": messages,
            "updated_at": time.strftime("%Y-%m-%d %H:%M")
        }, f, ensure_ascii=False, indent=2)


def session_load(session_id: str):
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def session_delete(session_id: str):
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(path):
        os.remove(path)


def make_title(messages: list) -> str:
    """Ersten User-Text als Titel kürzen."""
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            t = msg["content"][:50].strip()
            return t + ("..." if len(msg["content"]) > 50 else "")
    return "Chat"


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

HA_ACTIONS_PROMPT = """
Du hast vollen Schreibzugriff auf Home Assistant. Verwende folgende Befehls-Blöcke:

1. Gerät steuern:
<ha_action>
{"domain": "light", "service": "turn_on", "data": {"entity_id": "light.xyz", "brightness_pct": 50}}
</ha_action>

2. Automation erstellen/aktualisieren:
<ha_automation>
{"alias": "Name", "description": "...", "trigger": [...], "condition": [...], "action": [...], "mode": "single"}
</ha_automation>

3. Template-Sensor erstellen:
<ha_template_sensor>
{"name": "Anzeigename", "unique_id": "eindeutige_id", "unit_of_measurement": "W", "device_class": "power", "state_class": "measurement", "state": "{{ states('sensor.xyz') | float(0) + states('sensor.abc') | float(0) }}"}
</ha_template_sensor>

4. Skript erstellen:
<ha_script>
{"alias": "Skript Name", "unique_id": "skript_id", "sequence": [{"service": "light.turn_on", "target": {"entity_id": "light.xyz"}}]}
</ha_script>

5. Szene erstellen:
<ha_scene>
{"name": "Szenen Name", "unique_id": "szene_id", "entities": {"light.xyz": {"state": "on", "brightness": 200}}}
</ha_scene>

6. HA-Komponente neu laden:
<ha_reload>{"target": "automation"}</ha_reload>
(target kann sein: automation, template, script, scene, all)

7. HA komplett neu starten:
<ha_restart></ha_restart>

WICHTIG: Schreibe IMMER die passenden Blöcke – nicht nur erklären! Führe Änderungen direkt aus.
Mehrere Blöcke hintereinander sind erlaubt.
"""


def ensure_config_include(filename: str, section_key: str):
    """Stellt sicher dass eine Datei in configuration.yaml eingebunden ist."""
    config_file = "/config/configuration.yaml"
    include_line = f"{section_key}: !include {filename}"
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_content = f.read()
        if filename not in config_content:
            with open(config_file, "a", encoding="utf-8") as f:
                f.write(f"\n{include_line}\n")
            log.info(f"Added {include_line} to configuration.yaml")
    except Exception as e:
        log.warning(f"Could not update configuration.yaml: {e}")


def write_template_sensor(sensor: dict) -> str:
    """Template-Sensor in /config/template.yaml schreiben."""
    import yaml as _yaml
    template_file = "/config/template.yaml"
    existing = []
    if os.path.exists(template_file):
        with open(template_file, "r", encoding="utf-8") as f:
            existing = _yaml.safe_load(f) or []
    if not isinstance(existing, list):
        existing = [existing] if existing else []

    # Duplikat-Check per unique_id
    uid = sensor.get("unique_id", "")
    existing = [e for e in existing if not (isinstance(e, dict) and 
                e.get("sensor", [{}])[0].get("unique_id") == uid if e.get("sensor") else False)]

    entry = {"sensor": [sensor]}
    existing.append(entry)

    with open(template_file, "w", encoding="utf-8") as f:
        _yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)

    ensure_config_include("template.yaml", "template")
    return f"Template-Sensor '{sensor.get('name')}' in template.yaml geschrieben."


def write_script(script: dict) -> str:
    """Skript in /config/scripts.yaml schreiben."""
    import yaml as _yaml
    scripts_file = "/config/scripts.yaml"
    existing = {}
    if os.path.exists(scripts_file):
        with open(scripts_file, "r", encoding="utf-8") as f:
            existing = _yaml.safe_load(f) or {}
    if not isinstance(existing, dict):
        existing = {}

    uid = script.get("unique_id") or script.get("alias", "").lower().replace(" ", "_")
    existing[uid] = {k: v for k, v in script.items() if k != "unique_id"}

    with open(scripts_file, "w", encoding="utf-8") as f:
        _yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)
    return f"Skript '{script.get('alias')}' in scripts.yaml geschrieben."


def write_scene(scene: dict) -> str:
    """Szene in /config/scenes.yaml schreiben."""
    import yaml as _yaml
    scenes_file = "/config/scenes.yaml"
    existing = []
    if os.path.exists(scenes_file):
        with open(scenes_file, "r", encoding="utf-8") as f:
            existing = _yaml.safe_load(f) or []
    if not isinstance(existing, list):
        existing = []

    uid = scene.get("unique_id", "")
    existing = [s for s in existing if s.get("unique_id") != uid]
    existing.append(scene)

    with open(scenes_file, "w", encoding="utf-8") as f:
        _yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)
    return f"Szene '{scene.get('name')}' in scenes.yaml geschrieben."


def ha_reload(target: str):
    """HA-Komponente neu laden."""
    reload_map = {
        "automation": ("automation", "reload"),
        "template":   ("homeassistant", "reload_config_entry"),
        "script":     ("script", "reload"),
        "scene":      ("scene", "reload"),
        "all":        ("homeassistant", "reload_all"),
    }
    if target == "template":
        # Template reload braucht andere Methode
        try:
            ha_post("/services/homeassistant/reload_all", {})
        except Exception:
            pass
        return
    if target in reload_map:
        domain, service = reload_map[target]
        try:
            ha_post(f"/services/{domain}/{service}", {})
        except Exception as e:
            log.warning(f"Reload {target} failed: {e}")


def chat_with_opencode(messages: list, opencode_url: str) -> dict:
    """Chat via OpenCode local server API mit vollem HA-Zugriff."""
    import re
    import yaml as _yaml

    base = opencode_url.strip().rstrip("/.").rstrip("/")
    if not base.startswith("http"):
        base = "http://" + base

    # Session erstellen
    r = requests.post(f"{base}/session", json={}, timeout=10)
    r.raise_for_status()
    session_id = r.json()["id"]
    log.info(f"OpenCode Session: {session_id}")

    # Letzten User-Text extrahieren
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            user_text = msg["content"]
            break

    # History als Kontext
    history_text = ""
    for msg in messages[:-1]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            history_text += f"{role.upper()}: {content}\n"

    full_prompt = user_text
    if history_text:
        full_prompt = f"[Bisheriger Verlauf:]\n{history_text}\n[Aktuelle Anfrage:] {user_text}"

    # Aktuelle HA-Entitäten als Kontext mitgeben
    try:
        states = ha_get("/states")
        entity_summary = ", ".join([
            f"{s['entity_id']}={s['state']}"
            for s in states[:60]
        ])
        ha_context = f"\n\n[Verfügbare HA-Entitäten (Auswahl)]: {entity_summary}"
    except Exception:
        ha_context = ""

    payload = {
        "parts": [{"type": "text", "text": SYSTEM_PROMPT + HA_ACTIONS_PROMPT + ha_context + "\n\n" + full_prompt}],
        "model": {"providerID": "opencode", "modelID": "big-pickle"}
    }

    r = requests.post(f"{base}/session/{session_id}/message", json=payload, timeout=180)
    r.raise_for_status()
    response_data = r.json()

    # Text aus Response
    response_text = ""
    for part in response_data.get("parts", []):
        if part.get("type") == "text":
            response_text += part.get("text", "")
        elif isinstance(part.get("content"), str):
            response_text += part["content"]

    tool_calls = []
    results_log = []

    # ── ha_action ─────────────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_action>(.*?)</ha_action>', response_text, re.DOTALL):
        try:
            action = json.loads(match.group(1).strip())
            execute_tool("call_service", {
                "domain": action["domain"],
                "service": action["service"],
                "service_data": action.get("data", {})
            })
            tool_calls.append({"tool": f"{action['domain']}.{action['service']}"})
            results_log.append(f"✅ Ausgeführt: {action['domain']}.{action['service']}")
        except Exception as e:
            results_log.append(f"❌ ha_action Fehler: {e}")
            log.error(f"ha_action: {e}")

    # ── ha_automation ─────────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_automation>(.*?)</ha_automation>', response_text, re.DOTALL):
        try:
            automation = json.loads(match.group(1).strip())
            execute_tool("create_automation", automation)
            tool_calls.append({"tool": "create_automation"})
            results_log.append(f"✅ Automation '{automation.get('alias')}' erstellt")
        except Exception as e:
            results_log.append(f"❌ Automation Fehler: {e}")
            log.error(f"ha_automation: {e}")

    # ── ha_template_sensor ────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_template_sensor>(.*?)</ha_template_sensor>', response_text, re.DOTALL):
        try:
            sensor = json.loads(match.group(1).strip())
            msg = write_template_sensor(sensor)
            ha_reload("template")
            tool_calls.append({"tool": "template_sensor"})
            results_log.append(f"✅ {msg}")
        except Exception as e:
            results_log.append(f"❌ Template-Sensor Fehler: {e}")
            log.error(f"ha_template_sensor: {e}")

    # ── ha_script ─────────────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_script>(.*?)</ha_script>', response_text, re.DOTALL):
        try:
            script = json.loads(match.group(1).strip())
            msg = write_script(script)
            ha_reload("script")
            tool_calls.append({"tool": "script"})
            results_log.append(f"✅ {msg}")
        except Exception as e:
            results_log.append(f"❌ Skript Fehler: {e}")
            log.error(f"ha_script: {e}")

    # ── ha_scene ──────────────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_scene>(.*?)</ha_scene>', response_text, re.DOTALL):
        try:
            scene = json.loads(match.group(1).strip())
            msg = write_scene(scene)
            ha_reload("scene")
            tool_calls.append({"tool": "scene"})
            results_log.append(f"✅ {msg}")
        except Exception as e:
            results_log.append(f"❌ Szene Fehler: {e}")
            log.error(f"ha_scene: {e}")

    # ── ha_reload ─────────────────────────────────────────────────────────────
    for match in re.finditer(r'<ha_reload>(.*?)</ha_reload>', response_text, re.DOTALL):
        try:
            data = json.loads(match.group(1).strip())
            target = data.get("target", "all")
            ha_reload(target)
            tool_calls.append({"tool": f"reload_{target}"})
            results_log.append(f"✅ {target} neu geladen")
        except Exception as e:
            results_log.append(f"❌ Reload Fehler: {e}")

    # ── ha_restart ────────────────────────────────────────────────────────────
    if re.search(r'<ha_restart\s*/?>', response_text):
        try:
            ha_post("/services/homeassistant/restart", {})
            tool_calls.append({"tool": "ha_restart"})
            results_log.append("✅ Home Assistant wird neu gestartet...")
        except Exception as e:
            results_log.append(f"❌ Restart Fehler: {e}")

    # Session aufräumen
    try:
        requests.delete(f"{base}/session/{session_id}", timeout=5)
    except Exception:
        pass

    # Blöcke aus sichtbarem Text entfernen
    clean_text = re.sub(r'<ha_[a-z_]+>.*?</ha_[a-z_]+>', '', response_text, flags=re.DOTALL)
    clean_text = re.sub(r'<ha_restart\s*/?>', '', clean_text)
    clean_text = clean_text.strip()

    # Ausgeführte Aktionen ans Ende anhängen
    if results_log:
        clean_text += "\n\n---\n" + "\n".join(results_log)

    updated_messages = messages + [{"role": "assistant", "content": clean_text}]
    return {"response": clean_text, "messages": updated_messages, "tool_calls": tool_calls}


# ─── API Endpunkte ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", default_model=DEFAULT_MODEL, has_api_key=bool(DEFAULT_API_KEY))


def chat_with_anthropic(messages, api_key, model):
    """Anthropic chat als eigenständige Funktion für async."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        return {"error": f"Anthropic Client Fehler: {e}"}

    current_messages = messages.copy()
    tool_calls_log = []

    for iteration in range(10):
        trimmed_messages = []
        for i, msg in enumerate(current_messages):
            if isinstance(msg.get("content"), list):
                new_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
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

        if response.stop_reason == "tool_use":
            assistant_content = []
            for block in response.content:
                try:
                    assistant_content.append(json.loads(json.dumps(block.model_dump(), default=str)))
                except Exception:
                    pass
            current_messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_calls_log.append({"tool": block.name})
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            current_messages.append({"role": "user", "content": tool_results})
        else:
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            safe_messages = []
            for msg in current_messages:
                try:
                    safe_messages.append(json.loads(json.dumps(msg, default=str)))
                except Exception:
                    pass
            safe_messages.append({"role": "assistant", "content": text})

            try:
                return {"response": text, "messages": safe_messages, "tool_calls": tool_calls_log}
            except Exception as e:
                return {"response": text, "messages": [], "tool_calls": []}

    return {"error": "Maximale Iterations-Anzahl erreicht."}


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    provider = data.get("provider") or DEFAULT_PROVIDER
    api_key = data.get("api_key") or DEFAULT_API_KEY
    opencode_url = data.get("opencode_url") or DEFAULT_OPENCODE_URL
    model = data.get("model", DEFAULT_MODEL)

    log.info(f"Chat-Request: {len(messages)} Nachrichten, provider={provider}")

    if not messages:
        return jsonify({"error": "Keine Nachricht übergeben."}), 400

    if provider == "opencode" and not opencode_url:
        return jsonify({"error": "Keine OpenCode URL konfiguriert."}), 400
    if provider == "anthropic" and not api_key:
        return jsonify({"error": "Kein Anthropic API-Key konfiguriert."}), 400

    # Async Job starten
    job_id = str(uuid.uuid4())
    session_id = data.get("session_id") or str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending"}
    t = threading.Thread(target=run_chat_job, args=(job_id, messages, provider, api_key, model, opencode_url, session_id), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/api/chat/poll/<job_id>", methods=["GET"])
def chat_poll(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job nicht gefunden"}), 404
    if job["status"] == "pending":
        return jsonify({"status": "pending"})
    # Job done - cleanup
    result = job["result"]
    del _jobs[job_id]
    if job["status"] == "error":
        return jsonify({"status": "error", **result})
    return jsonify({"status": "done", **result})


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    return jsonify(session_list())


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    s = session_load(session_id)
    if not s:
        return jsonify({"error": "Session nicht gefunden"}), 404
    return jsonify(s)


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    session_delete(session_id)
    return jsonify({"deleted": True})


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
