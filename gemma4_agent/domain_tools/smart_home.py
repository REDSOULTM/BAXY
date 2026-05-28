"""Smart Home domain tool — extracted from domain_tools.py (R2 sprint 2026-05-28).

Control LOCAL de Home Assistant via REST API + MQTT publish (paho opcional).
NO toca dispositivos cloud — sólo el HA local del usuario (host + long-lived
access token via env GEMMA4_HASS_TOKEN). MQTT publish para automaciones que
no van via HA.

Funciones extraídas (10):
  smart_home_tool                (entry, 9 acciones)
  _hass_alive                    (probe rápido al endpoint, distingue 401/404 de timeout)
  _hass_request                  (helper REST genérico)
  _hass_states                   (discover entidades)
  _hass_get_state / _hass_set_state
  _hass_call_service             (con rollback snapshot)
  _hass_area_list                (REST snapshot via /states)
  _hass_area_control             (turn_on/off por área agrupado por domain)
  _smart_home_mqtt_publish       (paho opcional)

Helpers compartidos: solo _ok/_err desde _shared. AgentState para checkpoints.
Auto-contenido — no usa _resources_by_kind ni helpers de domain_tools."""
from __future__ import annotations

import importlib.util
import json
import os
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState


__all__ = [
    "smart_home_tool",
    "_hass_alive",
    "_hass_request",
    "_hass_states",
    "_hass_get_state",
    "_hass_set_state",
    "_hass_call_service",
    "_hass_area_list",
    "_hass_area_control",
    "_smart_home_mqtt_publish",
]


