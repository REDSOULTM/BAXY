"""Dry-run mission evals for realistic composed computer_use workflows.

This does not execute live GUI actions. It checks that realistic missions are
represented as multi-step plans, every step is in the closed primitive set, a
verifier exists, and missions with real-world side effects are explicitly
blocked from live execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class MissionCase:
    name: str
    source_use_case: str
    plan: tuple[tuple[str, str], ...]
    app_family: str
    verifier: str
    live_blocked_reason: str = ""

    @property
    def live_allowed(self) -> bool:
        return not self.live_blocked_reason


MISSIONS: tuple[MissionCase, ...] = (
    MissionCase(
        name="send_message",
        source_use_case="Mandar un mensaje por Discord/WhatsApp",
        plan=(("focus_app", "discord"), ("open_chat", "contacto"), ("type", "hola"), ("send", "")),
        app_family="app_specialist",
        verifier="chat_open_text_inserted_sent_state",
        live_blocked_reason="would send a real message",
    ),
    MissionCase(
        name="join_discord_voice",
        source_use_case="Entrar a una llamada de Discord",
        plan=(("focus_app", "discord"), ("open_voice", "canal"), ("discord_control", "mute")),
        app_family="app_specialist",
        verifier="discord_voice_connected_and_mute_state",
        live_blocked_reason="would join a real voice channel",
    ),
    MissionCase(
        name="fill_web_form",
        source_use_case="Rellenar un formulario web",
        plan=(("open_url", "example.test/form"), ("wait_for", "Email"), ("fill_field", "email=a@b.com"), ("toggle", "terms=on"), ("wait_for", "Ready")),
        app_family="browser",
        verifier="browser_dom_accessibility_and_field_values",
    ),
    MissionCase(
        name="windows_setting_toggle",
        source_use_case="Configurar una opcion en Windows",
        plan=(("focus_app", "settings"), ("wait_for", "opcion"), ("toggle", "opcion=on"), ("wait_for", "Activado")),
        app_family="native_uia",
        verifier="uia_toggle_pattern",
        live_blocked_reason="would change a real system setting",
    ),
    MissionCase(
        name="open_file",
        source_use_case="Buscar un archivo y abrirlo",
        plan=(("focus_app", "explorer"), ("wait_for", "archivo"), ("click", "archivo"), ("wait_for", "contenido")),
        app_family="native_uia",
        verifier="explorer_selection_or_document_window",
        live_blocked_reason="would open a user file",
    ),
    MissionCase(
        name="copy_between_apps_without_clipboard",
        source_use_case="Copiar informacion entre apps sin clipboard",
        plan=(("focus_app", "origen"), ("wait_for", "dato"), ("focus_app", "destino"), ("fill_field", "campo=dato"), ("wait_for", "dato")),
        app_family="cross_app",
        verifier="source_read_and_destination_field_value",
        live_blocked_reason="would write into a real destination app",
    ),
    MissionCase(
        name="app_preference_update",
        source_use_case="Actualizar una preferencia en una app",
        plan=(("focus_app", "app"), ("wait_for", "Ajustes"), ("click", "Ajustes"), ("toggle", "preferencia=on"), ("wait_for", "Activado")),
        app_family="native_uia",
        verifier="uia_or_ocr_state_after_toggle",
        live_blocked_reason="would change a real app preference",
    ),
    MissionCase(
        name="create_note",
        source_use_case="Crear una nota/documento",
        plan=(("focus_app", "editor"), ("type", "nota de prueba"), ("keypress", "ctrl+s"), ("fill_field", "Nombre=test.txt"), ("send", "")),
        app_family="native_uia",
        verifier="file_created_and_editor_text_state",
        live_blocked_reason="would create or save a real file",
    ),
    MissionCase(
        name="play_media",
        source_use_case="Operar multimedia",
        plan=(("open_url", "youtube.com"), ("wait_for", "Buscar"), ("fill_field", "Buscar=cancion"), ("send", ""), ("click", "resultado"), ("wait_for", "Reproduciendo")),
        app_family="browser",
        verifier="browser_page_state_or_media_state",
        live_blocked_reason="would play media on the user's machine",
    ),
    MissionCase(
        name="support_workflow",
        source_use_case="Workflow de soporte",
        plan=(("open_url", "docs.example.test"), ("wait_for", "Paso"), ("focus_app", "app"), ("wait_for", "Ajustes"), ("toggle", "opcion=on"), ("wait_for", "Aplicado")),
        app_family="cross_app",
        verifier="per_step_structural_verifiers",
        live_blocked_reason="would change a real app/system setting",
    ),
    MissionCase(
        name="purchase_game",
        source_use_case="Comprar un juego en una tienda web",
        plan=(("open_url", "store.example.test"), ("wait_for", "Juego"), ("click", "Agregar al carrito"), ("wait_for", "Checkout")),
        app_family="browser",
        verifier="checkout_reached_then_payment_guard",
        live_blocked_reason="purchase/payment flow explicitly excluded",
    ),
    MissionCase(
        name="publish_post",
        source_use_case="Publicar algo simple en una web/app",
        plan=(("open_url", "example.test"), ("fill_field", "post=texto"), ("click", "Publicar")),
        app_family="browser",
        verifier="requires_explicit_publish_confirmation",
        live_blocked_reason="would publish content",
    ),
    MissionCase(
        name="download_file",
        source_use_case="Descargar un archivo",
        plan=(("open_url", "example.test/download"), ("click", "Download"), ("wait_for", "Completado")),
        app_family="browser",
        verifier="download_file_exists_and_size",
        live_blocked_reason="would download a real file",
    ),
    MissionCase(
        name="reservation",
        source_use_case="Reservar algo sin pago inmediato",
        plan=(("open_url", "booking.example.test"), ("fill_field", "fecha=manana"), ("click", "Reservar")),
        app_family="browser",
        verifier="requires_explicit_commit_confirmation",
        live_blocked_reason="would create a real reservation/commitment",
    ),
)


SNAPSHOTS: dict[str, dict[str, Any]] = {
    "browser": {
        "app_kind": "browser",
        "is_browser": True,
        "cdp_candidate": True,
        "ocr_available": True,
        "vision_fallback_available": True,
    },
    "native_uia": {
        "app_kind": "native_or_unknown",
        "uia_available": True,
        "uia_degraded": False,
        "ocr_available": True,
        "vision_fallback_available": True,
    },
    "app_specialist": {
        "app_kind": "native_or_unknown",
        "uia_available": True,
        "uia_degraded": False,
        "ocr_available": True,
        "vision_fallback_available": True,
    },
    "cross_app": {
        "app_kind": "native_or_unknown",
        "uia_available": True,
        "uia_degraded": False,
        "ocr_available": True,
        "vision_fallback_available": True,
    },
}


def _plan_json(mission: MissionCase) -> str:
    return json.dumps([{"op": op, "arg": arg} for op, arg in mission.plan], ensure_ascii=True)


def run_dry(include_blocked: bool = True) -> tuple[bool, list[dict[str, Any]]]:
    from gemma4_agent.computer_use import parse_plan
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.router import CapabilityRouter

    rows: list[dict[str, Any]] = []
    all_ok = True
    for mission in MISSIONS:
        if mission.live_blocked_reason and not include_blocked:
            continue
        plan = parse_plan(_plan_json(mission))
        ops = [step["op"] for step in plan or []]
        primitive_ok = bool(plan) and all(op in CapabilityRouter.verified_ops for op in ops)
        composite_ok = len(ops) >= 2
        verifier_ok = bool(mission.verifier and mission.verifier != "none")
        first_action_op = next((op for op in ops if op not in {"focus_app", "wait", "wait_for"}), ops[0] if ops else "")
        policy = choose_policy(SNAPSHOTS[mission.app_family], first_action_op)
        blocked_ok = bool(mission.live_blocked_reason) or mission.name == "fill_web_form"
        ok = primitive_ok and composite_ok and verifier_ok and bool(policy.primary) and blocked_ok
        all_ok = all_ok and ok
        rows.append({
            "ok": ok,
            "name": mission.name,
            "source_use_case": mission.source_use_case,
            "ops": ops,
            "policy": policy.primary,
            "verifier": mission.verifier,
            "live_allowed": mission.live_allowed,
            "blocked_reason": mission.live_blocked_reason,
        })
    return all_ok, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allowed-only", action="store_true",
                        help="skip live-blocked missions in the report")
    args = parser.parse_args(argv)

    ok, rows = run_dry(include_blocked=not args.allowed_only)
    if args.json:
        print(json.dumps({"ok": ok, "rows": rows}, ensure_ascii=True, indent=2))
    else:
        print("COMPUTER_USE_MISSION_EVAL dry-run")
        for row in rows:
            mark = "PASS" if row["ok"] else "FAIL"
            live = "live-ok" if row["live_allowed"] else "live-blocked"
            print(f"[{mark}] {row['name']}: ops={len(row['ops'])} policy={row['policy']} {live}")
            if row["blocked_reason"]:
                print(f"       blocked: {row['blocked_reason']}")
        print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
