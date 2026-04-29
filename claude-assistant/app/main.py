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
    if not opencode_url.startswith("http"):
        opencode_url = "http://" + opencode_url
    base = opencode_url.rstrip("/")
    
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
    
    r = requests.post(f"{base}/session/{session_id}/message", json=payload, timeout=120)
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