def smart_home_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local smart home control (Home Assistant + MQTT).

    Actions: status, discover, get_state, set_state, call_service, scene_run,
    area_list, area_control, mqtt_publish. All endpoints are LOCAL HTTP to
    your Home Assistant install; auth is a long-lived access token via
    GEMMA4_HASS_TOKEN env var. mqtt_publish requires paho-mqtt installed.
    """
    action = str(args.get("action") or "status").casefold()
    host = str(args.get("host") or os.environ.get("GEMMA4_HASS_HOST") or "http://homeassistant.local:8123").rstrip("/")
    token = str(args.get("token") or os.environ.get("GEMMA4_HASS_TOKEN") or "").strip()
    alive = _hass_alive(host)
    if action == "status":
        try:
            mqtt_available = importlib.util.find_spec("paho") is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            mqtt_available = False
        return _ok(
            home_assistant=bool(alive),
            host=host,
            has_token=bool(token),
            mqtt_available=mqtt_available,
            note="Set GEMMA4_HASS_HOST and GEMMA4_HASS_TOKEN (long-lived access token from /profile in your HA UI).",
        )
    if not alive:
        return _err(
            f"Home Assistant is not reachable at {host}",
            status="needs_user", verified=False,
            completion_status="needs_home_assistant_running",
            note="Set GEMMA4_HASS_HOST to the URL your HA instance listens on (default http://homeassistant.local:8123).",
        )
    if action == "mqtt_publish":
        return _smart_home_mqtt_publish(args)
    if not token:
        return _err(
            "Home Assistant requires a long-lived access token",
            status="needs_user",
            completion_status="needs_user_auth",
            required_env="GEMMA4_HASS_TOKEN",
            note="Create one in the HA UI > your profile > Long-Lived Access Tokens.",
        )
    if action in {"discover", "states"}:
        return _hass_states(host, token, args)
    if action == "get_state":
        return _hass_get_state(host, token, args)
    if action == "set_state":
        return _hass_set_state(host, token, args, state)
    if action == "call_service":
        return _hass_call_service(host, token, args, state)
    if action == "scene_run":
        scene = str(args.get("scene") or args.get("entity_id") or "").strip()
        if not scene:
            return _err("scene_run requires scene= or entity_id=")
        return _hass_call_service(host, token, {"domain": "scene", "service": "turn_on", "data": {"entity_id": scene}}, state)
    if action in {"area_list", "areas"}:
        return _hass_area_list(host, token)
    if action == "area_control":
        return _hass_area_control(host, token, args, state)
    return _err(
        "unknown smart_home action", action=action,
        valid_actions=[
            "status", "discover", "states", "service_call", "mqtt_publish",
            "automation_trigger",
        ],
        status="needs_user",
    )


def _hass_alive(host: str) -> bool:
    # T3-smart_home-alive-always-true-031: distingue HTTPError (servidor vivo
    # con 401/403) de URLError/timeout (servidor caído).
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(f"{host}/api/", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=2.0):
            return True
    except urllib.error.HTTPError as exc:
        # Cualquier HTTP code legítimo significa que HA responde.
        return exc.code in (200, 401, 403, 404)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _hass_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    import urllib.request
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "Gemma4Agent/1.0"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            try:
                return {"_ok": True, "_status": resp.status, "data": json.loads(body) if body else None}
            except json.JSONDecodeError:
                return {"_ok": True, "_status": resp.status, "data": body.decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"_ok": False, "_error": str(exc)}


def _hass_states(host: str, token: str, args: dict[str, Any]) -> dict[str, Any]:
    resp = _hass_request("GET", f"{host}/api/states", token)
    if not resp.get("_ok"):
        return _err(f"GET /api/states failed: {resp.get('_error')}")
    states = resp.get("data") or []
    domain_filter = str(args.get("domain") or "").casefold()
    if domain_filter:
        states = [s for s in states if str(s.get("entity_id", "")).split(".", 1)[0].casefold() == domain_filter]
    limit = int(args.get("limit", 500))
    return _ok(count=len(states), states=states[:limit], domain_filter=domain_filter or None)


def _hass_get_state(host: str, token: str, args: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip()
    if not entity_id:
        return _err("missing entity_id")
    resp = _hass_request("GET", f"{host}/api/states/{entity_id}", token)
    if not resp.get("_ok"):
        return _err(f"GET state failed: {resp.get('_error')}", entity_id=entity_id)
    return _ok(entity_id=entity_id, state=resp.get("data"))


def _hass_set_state(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip()
    new_state = args.get("state")
    if not entity_id or new_state is None:
        return _err("set_state requires entity_id and state")
    # Snapshot the previous state for rollback.
    before = _hass_get_state(host, token, {"entity_id": entity_id}).get("state") or {}
    payload = {"state": str(new_state), "attributes": args.get("attributes") if isinstance(args.get("attributes"), dict) else {}}
    checkpoint = state.checkpoint(
        f"smart_home set_state {entity_id}",
        rollback=[{"tool": "smart_home", "args": {"action": "set_state", "entity_id": entity_id, "state": before.get("state"), "attributes": before.get("attributes")}}] if before.get("state") is not None else [],
        metadata={"before": before, "target": payload},
    )
    resp = _hass_request("POST", f"{host}/api/states/{entity_id}", token, payload)
    if not resp.get("_ok"):
        return _err(f"set_state failed: {resp.get('_error')}", entity_id=entity_id, checkpoint=checkpoint.get("checkpoint"))
    return _ok(entity_id=entity_id, before=before, after=resp.get("data"), checkpoint=checkpoint.get("checkpoint"), verified=True)


def _hass_call_service(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    domain = str(args.get("domain") or "").strip()
    service = str(args.get("service") or "").strip()
    if not domain or not service:
        return _err("call_service requires domain and service")
    raw_payload = args.get("data")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    # Merge target into payload (HA accepts entity_id at top-level).
    raw_target = args.get("target")
    target: dict[str, Any] | None = raw_target if isinstance(raw_target, dict) else None
    if target:
        payload = {**payload, **target}
    # For toggle/turn_off/turn_on on a switch/light, snapshot before so rollback exists.
    rollback_step = None
    if service in {"turn_on", "turn_off", "toggle"} and payload.get("entity_id"):
        eid_raw = payload["entity_id"]
        eid = eid_raw if isinstance(eid_raw, str) else (eid_raw[0] if eid_raw else None)
        if eid:
            current = _hass_get_state(host, token, {"entity_id": eid}).get("state") or {}
            if current.get("state") == "on" and service == "turn_off":
                rollback_step = {"tool": "smart_home", "args": {"action": "call_service", "domain": domain, "service": "turn_on", "data": {"entity_id": eid}}}
            elif current.get("state") == "off" and service == "turn_on":
                rollback_step = {"tool": "smart_home", "args": {"action": "call_service", "domain": domain, "service": "turn_off", "data": {"entity_id": eid}}}
    checkpoint = state.checkpoint(
        f"smart_home {domain}.{service}",
        rollback=[rollback_step] if rollback_step else [],
        metadata={"domain": domain, "service": service, "payload": payload},
    )
    resp = _hass_request("POST", f"{host}/api/services/{domain}/{service}", token, payload)
    if not resp.get("_ok"):
        return _err(f"call_service failed: {resp.get('_error')}", domain=domain, service=service)
    return _ok(domain=domain, service=service, payload=payload, response=resp.get("data"), checkpoint=checkpoint.get("checkpoint"), verified=True)


def _hass_area_list(host: str, token: str) -> dict[str, Any]:
    # Areas are exposed via the config endpoint; the WebSocket area_registry/list
    # is more complete, but a REST snapshot via /api/config + /api/states covers
    # the basics for naming.
    resp = _hass_request("GET", f"{host}/api/states", token)
    if not resp.get("_ok"):
        return _err(f"area_list failed: {resp.get('_error')}")
    states = resp.get("data") or []
    areas: dict[str, list[str]] = {}
    for s in states:
        area = (s.get("attributes") or {}).get("area_id") or (s.get("attributes") or {}).get("area") or ""
        if not area:
            continue
        areas.setdefault(str(area), []).append(s.get("entity_id"))
    return _ok(areas=[{"area_id": k, "entities": v, "count": len(v)} for k, v in areas.items()], count=len(areas), note="Areas read from entity attributes; for the full area_registry use the WebSocket API.")


def _hass_area_control(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    area = str(args.get("area") or args.get("area_id") or "").strip()
    service = str(args.get("service") or "turn_off").strip()
    if not area:
        return _err("missing area")
    area_info = _hass_area_list(host, token)
    matching = next((a for a in area_info.get("areas", []) if a.get("area_id") == area or area.casefold() in str(a.get("area_id") or "").casefold()), None)
    if not matching:
        return _err("area not found", area=area, available=[a["area_id"] for a in area_info.get("areas", [])])
    # Group by domain so we call e.g. light.turn_off once per area.
    results: list[dict[str, Any]] = []
    by_domain: dict[str, list[str]] = {}
    for entity in matching.get("entities", []):
        domain = str(entity).split(".", 1)[0]
        by_domain.setdefault(domain, []).append(entity)
    for domain, entities in by_domain.items():
        if domain not in {"light", "switch", "fan", "media_player", "climate", "cover", "vacuum"}:
            continue
        r = _hass_call_service(host, token, {"domain": domain, "service": service, "data": {"entity_id": entities}}, state)
        results.append({"domain": domain, "entities": entities, "result": {"ok": r.get("ok"), "error": r.get("error")}})
    return _ok(area=matching["area_id"], service=service, calls=results, verified=all(r["result"]["ok"] for r in results))


def _smart_home_mqtt_publish(args: dict[str, Any]) -> dict[str, Any]:
    if importlib.util.find_spec("paho.mqtt.client") is None:
        return _err(
            "paho-mqtt is not installed",
            status="needs_dependency",
            install_hint="python -m pip install paho-mqtt",
        )
    topic = str(args.get("topic") or "").strip()
    payload = args.get("payload")
    if not topic:
        return _err("missing topic")
    broker = str(args.get("broker") or os.environ.get("GEMMA4_MQTT_BROKER") or "127.0.0.1").strip()
    port = int(args.get("port", os.environ.get("GEMMA4_MQTT_PORT", 1883) or 1883))
    qos = int(args.get("qos", 0))
    retain = bool(args.get("retain", False))
    import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
    client = mqtt.Client()
    user = os.environ.get("GEMMA4_MQTT_USER")
    pwd = os.environ.get("GEMMA4_MQTT_PASSWORD")
    if user:
        client.username_pw_set(user, pwd)
    try:
        client.connect(broker, port, keepalive=10)
    except Exception as exc:
        return _err(f"MQTT connect failed: {exc}", broker=broker, port=port)
    if isinstance(payload, (dict, list)):
        payload_str = json.dumps(payload)
    else:
        payload_str = str(payload) if payload is not None else ""
    info = client.publish(topic, payload_str, qos=qos, retain=retain)
    client.disconnect()
    return _ok(topic=topic, payload_bytes=len(payload_str), broker=f"{broker}:{port}", qos=qos, retain=retain, rc=info.rc, verified=info.rc == 0)
