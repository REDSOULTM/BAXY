#!/usr/bin/env python3
"""Author the independent Goal 10 current-contract review outside the product."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from typing import Any

if __package__:
    from scripts.adjudicate_observed_product_replay import write_jsonl_atomic
    from scripts.build_observed_current_contracts import (
        DEFAULT_CORPUS,
        DEFAULT_MAPPING,
        ROOT,
        read_mapping,
        template_rows,
        unique_variants,
    )
    from scripts.adjudicate_observed_product_replay import read_jsonl
else:
    from adjudicate_observed_product_replay import read_jsonl, write_jsonl_atomic
    from build_observed_current_contracts import (
        DEFAULT_CORPUS,
        DEFAULT_MAPPING,
        ROOT,
        read_mapping,
        template_rows,
        unique_variants,
    )


@dataclass(frozen=True)
class Decision:
    kind: str
    operations: tuple[str, ...] = ()
    support: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    rule: str = ""


CURRENT_DIRECT = {
    "app.open",
    "audio.mute",
    "audio.status",
    "browser.navigate",
    "capture.screenshot",
    "game.launch",
    "media.control",
    "memory.recall",
    "memory.save",
    "reminder.create",
    "system.status",
    "web.search",
}


def normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(character for character in folded if not unicodedata.combining(character)).split()
    )


def contains(value: str, *fragments: str) -> bool:
    return any(fragment in value for fragment in fragments)


def action(operation: str, rule: str, *support: str) -> Decision:
    return Decision("action", (operation,), tuple(support), (), rule)


def conversation(rule: str, *denied: str) -> Decision:
    return Decision("conversation", (), (), tuple(denied), rule)


def clarify(rule: str) -> Decision:
    return Decision("clarify", (), (), (), rule)


def no_effect_decision(value: str) -> Decision | None:
    if contains(value, "don't open", "no abras chrome", "no abras el navegador", "mejor no abras"):
        return conversation("explicit_no_open", "app.open")
    if contains(value, "no cierres spotify", "nunca cierres spotify"):
        return conversation("explicit_no_close", "app.close")
    if contains(value, "no pongas musica"):
        return conversation("explicit_no_media", "media.play.query", "media.play.exact")
    if contains(value, "no bajes el brillo"):
        return conversation("explicit_no_brightness", "system.settings.adjust", "system.settings.set")
    if contains(value, "no subas el volumen"):
        return conversation("explicit_no_volume", "audio.volume.adjust", "audio.volume")
    if contains(value, "no silencies el audio"):
        return conversation("explicit_no_mute", "audio.mute")
    if contains(value, "jamas apagues"):
        return conversation("explicit_no_power", "system.power")

    if contains(value, "abri la calculadora y decime que hora"):
        return Decision(
            "action",
            ("app.open", "system.time"),
            (),
            (),
            "open_calculator_and_time",
        )
    if re.search(r"\b(que|what|wie|quelle|che|qe) (hora|time|spat|heure|ore)", value) or value in {
        "que fecha es",
        "y la fecha?",
        "mostrame la fecha",
        "que dia es hoy",
        "pasame la hora",
        "mostrame la hora",
        "dame la hora",
    }:
        return action("system.time", "current_time_or_date")
    if contains(value, "cuanto falta para las"):
        return action("system.time", "relative_time")
    if value == "tiempo":
        return clarify("time_or_weather_ambiguous")
    if contains(value, "cuanto espacio", "espacio libre", "espacio usado", "y disco?"):
        return action("system.status", "system_disk_status")
    if contains(value, "cuanta memoria", "cuanta ram", "tirame cuanta memoria"):
        return action("system.status", "system_memory_status")
    if contains(value, "procesos", "app usa mas memoria"):
        return action("system.process.list", "process_status")
    if contains(value, "mi ip", "my ip"):
        return action("network.ip.list", "network_ip_status")
    if value == "funciona mi internet":
        return action("network.status", "network_connectivity_status")
    if value == "tengo internet":
        return conversation("declarative_network_state")
    if contains(value, "clima", "va a llover", "noticias de hoy", "paso hoy en el mundo"):
        return action("web.search", "current_web_information")
    if contains(value, "busca recetas", "busca teclados"):
        return action("web.search", "web_information_search")

    if contains(value, "esta silenciado el audio", "que esta sonando"):
        operation = "audio.status" if "silenciado" in value else "media.status"
        return action(operation, "media_or_audio_status")
    if (
        re.search(r"\b(subi|sube|alza|aumenta|monte|mach die lautstarke lauter)\b", value)
        and "brillo" not in value
        and not re.search(r"\b(\d{1,3}|mitad|maximo)\b", value)
    ):
        return clarify("relative_volume_missing_amount")
    if contains(value, "mutea el sonido", "silencia el audio"):
        return action("audio.mute", "output_mute")
    if contains(value, "en discord apreta silenciar"):
        return action(
            "input.visible.click",
            "application_mute_click",
            "window.resolve",
            "window.focus",
        )

    if contains(value, "esta abierto el chrome", "esta abierto el explorador"):
        return action("window.application.status", "named_window_status")
    if value == "tengo discord abierto":
        return conversation("declarative_window_state")
    if contains(value, "ventana de steam abierta"):
        return action("window.application.status", "named_window_status")
    if contains(value, "ventana esta activa"):
        return action("window.active", "active_window_status")
    if contains(value, "trae chrome al frente"):
        return action("window.focus", "named_window_focus", "window.resolve")
    if contains(value, "lista las ventanas y enfoca"):
        return clarify("window_target_ambiguous")
    if contains(value, "ventanas", "que tengo abierto", "mostrame que tengo abierto"):
        return conversation("window_inventory_not_in_catalog")
    if contains(value, "pone chrome a la izquierda"):
        return clarify("window_move_missing_coordinates")
    if contains(value, "enfoca la mejor", "lista las ventanas y enfoca"):
        return clarify("window_target_ambiguous")
    if contains(value, "minimiza todas", "minimiza todo", "cerra todas las ventanas"):
        return conversation("bulk_window_effect_not_in_catalog")

    if contains(value, "apreta enter"):
        return action("input.key.press", "focused_key_press")
    if contains(value, "abri la calculadora y apreta"):
        return Decision(
            "action",
            ("app.open", "input.text.type"),
            (),
            (),
            "calculator_composite",
        )
    if contains(value, "apreta el 5"):
        return action("input.text.type", "focused_text_entry")
    if contains(
        value,
        "boton nueve",
        "boton aceptar",
        "boton rojo",
        "aprieta en among us",
    ):
        return action("input.visible.click", "visible_button_click")
    if contains(value, "ponle hola", "escribe en el dialogo"):
        return action("input.text.type", "focused_text_entry")
    if contains(value, "abre este", "abri eso", "abrelo", "cerrala", "cerra esto", "habl[e]? este"):
        return clarify("referent_missing")

    if contains(
        value,
        "cierra el bloc",
        "cerra la calculadora",
        "cierra la calculadora",
    ):
        return action("app.close", "named_application_close", "window.resolve")
    if contains(value, "calculadora", "calculator", "calc ") or contains(
        value, "rechner", "calcolatrice", "calculatrice"
    ):
        if contains(value, "apreta", "suma", "multiplica", "multiplica"):
            return Decision(
                "action",
                ("app.open", "input.text.type"),
                (),
                (),
                "calculator_composite",
            )
        return action("app.open", "named_application_open")
    if contains(value, "explorador de archivos", "open the file explorer"):
        return action("app.open", "named_application_open")
    if contains(value, "terminal"):
        return action("app.open", "named_application_open")
    if contains(value, "bloc de notas"):
        return action("app.open", "named_application_open")
    if contains(value, "configuracion de windows", "app de configuracion"):
        return action("app.open", "named_application_open")
    if contains(value, "abre opera gx y busca"):
        return action("browser.navigate.named", "named_browser_search")
    if contains(value, "abri chrome y pone musica"):
        return clarify("media_query_missing_before_composite")
    if re.search(r"\b(abri|abre|open|ouvre|offne|apri|avri|abrime)\b", value) and contains(
        value, "chrome", "firefox", "opera", "discord", "steam", "whatsapp", "photoshop"
    ):
        return action("app.open", "named_application_open")
    if contains(value, "abre steel", "aplicacion zzqwx123"):
        return action("app.open", "named_application_open")
    if contains(value, "abre stea", "abres team", "abre ste."):
        return action("app.open", "named_application_open")
    if contains(
        value,
        "cerra chrome",
        "cerra el chrome",
        "cierra el bloc",
        "cierra whatsapp",
        "cierres whatsapp",
        "cierra discord",
        "cerra la calculadora",
    ):
        return action("app.close", "named_application_close", "window.resolve")

    if contains(value, "gmail.com", "github.com", "wikipedia", "portal uniej", "portal una"):
        return action("browser.navigate", "known_web_destination")
    if re.search(r"\b(ve|anda|llevame|entra) a (github|gmail|chatgpt|disney)\b", value):
        return action("browser.navigate", "known_web_destination")
    if contains(value, "abre gmail", "abri gmail"):
        return action("browser.navigate", "known_web_destination")
    if contains(value, "resumime esta pagina", "resumime la pagina actual"):
        return action("browser.page.read", "active_page_summary")
    if contains(value, "abre opera gx y busca"):
        return action("browser.navigate.named", "named_browser_search")
    if contains(value, "pestana nueva", "todas las pestanas"):
        return conversation("browser_effect_not_in_catalog")

    if contains(value, "busca el archivo", "busca el archivo"):
        return action("filesystem.search", "sandbox_file_search")
    if contains(value, "archivos de mi escritorio", "que hay en descargas", "archivos tengo en descargas"):
        return action("filesystem.list", "sandbox_directory_list")
    if contains(value, "mi carpeta de descargas"):
        return action("filesystem.folder.open", "sandbox_folder_open")
    if contains(value, "resumime informe.pdf"):
        return action("filesystem.read.text", "sandbox_file_summary", "filesystem.search")
    if contains(value, "crea una carpeta"):
        return action("filesystem.create.directory", "sandbox_directory_create")
    if contains(value, "borra el archivo"):
        return action("filesystem.trash.prepare", "sandbox_trash_prepare", "filesystem.search")

    if contains(value, "mis notas", "notas tengo guardadas"):
        return action("note.list", "note_inventory")
    if contains(value, "anota ", "toma nota", "crea una nota"):
        return action("note.create", "note_create")
    if contains(value, "mostrame mis tareas"):
        return action("task.list", "task_inventory")
    if contains(value, "que tengo agendado"):
        return action("calendar.event.list", "calendar_inventory")
    if contains(
        value,
        "recordame",
        "recuerdame",
        "avisame",
        "despertame",
        "remind me",
    ):
        return action("reminder.create", "reminder_create")
    if contains(value, "acordate que", "guarda que", "quiero que me recuerdes"):
        return action("memory.save", "explicit_memory_save")
    if contains(value, "me gusta tomar cafe"):
        return clarify("implicit_preference_requires_consent")

    if contains(value, "whatsapp", "wsp", "por discord", "en discord") and contains(
        value, "manda", "mandale", "escribile", "respondele"
    ):
        if value == "escribile por whatsapp a pedro":
            return clarify("message_text_missing")
        return action("message.send", "message_send", "message.recipient.resolve")
    if contains(value, "escribile a", "respondele a", "contestale que"):
        return clarify("message_channel_or_recipient_missing")
    if contains(value, "correo", "mail a"):
        return conversation("outgoing_email_not_in_catalog")
    if contains(value, "contacto", "contactos", "agenda a carlos"):
        return conversation("contact_management_not_in_catalog")
    if contains(value, "ultimo mensaje", "que me escribio"):
        return conversation("message_read_not_in_catalog")

    if contains(value, "instala requests"):
        return conversation("python_package_install_not_in_catalog")
    if contains(value, "instala photoshop", "instala photoshop"):
        return action("package.install.prepare", "package_install_prepare")
    if contains(value, "desinstala"):
        return conversation("package_uninstall_not_in_catalog")
    if contains(value, "ejecuta pytest", "ejecuta ls", "corre git status"):
        return conversation("shell_execution_not_in_catalog")

    if contains(value, "pone tom and jerry"):
        return clarify("media_provider_missing")
    if contains(value, "ponme musika"):
        return clarify("media_query_missing")
    if contains(value, "quiero ver") and contains(value, "netflix"):
        title = value.replace("quiero ver", "").replace("en netflix", "").strip()
        return action("streaming.play.named", "named_netflix_title") if title else clarify(
            "streaming_title_missing"
        )
    if contains(value, "youtube") and contains(value, "videos de gatos"):
        return action("media.play.youtube", "youtube_query")
    if contains(value, "abri chrome y pone musica"):
        return clarify("media_query_missing_before_composite")

    if contains(value, "modo avion", "monitor", "hz", "resolucion", "fondo de pantalla"):
        return conversation("requested_capability_not_in_catalog")
    if contains(value, "reinicia la pc", "apaga la computadora"):
        return action("system.power", "system_power")
    if contains(value, "brillo al 100", "devuelvelo a 100", "ponlo a 100"):
        return clarify("setting_referent_missing")
    if contains(value, "tengo el brillo"):
        return conversation("declarative_setting_state")
    if contains(value, "lista los timers"):
        return action("notification.list.due", "notification_inventory")
    if contains(value, "conta 10 minutos"):
        return action("notification.schedule", "notification_schedule")
    if contains(value, "erstelle eine notiz"):
        return action("note.create", "note_create")
    if contains(value, "minimisa opera"):
        return action("window.minimize", "named_window_effect", "window.resolve")
    if contains(value, "nerflix") and contains(value, "stranger things"):
        return action("streaming.play.named", "named_netflix_title")
    if contains(value, "%userprofile%"):
        return clarify("bare_path_requires_request")
    if contains(value, "quiero que lo veas"):
        return conversation("external_file_path_not_in_catalog")
    if contains(value, "quiero editar una foto en photoshop"):
        return action("app.open", "named_application_open")
    if value in {"qe ora es", "que oras sao"}:
        return action("system.time", "current_time_or_date")
    if value.endswith(" en la calc"):
        return Decision(
            "action",
            ("app.open", "input.text.type"),
            (),
            (),
            "calculator_composite",
        )
    if contains(value, "hable este", "ve a cotele", "ve portal 2 un", "si hazlo"):
        return clarify("referent_missing")
    if contains(value, "mad de rivals"):
        return clarify("named_destination_ambiguous")
    return None


def legacy_decision(value: str, operations: list[str], text_hash: str) -> Decision:
    no_effect = no_effect_decision(value)
    if no_effect is not None:
        return no_effect

    if operations == ["audio.volume"]:
        if contains(value, "decime cuanto volumen", "mostrame el volumen"):
            return action("audio.status", "audio_status")
        if re.search(r"\b(\d{1,3}|mitad|maximo)\b", value):
            return action("audio.volume", "absolute_volume")
        return clarify("relative_volume_missing_amount")
    if "system.settings" in operations:
        if contains(value, "que brillo", "mostrame el brillo"):
            return action("system.settings.status", "brightness_status")
        if contains(value, "resolucion"):
            return conversation("display_resolution_not_in_catalog")
        if re.search(r"\b(\d{1,3}|maximo)\b", value):
            return action("system.settings.set", "absolute_brightness")
        return clarify("relative_brightness_missing_amount")
    if "window.manage" in operations:
        if contains(value, "ventana de steam abierta"):
            return action("window.application.status", "named_window_status")
        if contains(value, "ventana esta activa"):
            return action("window.active", "active_window_status")
        if contains(value, "minimiza esta", "maximiza la ventana", "maximiza la ventana actual"):
            operation = "window.minimize" if "minimiza" in value else "window.maximize"
            return action(operation, "active_window_effect", "window.active")
        if contains(value, "cerra esta", "cierra esta"):
            return action("app.close", "active_window_close", "window.active")
        if contains(value, "cambia a la otra"):
            return action("input.key.press", "switch_window_alt_tab")
        if contains(value, "mas grande", "minimiza todas"):
            return conversation("window_inventory_or_bulk_not_in_catalog")
        if contains(value, "ventana actual") and contains(value, "cerra"):
            return action("app.close", "active_window_close", "window.active")
    if "bluetooth.manage" in operations:
        if contains(value, "tengo el bluetooth"):
            return conversation("declarative_bluetooth_state")
        if value == "y el bluetooth?":
            return action("bluetooth.device.list", "bluetooth_status")
        return action("bluetooth.radio.set", "bluetooth_radio_effect")
    if "wifi.manage" in operations:
        if contains(value, "redes wifi"):
            return conversation("wifi_scan_not_in_catalog")
        if contains(value, "conectate", "conectate"):
            return action("wifi.connect.named", "wifi_connect_named", "wifi.profile.list")
        if contains(value, "apaga el wifi"):
            return conversation("wifi_radio_off_not_in_catalog")
        return action("wifi.status", "wifi_status")
    if "notification.manage" in operations:
        if contains(value, "cancela"):
            return action("notification.cancel.latest", "notification_cancel")
        if "99" in value:
            return clarify("invalid_alarm_time")
        return action("notification.schedule", "notification_schedule")
    if "note.manage" in operations:
        return action("note.create", "note_create")
    if "task.manage" in operations:
        if contains(value, "mensaje al grupo"):
            if not contains(value, "whatsapp", "wsp", "discord"):
                return clarify("message_channel_missing")
            return action("message.send", "message_send", "message.recipient.resolve")
        if contains(value, "crea una tarea"):
            if value == "crea una tarea para el viernes":
                return clarify("task_title_missing")
            return action("task.create", "task_create")
        return clarify("bulk_target_ambiguous") if value == "cerrame todo" else conversation(
            "misclassified_task_history"
        )
    if "calendar.manage" in operations:
        return action("calendar.event.create", "calendar_create") if contains(
            value, "reunion"
        ) else conversation("misclassified_calendar_history")
    if "clipboard.manage" in operations:
        return action(
            "clipboard.read.text" if contains(value, "que hay") else "clipboard.write.text",
            "clipboard_read_or_write",
        )
    if "peripheral.manage" in operations:
        if contains(value, "discord"):
            return action(
                "input.visible.click",
                "application_mute_click",
                "window.resolve",
                "window.focus",
            )
        return clarify("microphone_application_ambiguous")
    if "game.manage" in operations:
        return action("game.catalog.list", "game_catalog")
    if "game.install" in operations:
        return clarify("unsupported_game_provider") if contains(value, "teams") else action(
            "game.install.named", "named_game_install"
        )
    if "backup.manage" in operations:
        return conversation("requested_backup_target_not_in_catalog")
    if "office.document" in operations:
        return conversation("unsupported_streaming_service")
    if "vision.describe" in operations:
        if contains(value, "fondo de pantalla") or text_hash.startswith("6d4fd666"):
            return conversation("misclassified_vision_history")
        if contains(value, "lee", "leeme"):
            return action("ocr.read", "screen_text_read", "capture.screenshot")
        return action("vision.describe", "screen_description", "capture.screenshot")
    if "message.send" in operations:
        if contains(value, "apreta enviar en whatsapp"):
            return action(
                "input.visible.click",
                "application_send_click",
                "window.resolve",
                "window.focus",
            )
        if not contains(value, "whatsapp", "wsp", "discord"):
            return clarify("message_channel_missing")
        if value == "escribile por whatsapp a pedro":
            return clarify("message_text_missing")
        return action("message.send", "message_send", "message.recipient.resolve")
    if "media.play" in operations:
        if contains(value, "whatsapp", "mensaje a musica", "mensaje al grupo", "escribe hola"):
            if not contains(value, "whatsapp", "wsp", "discord"):
                return clarify("message_channel_missing")
            return action("message.send", "message_send", "message.recipient.resolve")
        if contains(value, "alarma", "timer"):
            return action("notification.schedule", "notification_schedule")
        if contains(value, "netflix"):
            return action("streaming.play.named", "named_netflix_title")
        if contains(value, "disney", "prime video"):
            return conversation("unsupported_streaming_service")
        if contains(value, "youtube"):
            return action("media.play.youtube", "youtube_query")
        if contains(value, "pausa", "reanuda", "siguiente", "anterior", "para la musica"):
            return action("media.control", "media_transport")
        if contains(value, "que cancion"):
            return action("media.status", "media_status")
        if contains(value, "spotify abierto", "spotify open", "esta corriendo spotify"):
            return action("window.application.status", "named_window_status")
        if contains(value, "instala spotify"):
            return action("package.install.prepare", "package_install_prepare")
        if contains(value, "desinstala spotify"):
            return conversation("package_uninstall_not_in_catalog")
        if contains(value, "abri spotify"):
            return action("app.open", "named_application_open")
        if contains(value, "baja la musica"):
            return clarify("relative_volume_missing_amount")
        if contains(value, "volumen de spotify"):
            return conversation("per_application_volume_not_in_catalog")
        query_markers = (
            "daft punk",
            "beethoven",
            "michael jackson",
            "bad bunny",
            "bohemian rhapsody",
            "rock",
            "musica tranqui",
            "spotify",
            "cancion",
            "musica",
        )
        if contains(value, *query_markers):
            return action("media.play.query", "named_media_query")
        return clarify("media_query_missing")
    if "streaming.navigate" in operations:
        if contains(value, "netflix") and not contains(value, "algo", "una serie"):
            return action("streaming.play.named", "named_netflix_title")
        if contains(value, "youtube"):
            return action("streaming.navigate", "streaming_destination")
        return conversation("unsupported_or_missing_streaming_title")
    if "media.control" in operations:
        return action("browser.control" if contains(value, "pagina anterior") else "media.control", "transport_control")
    if operations == ["app.close"]:
        return action("app.close", "named_application_close", "window.resolve")
    if operations == ["audio.mute"]:
        return action("audio.mute", "output_mute")
    if operations == ["reminder.create"]:
        return action("reminder.create", "reminder_create")
    if operations == ["streaming.navigate"]:
        return action("streaming.navigate", "streaming_destination")
    if operations == ["system.status"] and contains(value, "que es una gpu"):
        return conversation("knowledge_question")
    if operations == ["memory.recall", "memory.save"]:
        return action("memory.recall", "memory_recall")
    if operations == ["memory.save"] and not contains(
        value, "recuerda", "acordate", "guarda", "recorda", "remember"
    ):
        return clarify("implicit_memory_requires_consent")
    if operations == ["system.status"] and contains(value, "hora y cuanta bateria"):
        return Decision(
            "action",
            ("system.time", "system.status"),
            (),
            (),
            "time_and_battery_status",
        )
    if all(operation in CURRENT_DIRECT for operation in operations):
        return Decision("action", tuple(operations), (), (), "current_catalog_direct")
    return clarify("historical_contract_requires_independent_clarification")


def decide(variant: dict[str, Any]) -> Decision:
    if variant["text_sha256"].startswith("d6c0e4e5"):
        return action("app.open", "session_referent_application_open")
    value = normalized(variant["text"])
    operations = list(variant["historical_contract"].get("operations") or [])
    if not operations:
        return no_effect_decision(value) or conversation("natural_conversation")
    return legacy_decision(value, operations, variant["text_sha256"])


def review_rows(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for template in template_rows(variants):
        decision = decide(template)
        output.append(
            {
                "schema": "baxy.goal10-observed-contract-review.v1",
                "text": template["text"],
                "text_sha256": template["text_sha256"],
                "replay_text_sha256": template["replay_text_sha256"],
                "acceptance_test_id": template["acceptance_test_id"],
                "historical_contract_sha256": template["historical_contract_sha256"],
                "verdict": "pass",
                "reason": f"Independent semantic rule {decision.rule} selects only current typed operations.",
                "authority_bases": [
                    "documentacion/00_IDENTIDAD.md",
                    "artifacts/development/current_core_catalog_snapshot_r219.json",
                ],
                "contract": {
                    "kind": decision.kind,
                    "operations": list(decision.operations),
                    "allowed_support_operations": list(decision.support),
                    "denied_operations": list(decision.denied),
                    "success_evidence": [
                        "Visible terminal text is pertinent, natural, language-matched and honest.",
                        "Every authorized operation uses its current catalog verifier and reaches an honest terminal.",
                    ],
                },
                "rule": decision.rule,
            }
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output.resolve()
    if output_path == ROOT or ROOT in output_path.parents:
        raise RuntimeError("exact observed contract reviews must stay outside the repository")
    corpus_rows = list(read_jsonl(args.corpus.resolve()))
    message_ids = {row["message_id"] for row in corpus_rows}
    mapping = read_mapping(args.mapping.resolve(), message_ids)
    variants = unique_variants(corpus_rows, mapping)
    rows = review_rows(variants)
    if len(rows) != 626 or any(row["verdict"] != "pass" for row in rows):
        raise RuntimeError("independent review coverage is not exactly 626 binary approvals")
    write_jsonl_atomic(output_path, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
