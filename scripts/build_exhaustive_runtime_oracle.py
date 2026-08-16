"""Build an independent expected-outcome oracle for every runtime case.

Expectations come from fields stored beside historical inputs (the 7,776-case
mission baseline and every Git revision of ``tool2vec_queries``), then from the
previous frozen contract corpus.  The runtime's own decision is never used as
ground truth.  Cases without an independent expectation remain explicit model
judge work; they are not silently discarded or guessed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_historical_corpus import normalize


REPO = Path(__file__).resolve().parents[1]
PROGRAMACION = REPO.parent
LEDGER = REPO / "artifacts" / "historical_exhaustive"
CASES = LEDGER / "all_executable_cases.jsonl"
BASELINE = PROGRAMACION / "Probando Gemma 4" / "_mission_eval_baseline_7776.jsonl"
EXISTING = REPO / "tests" / "data" / "historical_messages.jsonl"
PROBANDO = PROGRAMACION / "Probando Gemma 4"

NO_EFFECT_TOOL_LABELS = {
    "",
    "ninguna",
    "none",
    "developer",
    "study",
    "knowledge",
    "creative_local",
    "data_analysis",
    "fact_check",
    "source_manager",
}

UNSUPPORTED_TOOL_LABELS = {
    "accessibility",
    "contacts",
    "container",
    "database",
    "dependency",
    "desktop_layout",
    "env",
    "form_filler",
    "gui",
    "habit_tracker",
    "job_manager",
    "maintenance",
    "photo_library",
    "registry",
    "safety",
    "state",
    "terminal",
    "uia",
    "computer_use",
    "verify",
    "watcher",
}

FAMILY_ALIASES = {
    "app": "app",
    "apps": "app",
    "audio": "audio",
    "media_volume": "audio",
    "media_mute": "audio",
    "backup": "backup",
    "browser": "browser",
    "web_open_url": "browser",
    "calendar": "calendar",
    "local_calendar": "calendar",
    "clipboard": "clipboard",
    "capture": "vision",
    "ocr": "vision",
    "filesystem": "filesystem",
    "files": "filesystem",
    "local_search": "filesystem",
    "steam": "game",
    "game": "game",
    "game_launcher": "game",
    "vision": "vision",
    "screenshot": "vision",
    "media": "media",
    "streaming": "media",
    "memory": "memory",
    "notes_tasks": "note_task",
    "note": "note_task",
    "task": "note_task",
    "notification": "notification",
    "reminder": "notification",
    "routine": "routine",
    "system": "system",
    "device_settings": "system_settings",
    "network": "network",
    "wifi": "network",
    "bluetooth": "bluetooth",
    "office": "office",
    "document": "office",
    "printer_scanner": "peripheral",
    "peripheral": "peripheral",
    "whatsapp": "message",
    "discord": "message",
    "message": "message",
    "email": "message",
    "web": "web",
    "download": "package",
    "package": "package",
    "window": "window",
    "input": "input",
}


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def is_runtime(case: dict[str, Any]) -> bool:
    return any(
        str(value).startswith("runtime_")
        for value in case.get("provenance_classes") or ()
    )


def string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def operation_families(values: Iterable[str]) -> tuple[list[str], list[str]]:
    families: set[str] = set()
    unknown: set[str] = set()
    for raw in values:
        value = raw.casefold().strip()
        if value in NO_EFFECT_TOOL_LABELS:
            continue
        parts = [
            part.strip(" .:_-")
            for part in value.replace(",", "/").replace(" ", "/").split("/")
            if part.strip(" .:_-")
        ]
        matched = False
        for part in parts:
            direct = next((family for alias, family in FAMILY_ALIASES.items()
                if part == alias or part.startswith(alias + ".")), None)
            if direct is not None:
                families.add(direct)
                matched = True
                continue
            embedded = next(((alias, family) for alias, family in sorted(
                FAMILY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
                if alias in part), None)
            if embedded is not None:
                families.add(embedded[1])
                matched = True
        if not matched:
            unknown.add(raw)
    return sorted(families), sorted(unknown)


def expectation(
    source: str,
    match: str,
    labels: Iterable[str],
    **metadata: Any,
) -> dict[str, Any]:
    values = sorted({str(value) for value in labels})
    families, unknown = operation_families(values)
    explicit_none = not values or all(
        value.casefold().strip() in NO_EFFECT_TOOL_LABELS for value in values
    )
    explicitly_unsupported = bool(values) and all(
        value.casefold().strip() in UNSUPPORTED_TOOL_LABELS for value in values
    )
    expected_effect = (
        "operation"
        if families
        else "none"
        if explicit_none
        else "unsupported"
        if explicitly_unsupported
        else "unknown"
    )
    return {
        "source": source,
        "match": match,
        "labels": values,
        "families": families,
        "unknown_labels": unknown,
        "expected_effect": expected_effect,
        **metadata,
    }


def add_index(
    exact: dict[str, list[dict[str, Any]]],
    normalized: dict[str, list[dict[str, Any]]],
    text: str,
    item: dict[str, Any],
) -> None:
    exact[text].append(item)
    normalized[normalize(text)].append(item)


def baseline_expectation(row: dict[str, Any]) -> dict[str, Any]:
    """Build the authoritative expectation for one historical baseline row.

    ``also_valid`` contains tolerated alternative tool families, not mandatory
    effects.  In particular, a row with no ``tools_expected`` is still a
    conversational/clarification case even when an evaluator noted that a web
    or browser action would also have been acceptable.
    """

    primary_labels = string_values(row.get("tools_expected"))
    alternative_labels = string_values(row.get("also_valid"))
    labels = [*primary_labels, *alternative_labels] if primary_labels else []
    alternative_families, alternative_unknown = operation_families(
        alternative_labels
    )
    return expectation(
        "mission_baseline_7776",
        "exact",
        labels,
        category=row.get("cat"),
        expected_reply=row.get("reply"),
        issues=row.get("issues") or [],
        alternative_labels=alternative_labels,
        alternative_families=alternative_families,
        alternative_unknown_labels=alternative_unknown,
    )


def baseline_indexes():
    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not BASELINE.is_file():
        return exact, normalized
    for row in read_jsonl(BASELINE):
        item = baseline_expectation(row)
        add_index(exact, normalized, str(row["user_text"]), item)
    return exact, normalized


def existing_indexes():
    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(EXISTING):
        item = expectation(
            "frozen_historical_contract",
            "exact",
            row.get("operations") or [],
            historical_class=row.get("class"),
            expected_state=row.get("expected_state"),
        )
        add_index(exact, normalized, str(row["text_literal"]), item)
    return exact, normalized


def frozen_oracle_indexes():
    """Preserve the hash-bound restored oracle when archaeology inputs are absent."""

    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    frozen = LEDGER / "runtime_oracle.jsonl"
    if not frozen.is_file():
        return exact, normalized
    for row in read_jsonl(frozen):
        expectations = row.get("expectations") or []
        if not expectations:
            expectations = [{
                "source": "restored_runtime_oracle",
                "match": "exact",
                "labels": [],
                "families": row.get("expected_families") or [],
                "unknown_labels": [],
                "expected_effect": row.get("expected_effect") or "review_required",
            }]
        for item in expectations:
            add_index(exact, normalized, str(row["text_literal"]), item)
    return exact, normalized


def tool2vec_indexes():
    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not PROBANDO.is_dir():
        return exact, normalized
    objects = subprocess.run(
        ["git", "-C", str(PROBANDO), "rev-list", "--objects", "--all"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    candidates: set[tuple[str, str]] = set()
    for line in objects.splitlines():
        if " " not in line:
            continue
        object_id, path = line.split(" ", 1)
        if path.endswith("tool2vec_queries.jsonl"):
            candidates.add((object_id, path))
    recovered: dict[tuple[str, str], set[str]] = defaultdict(set)
    for object_id, path in sorted(candidates):
        data = subprocess.run(
            ["git", "-C", str(PROBANDO), "cat-file", "blob", object_id],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode("utf-8", errors="replace")
        for line_number, line in enumerate(data.splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = row.get("q")
            label = row.get("tool")
            if not isinstance(text, str) or not text.strip() or label is None:
                continue
            recovered[(text, str(label))].add(
                f"{object_id}:{path}:{line_number}"
            )
    for (text, label), sources in sorted(recovered.items()):
        item = expectation(
            "tool2vec_queries",
            "exact",
            [label],
            source_revision_count=len(sources),
            source_revisions_sha256=hashlib.sha256(
                "\n".join(sorted(sources)).encode("utf-8")
            ).hexdigest(),
        )
        add_index(exact, normalized, text, item)
    return exact, normalized


def deduplicate(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    for item in items:
        stable = json.dumps(item, ensure_ascii=False, sort_keys=True)
        keyed[hashlib.sha256(stable.encode("utf-8")).hexdigest()] = item
    return [keyed[key] for key in sorted(keyed)]


def choose_expectations(
    text: str,
    indexes: list[
        tuple[
            str,
            dict[str, list[dict[str, Any]]],
            dict[str, list[dict[str, Any]]],
        ]
    ],
) -> tuple[str, list[dict[str, Any]]]:
    for name, exact, _ in indexes:
        if text in exact:
            return f"{name}_exact", deduplicate(exact[text])
    key = normalize(text)
    for name, _, normalized in indexes:
        candidates = normalized.get(key) or []
        signatures = {
            (item["expected_effect"], tuple(item["families"]))
            for item in candidates
        }
        if candidates and len(signatures) == 1:
            adjusted = [{**item, "match": "normalized"} for item in candidates]
            return f"{name}_normalized", deduplicate(adjusted)
    return "unreviewed", []


def incomplete_write_or_type_request(value: str) -> bool:
    """Recognize write/type commands that never provide literal content.

    A language, presentation format, or destination constrains *how* or
    *where* to write; it is not the text to be written.  Keep the rule narrow
    so payloads such as ``escribi 12+12`` and ``type 5+3`` remain actionable.
    """

    command = re.fullmatch(
        r"(?:escribe|escribi|teclea|tipea|write|type)(?: (?P<body>.+))?",
        value,
    )
    if command is None:
        return False
    body = str(command.group("body") or "").strip()
    if not body:
        return True

    placeholder = (
        r"(?:(?:la|el|una|un|the|a) )?"
        r"(?:frase|oracion|texto|contenido|mensaje|phrase|sentence|text|content|message)"
    )
    modifier = (
        r"(?:(?:solo|only) )?(?:en|in) "
        r"(?:espanol|spanish|ingles|english|spanglish|"
        r"mayusculas|uppercase|minusculas|lowercase|negrita|bold|cursiva|italics?|"
        r"(?:el |the )?(?:bloc de notas|notepad|word|documento|document|campo|field))"
    )
    return re.fullmatch(
        rf"(?:{placeholder} )?{modifier}(?: {modifier})*",
        body,
    ) is not None


def bare_context_dependent_selector(value: str) -> bool:
    """Recognize selectors that cannot identify a target without context."""

    return re.fullmatch(
        r"(?:(?:el|la|lo|the) )?"
        r"(?:siguiente|proximo|proxima|anterior|next|previous)"
        r"(?: (?:uno|una|one))?",
        value,
    ) is not None


def bare_name_location_question(value: str) -> bool:
    """Keep vague name-location questions conversational without file cues."""

    return re.fullmatch(
        r"(?:[a-z0-9]+ )?(?:donde|onde|where) (?:esta|ta|is) "
        r"(?:(?:el|o|the) )?(?:nombre|nome|name)",
        value,
    ) is not None


SemanticReviewer = Callable[[str, str], dict[str, Any] | None]


def _review_explicit_guardrails(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review narrow explicit operations and ambiguity guardrails."""

    residue_expectations = {
        "verificar ports ceux": (
            ["network.port.list"],
            "explicit_stable_local_listener_inventory",
        ),
        "que dia es": (
            ["system.time"],
            "explicit_local_calendar_date_read",
        ),
        "di cosa parla il film dune": (
            ["web.search"],
            "explicit_public_movie_topic_search",
        ),
        "se me cerro el juego de repente ayudame a ver por que se cae": (
            ["system.application.crash.diagnose"],
            "explicit_recent_application_crash_diagnostic",
        ),
        "o spotify esta aberto": (
            ["window.application.status"],
            "explicit_visible_application_status_read",
        ),
        "confirma que a janela do chrome esta aberta": (
            ["window.application.status"],
            "explicit_visible_application_status_read",
        ),
        "quiero ver david": (
            ["web.search"],
            "explicit_public_subject_search_after_invocation",
        ),
        "un peu de systemes": (
            [],
            "conversation_topic_request_without_local_action",
        ),
        "siguiente tema": (
            ["media.control"],
            "explicit_next_media_control",
        ),
        "quelle est ma luminosite": (
            ["system.settings.status"],
            "explicit_current_brightness_read",
        ),
        "ejecuta taskkill f im explorer exe": (
            ["system.process.terminate.named"],
            "explicit_forced_exact_process_termination",
        ),
        "quiero saber si batman esta en steam": (
            ["game.catalog.list"],
            "explicit_local_steam_catalog_membership_read",
        ),
        "deconnecte ma session": (
            ["system.power"],
            "explicit_confirmed_windows_session_signout_transition",
        ),
        "metti qui la cosa": (
            ["clipboard.paste"],
            "explicit_paste_current_clipboard_into_focused_control",
        ),
    }
    if value in residue_expectations:
        labels, rule = residue_expectations[value]
        return expectation(
            "semantic_review",
            "semantic",
            labels,
            review_rule=rule,
        )
    if re.fullmatch(r"epic games(?:,? (?:dale|go|abre|open))?", value):
        return expectation(
            "semantic_review",
            "semantic",
            ["app"],
            expected_effect="operation",
            review_rule="named_game_launcher_requires_verified_application_open",
        )
    if re.fullmatch(
        r"(?:what resolution am i using|que resolucion (?:estoy usando|tengo))",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["vision"],
            expected_effect="operation",
            review_rule="display_resolution_requires_verified_screen_dimensions",
        )
    if re.fullmatch(
        r"(?:resume|resumeme|summarize|translate|traduce|lee|read) "
        r"(?:este|esta|this|ese|esa|that) "
        r"(?:pdf|documento|document|archivo|file|presentacion|presentation)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="referenced_document_missing_requires_attachment_or_path",
        )
    if re.fullmatch(
        r"(?:te pedi que )?lo (?:instales|instalaras),? no que "
        r"(?:abras|habras|abrieras) (?:la |su )?pagina|"
        r"install it instead of opening (?:its|the) page",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="package_install_pronoun_without_antecedent_requires_identity",
        )
    if re.fullmatch(
        r"(?:(?:puedes|podrias|can you) )?(?:hacer|haz|crea|make|create) "
        r"(?:un |a )?(?:respaldo|backup)(?: ahora mismo| ahora| right now| now)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["backup.known.create"],
            review_rule="explicit_full_known_folder_private_backup",
        )
    if re.fullmatch(
        r"(?:restaura(?:r)? (?:(?:el|mi|un) )?"
        r"(?:respaldo|backup|copia(?: de seguridad)?)(?: de datos)?"
        r"(?: anterior| mas reciente| ultimo| ultima)?(?: por favor)?|"
        r"restore (?:(?:the|my|a) )?(?:previous |latest |last )?backup(?: please)?|"
        r"ripresta (?:il |mio )?backup(?: per favore)?)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["backup.known.restore.latest"],
            review_rule="explicit_latest_verified_private_backup_restore",
        )
    if re.fullmatch(
        r"(?:un )?(?:respaldo|backup|copia de seguridad)(?: de datos)?"
        r"(?: por favor| please)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["backup.known.create"],
            review_rule="explicit_known_folder_private_backup",
        )
    if re.fullmatch(
        r"(?:comprime|comprimir|zipa|compress|archive|compresse) "
        r"(?:mi|mis|my|meu|minha|mon|mes|el|la|los|las|the) "
        r"(?:escritorio|desktop|bureau|documentos|documents?|fotos|photos?|pictures?|proyectos|projects?) "
        r"(?:en|into|to|em|dans) (?:un|una|a|um) (?:archivo )?zip",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["backup.known.create"],
            review_rule="explicit_known_folder_verified_zip_archive",
        )
    if re.fullmatch(
        r"(?:info|informacion|information|details?) "
        r"(?:de|sobre|about) (?:la |the )?(?:pelicula|movie|film)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["media.status", "web.search"],
            review_rule="current_movie_identity_then_public_information_search",
        )
    if re.fullmatch(
        r"(?:o |lo |y )?que (?:esta )?(?:tocando|sonando|reproduciendo)|"
        r"what (?:is|'s) playing",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["media.status"],
            review_rule="explicit_current_media_status_read",
        )
    if re.fullmatch(
        r"(?:quiero ver|i want to see) ([a-z0-9][a-z0-9 ._-]{1,120})",
        value,
    ) and not re.search(
        r"\b(?:algo|anything|esto|this|eso|that|mis archivos|my files|"
        r"pantalla|screen)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["web.search"],
            review_rule="explicit_concrete_public_subject_view",
        )
    if re.fullmatch(
        r"(?:saber|ver|mostrar|muestra|show) (?:la |mi |my )?"
        r"(?:cita|appointment)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["calendar.event.list"],
            review_rule="explicit_upcoming_calendar_appointment_read",
        )
    if re.fullmatch(
        r"(?:verifica|verificar|comprueba|revisa|check|verify)(?: el)? dns"
        r"(?: rapido| quickly| now)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["network.dns.status"],
            review_rule="explicit_windows_dns_status_diagnostic",
        )
    ping_target = re.fullmatch(
        r"ping(?: a)? (?:el |the )?([a-z0-9]+(?:[ .-][a-z0-9]+){0,5})",
        value,
    )
    if ping_target and ping_target.group(1) not in {
        "eso", "esto", "it", "that", "this", "ese servidor", "that server",
    }:
        return expectation(
            "semantic_review",
            "semantic",
            ["network.ping"],
            review_rule="explicit_bounded_network_ping",
        )
    if re.fullmatch(
        r"(?:show|muestra|dime)(?: me)? (?:whoami|current user|usuario actual)|whoami",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["system.identity"],
            review_rule="explicit_effective_windows_identity_read",
        )
    if re.fullmatch(
        r"(?:recuerdame|recordame) (?:la |sobre la )?reunion manana "
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?|"
        r"remind me (?:about )?the meeting tomorrow (?:at )?"
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["notification.schedule"],
            review_rule="explicit_dated_meeting_notification",
        )
    if re.fullmatch(
        r"(?:juega|abre|lanza|play|launch) (?:cualquier cosa|anything)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["game.catalog.list", "game.launch"],
            review_rule="explicit_any_installed_game_selection_and_launch",
        )
    if value == "esta corriendo comfyui":
        return expectation(
            "semantic_review", "literal", ["system.process.list"],
            review_rule="explicit_named_process_status_query",
        )
    if value == "ouvir o cliente de riot":
        return expectation(
            "semantic_review", "literal", ["app.open"],
            review_rule="explicit_riot_client_open",
        )
    if value in {
        "haz click en el boton aceptar visible",
        "haz click en el boton aceptar si esta visible",
        "clique sur le bouton valider de la page",
        "click the accept button you see on my screen",
    }:
        return expectation(
            "semantic_review", "literal", ["input.visible.click"],
            review_rule="explicit_visible_control_click",
        )
    if value == "agrega una linea al final de notas txt":
        return expectation(
            "semantic_review", "literal", ["filesystem.sandbox.append.named"],
            review_rule="explicit_named_sandbox_append",
        )
    if value == "move backup txt a logs backup txt":
        return expectation(
            "semantic_review", "literal", ["filesystem.sandbox.move.named"],
            review_rule="explicit_named_sandbox_move",
        )
    if value == "programa una tarea que se repita todos los dias a las 9":
        return expectation(
            "semantic_review", "literal", ["notification.schedule"],
            review_rule="explicit_daily_windows_notification_task",
        )
    if value == "set up a reminder for friday":
        return expectation(
            "semantic_review", "literal", ["notification.schedule"],
            review_rule="explicit_friday_windows_reminder",
        )
    if re.fullmatch(r"(?:la )?tecla,? (?:que|what)", value):
        return expectation(
            "semantic_review", "semantic", [],
            review_rule="incomplete_key_question_requires_clarification",
        )
    if bare_name_location_question(value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="bare_name_location_question_has_no_file_search_authority",
        )
    if bare_context_dependent_selector(value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="bare_context_dependent_selector_requires_clarification",
        )
    if incomplete_write_or_type_request(value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="write_or_type_literal_content_missing_requires_clarification",
        )
    if re.fullmatch(
        r"(?:type .+ in (?:notepad|word)|"
        r"(?:in|en) (?:notepad|word|el bloc de notas|la calculadora|the calculator) "
        r"(?:write|escribe|escribi) .+(?: (?:and|y) (?:press|apreta) enter)?|"
        r"(?:abre|abri|open) (?:el |la |the )?(?:notepad|bloc de notas|calculadora|calculator),? "
        r"(?:y )?(?:write|type|escribe|escribi) .+|"
        r"(?:type|escribe|escribi) .+ (?:in|en) (?:el |la |the )?"
        r"(?:notepad|word|bloc de notas|calculadora|calculator))",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["app.open", "input.text.type"],
            review_rule="explicit_text_input_into_named_application",
        )
    if re.fullmatch(
        r"(?:mueve|move) (?:el |the )?(?:mouse|raton|pointer) (?:al |to the )?"
        r"(?:centro|center)(?: (?:de|of) (?:la |the )?(?:pantalla|screen))?|"
        r"(?:haz |make )?(?:mouse )?click (?:ahi|there)(?: fast| rapido)?|"
        r"(?:haz|make) scroll (?:hacia )?(?:abajo|down)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["input.pointer.control"],
            review_rule="explicit_pointer_control_action",
        )
    if re.fullmatch(
        r"(?:presiona|aprieta|press|send) (?:la |the )?"
        r"(?:combinacion |hotkey )?(?:control|ctrl)[ +]shift[ +](?:escape|esc)|"
        r"(?:type|press|presiona) (?:the |la )?(?:key |tecla )?"
        r"(?:escape|esc)(?: key)? (?:and then|then|y luego) "
        r"(?:press )?(?:the |la )?(?:win|windows)(?: key| tecla)?|"
        r"(?:presiona|aprieta|press) (?:la |the )?(?:tecla |key )?(?:win|windows)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["input.key.press"],
            review_rule="explicit_key_chord_or_sequence",
        )
    if re.fullmatch(
        r"(?:presiona|aprieta|press) (?:la )?(?:combinacion )?alt[ +]tab|"
        r"(?:abre|open) (?:el )?(?:menu contextual|context menu)|"
        r"(?:pega|paste) (?:el )?(?:texto )?(?:del |from the )?(?:portapapeles|clipboard)",
        value,
    ):
        return expectation(
            "semantic_review", "semantic", ["input.key.press"],
            review_rule="explicit_physical_key_or_paste_action",
        )
    if re.fullmatch(r"(?:elige|selecciona|escoge) (?:la )?opcion (?:de )?copiar", value):
        return expectation(
            "semantic_review", "semantic", ["clipboard.copy"],
            review_rule="explicit_focused_selection_copy_action",
        )
    if re.fullmatch(
        r"(?:recarga|actualiza|reload|refresh) (?:la |the )?(?:pagina|page) actual|"
        r"(?:pon|pone|coloca|set|put) (?:el |the )?(?:video )?(?:en |in )?"
        r"(?:pantalla completa|fullscreen)(?: (?:el |the )?video)?",
        value,
    ):
        return expectation(
            "semantic_review", "semantic", ["browser.control"],
            review_rule="explicit_current_browser_control_action",
        )
    if re.fullmatch(r"(?:dame|dime|show me|tell me) (?:el )?layout(?: ahora| now)?", value):
        return expectation(
            "semantic_review", "semantic", ["input.keyboard.status"],
            review_rule="explicit_keyboard_layout_status",
        )
    if re.fullmatch(r"dame las notas", value):
        return expectation(
            "semantic_review", "semantic", ["note.list"],
            review_rule="explicit_local_note_list",
        )
    if (re.search(r"\b(?:volumen|volume|sound)\b", value)
            and re.search(r"\b(?:sube|subi|sobe|aumenta|incrementa|raise|increase|turn up|"
                          r"baja|disminuye|reduce|abaixa|lower|decrease|turn down)\b", value)
            and not re.search(r"\b\d{1,3}\b", value)):
        return expectation(
            "semantic_review", "semantic", ["audio.volume.adjust"],
            review_rule="explicit_relative_output_volume_adjustment",
        )
    if (re.search(r"\b(?:brillo|brightness|screen)\b", value)
            and re.search(r"\b(?:sube|subi|sobe|aumenta|incrementa|raise|increase|turn up|"
                          r"baja|disminuye|reduce|abaixa|lower|decrease|turn down|dim)\b", value)
            and not re.search(r"\b\d{1,3}\b", value)):
        return expectation(
            "semantic_review", "semantic", ["system.settings.adjust"],
            review_rule="explicit_relative_brightness_adjustment",
        )
    if re.fullmatch(
        r"(?:(?:conecta(?:te)?|connect)(?: to)? (?:al |a la |el |la |the )?"
        r"(?:wifi|wi fi)(?: network| red)?(?: de| a| named)?|"
        r"(?:ponme|poneme) en (?:el )?(?:wifi|wi fi)|cambia (?:el )?(?:wifi|wi fi) a) .+",
        value,
    ):
        return expectation(
            "semantic_review", "semantic", ["wifi.connect.named"],
            review_rule="explicit_named_saved_wifi_connection",
        )
    if (re.search(r"\bsteam\b", value)
            and re.search(r"\b(?:instala|instalame|descarga|download|install)\b", value)
            and not re.search(r"\b(?:cualquier juego|any game)\b", value)):
        return expectation(
            "semantic_review", "semantic", ["game.install.named"],
            review_rule="explicit_named_steam_installation",
        )
    if re.fullmatch(
        r"(?:abre|open) (?:el |the )?(?:teclado|on screen keyboard)(?:,? por favor| please)?",
        value,
    ):
        return expectation(
            "semantic_review", "semantic", ["input.keyboard.open"],
            review_rule="explicit_on_screen_keyboard_open",
        )
    if re.fullmatch(
        r"(?:(?:usa|use) (?:el |the )?(?:idioma|keyboard layout|layout) "
        r"(?:del teclado )?(?:para |for )?(?:espanol|spanish)|"
        r"cambia (?:el )?idioma (?:del )?teclado(?: a espanol)?|cambia idioma teclado)",
        value,
    ):
        return expectation(
            "semantic_review", "semantic", ["input.keyboard.layout"],
            review_rule="explicit_spanish_keyboard_layout",
        )
    if re.fullmatch(
        r"(?:(?:posso|pode|can i) )?(?:trocar|mudar|change|switch) "
        r"(?:o |the )?(?:microfone|microphone)(?: agora| now)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="default_microphone_switch_missing_target_requires_clarification",
        )
    if re.fullmatch(
        r"(?:check|show|read|dime|muestra) (?:the |el )?"
        r"(?:wifi|wi fi) (?:connection )?(?:status|estado)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["wifi.status"],
            review_rule="explicit_wifi_connection_status_read",
        )
    if re.fullmatch(r"o som\?? manda", value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="ambiguous_portuguese_audio_action_requires_clarification",
        )
    if re.fullmatch(r"troca a entrada", value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="ambiguous_portuguese_input_switch_requires_device_clarification",
        )
    if re.fullmatch(r"(?:ponme|poneme|ponime) la del .+", value):
        return expectation(
            "semantic_review",
            "semantic",
            ["media.play.query"],
            review_rule="explicit_colloquial_media_search_and_play",
        )
    if re.search(r"\b(?:microfono|microphone|mic)\b", value) and re.search(
        r"\b(?:mute|mutea|silencia|unmute|volumen|volume)\b", value
    ):
        return expectation(
            "semantic_review", "semantic", ["audio.microphone.mute"],
            review_rule="explicit_default_microphone_mute",
        )
    if re.search(r"\b(?:escaner|escaneres|scanner|scanners)\b", value) and re.search(
        r"\b(?:disponibles|available|tienes|tengo|lista|list)\b", value
    ):
        return expectation(
            "semantic_review", "literal", ["peripheral.list"],
            review_rule="explicit_scanner_inventory",
        )
    active_text = re.fullmatch(r"(?:escribe|escribi|type) (?P<body>.+)", value)
    if active_text is not None:
        body = active_text.group("body").strip()
        excluded = re.search(
            r"\b(?:whatsapp|discord|wsp|correo|email|mensaje|archivo|temp|busqueda|"
            r"python|funcion|acrostico|continuacion|parrafo)\b",
            body,
        )
        vague = re.fullmatch(
            r"(?:(?:la|el|esta|este|the|this) )?(?:frase|texto|text|phrase)|"
            r"(?:esto|eso|this|that)(?: ya| now)?|max|my email here",
            body,
        )
        if excluded is None and vague is None:
            return expectation(
                "semantic_review",
                "semantic",
                ["input.text.type"],
                review_rule="explicit_literal_text_input_in_active_control",
            )
    if re.fullmatch(r"(?:tiempo|weather|time)", value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="isolated_time_or_weather_noun_requires_scope",
        )
    if re.fullmatch(
        r"(?:(?:what(?:'s| is)|tell me|show me) (?:the )?"
        r"(?:weather(?: forecast)?|forecast)(?: like)?|"
        r"(?:weather forecast|forecast)(?: for)?|"
        r"(?:(?:cual|como) (?:es|esta|estara)|dime|muestrame) (?:el )?"
        r"(?:clima|pronostico(?: del tiempo)?)(?: de| para)?) "
        r"(?:today|tomorrow|this week|hoy|manana|esta semana)"
        r"(?: (?:in|for|en|para) [a-z0-9 .,'-]{2,80})?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["web.search"],
            review_rule="explicit_current_weather_forecast",
        )
    if re.fullmatch(
        r"(?:(?:puedes|can you) )?(?:ver|check) si (?:tengo|i own) "
        r"(?:comprad[oa] |purchased )?(?:ese|esa|that|this) (?:juego|game)(?: en| on) .+|"
        r"(?:ve|anda|go)(?: a| to) (?:mi|my) (?:biblioteca|library)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="demonstrative_game_or_providerless_library_requires_context",
        )
    if re.fullmatch(
        r"(?:(?:cuanto (?:es|da)|calcula|calculame|resolve|resuelve|"
        r"multiplica|multiply) )?"
        r"-?\d+(?:[.,]\d+)? (?:por|times|by|x|\*|mas|plus|menos|minus|"
        r"dividido (?:por|entre)|divided by|/|\+|-) -?\d+(?:[.,]\d+)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="explicit_arithmetic_question_is_conversation",
        )
    if re.fullmatch(
        r"(?:abre (?:la )?(?:cuestion|tema|asunto) (?:del|de la|sobre) .+|"
        r"(?:(?:open|abre|abri) (?:the |el |la )?(?:music|musica|audio|video) "
        r"(?:thingy|thing|app|application|coso|cosa)|"
        r"(?:[a-z0-9]+ )?(?:el|la|the) (?:otro|otra|other) "
        r"(?:app|application|aplicacion))|"
        r"(?:(?:pero )?(?:por que .+ )?no me abriste (?:el )?juego,? )?"
        r"(?:abrilo|abrelo|lanzalo|ejecutalo)(?: ya)?|"
        r"(?:(?:por favor|please|pues|entonces|then) )?"
        r"(?:bajalo|subelo|ponlo|hazlo|hacelo|do it|lower it|raise it)"
        r"(?: por favor| please| then)?|"
        r"(?:la|el) que estaba ahi|(?:mira|mirar|revisa|ver) lo de .+|"
        r"(?:si,? )?lo hiciste pero no (?:funciono|sirvio)|"
        r"you did it but it did not work|"
        r"(?:agenda|calendar) next|i need my list|"
        r"(?:si|yes|no|okay|ok)|(?:tiempo|hora|weather)(?: gemma)?[ ,]+(?:tiempo|hora|weather)|"
        r".+ le gana a .+)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="contextual_or_ambiguous_reference_requires_clarification",
        )
    if re.match(
        r"^(?:(?:recuerdame|recordame) que (?:prefiero|me gusta|uso)|"
        r"remind me that i (?:prefer|like|use))\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["memory.save"],
            review_rule="explicit_private_preference_memory_request",
        )
    if (
        re.fullmatch(r"(?:recuerdame|recordame|remind me) .+ (?:hoy|today)", value)
        and not re.search(r"\b(?:a las|at) \d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", value)
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="today_reminder_missing_clock_time_requires_clarification",
        )
    if re.fullmatch(r"(?:recuerdame|recordame|remind me) .+", value) and not re.search(
        r"\b(?:hoy|manana|tomorrow|today|esta noche|tonight|a las|at \d|"
        r"(?:en|in) (?:\d+|un|una|uno|one|dos|two|tres|three) "
        r"(?:minutos?|minutes?|horas?|hours?|dias?|days?)|"
        r"(?:el|on) \d{1,2}(?: de [a-z]+)?|lunes|martes|miercoles|jueves|"
        r"viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="reminder_due_time_missing_requires_clarification",
        )
    if re.fullmatch(
        r"(?:(?:reproduce|reproduci|play) (?:el |the )?(?:ultimo|last|anterior|previous) "
        r"(?:video|pelicula|movie|song|cancion) (?:que |i )?(?:vi|saw|watched)|"
        r"(?:can you )?remind me .+ (?:later|sometime)|"
        r"(?:recuerdame|recordame) .+ (?:despues|mas tarde)|"
        r"(?:por favor|please) (?:el |the )?(?:volumen|volume)|"
        r"(?:please )?(?:deduplicate|deduplica) (?:my |mis )?(?:stored )?(?:files|archivos))",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="underspecified_history_time_setting_or_deduplication_requires_clarification",
        )
    if re.fullmatch(r"(?:run|ejecuta|ejecutar|corre) (?:npm|pnpm|yarn|pip|pip3) install", value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="package_install_without_identity_or_project_is_safely_clarified",
        )
    if re.fullmatch(
        r"(?:(?:run|ejecuta|ejecutar|corre) )?taskkill "
        r"(?:(?:f|t|im) )*(?:a )?[a-z0-9_-]+(?: exe)?(?:(?: f| t))?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["system.process.terminate.named"],
            review_rule="explicit_exact_named_process_forced_termination",
        )
    if re.fullmatch(
        r"(?:(?:force|forcibly) )?"
        r"(?:mata|matar|cierra|cerrar|cerra|termina|terminar|close|kill|terminate) "
        r"(?:a |el |la |the )?[a-z0-9_.-]+"
        r"(?: a la fuerza| de forma forzada| forcefully| forcibly| by force)?"
        r"(?: con taskkill| using taskkill)?(?: por favor| please| pls)?",
        value,
    ) and re.search(r"\b(?:a la fuerza|forzada|force|forcibly|taskkill|kill)\b", value):
        return expectation(
            "semantic_review",
            "semantic",
            ["system.process.terminate.named"],
            review_rule="explicit_named_application_forced_termination",
        )
    if re.fullmatch(
        r"[a-z0-9]+(?:ito|ita),? (?:ya|ahora|now)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="short_diminutive_followup_has_no_grounded_action",
        )
    if re.fullmatch(
        r".+?,? (?:lo otro|la otra|the other one) (?:tambien|too)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="elliptical_other_action_requires_prior_context",
        )
    if re.fullmatch(
        r"(?:busca(?:me)?|search(?: for)?|find) [a-z0-9]{1,3}",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="very_short_search_term_is_safely_clarified",
        )
    if re.search(
        r"\b(?:raised to the power of|elevad[oa] a la potencia|to the power of)\b",
        value,
    ) or re.fullmatch(r"(?:calculate|calcula|resolve|find the result of) [0-9+*/().^ -]+", value):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="bounded_arithmetic_is_conversation_not_public_search",
        )
    if re.fullmatch(
        r"(?:consulta|check|query) (?:una |an )?(?:app|application|aplicacion) "
        r"(?:por|by) (?:nombre|name).+",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="application_inventory_request_without_application_name",
        )
    if re.fullmatch(
        r"(?:no,? )?(?:dejalo|leave it)(?:,? )?(?:cierrala|cierralo|close it)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="pronoun_only_close_requires_resolved_conversation_context",
        )
    if re.fullmatch(
        r"(?:abre|abri|open) (?:ese|esa|that|it) (?:pdf|archivo|file)(?: ahora| now)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="demonstrative_file_open_requires_resolved_conversation_context",
        )
    return None


def _review_semantic_operations(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review the ordered semantic operation classifier."""

    semantic_operations: list[str] | None = None
    semantic_rule = ""
    named_application_close = re.fullmatch(
        r"(?:(?:puedes|podrias|can you|could you|necesito que|please) )?"
        r"(?:cierra|cerrar|cierres|cerra|close|schliess|schliesse|encerra|beende|quit)"
        r"(?: la| el| the| die| das| o| a)?"
        r"(?: app| aplicacion| application| ventana de| window of)? "
        r"([a-z0-9][a-z0-9 ._-]{0,80}?)"
        r"(?: de forma normal| normalmente| normally| por favor| please| pls| ahora| now|"
        r",? (?:ya )?no (?:la|lo) necesito|,? i (?:do not|don['’]?t) need it anymore)?",
        value,
    )
    blocked_close_target = bool(
        named_application_close
        and re.search(
            r"\b(?:that|this|current|previous|esa|ese|esta|este|actual|anterior|"
            r"window|ventana|finestra|tab|tabs|pestana|pestanas|pagina|page|"
            r"que abriste|todo|todos|toda|todas|everything|all|proceso|procesos|"
            r"process|processes|popup|pendiente|bugs?|segundo|segunda|youtube|force|fuerza)\b",
            named_application_close.group(1),
        )
    )
    if named_application_close and not blocked_close_target:
        semantic_operations = ["app.close"]
        semantic_rule = "explicit_named_application_normal_close"
    elif re.fullmatch(
        r"(?:(?:puedes|podrias|can you|could you) )?"
        r"(?:abre|abri|abrir|open|launch) (?:el |the )?"
        r"(?:navegador|browser) (?:microsoft edge|edge|google chrome|chrome|firefox|opera(?: gx)?)"
        r"(?: por favor| please| pls)?",
        value,
    ):
        semantic_operations = ["app.open"]
        semantic_rule = "explicit_named_browser_application_open"
    elif re.fullmatch(
        r"(?:(?:que|cual) (?:aplicacion|app|ventana) (?:esta )?activa(?: ahora)?|"
        r"(?:que|cual) ventana esta activa(?: ahora)?|"
        r"what (?:app|application|window) is active(?: right now)?)",
        value,
    ):
        semantic_operations = ["window.active"]
        semantic_rule = "explicit_active_window_inventory"
    elif re.fullmatch(
        r"(?:(?:que|cual) dispositivo de audio tengo activo|"
        r"(?:que|cual) es (?:mi )?dispositivo de audio activo|"
        r"what(?:'s| is) (?:my |the )?active audio (?:output )?device|"
        r"which audio (?:output )?device is active)",
        value,
    ):
        semantic_operations = ["audio.status"]
        semantic_rule = "explicit_active_audio_device_inventory"
    elif re.fullmatch(
        r"(?:(?:qu[ea?]+|cuales) recordatorios tengo(?: pendientes| activos)?|"
        r"(?:lista|muestra)(?:me)? mis recordatorios|"
        r"what reminders do i have(?: pending| active)?)",
        value,
    ):
        semantic_operations = ["reminder.list"]
        semantic_rule = "explicit_reminder_inventory"
    elif re.fullmatch(
        r"(?:(?:please|por favor) )?"
        r"(?:pause|pausa|pausar|resume|reanuda|reanudar|continue|continua|continuar) "
        r"(?:the |el |la )?(?:current |actual )?"
        r"(?:video|audio|media|music|musica|song|cancion)"
        r"(?: actual| current)?"
        r"(?: i was (?:watching|listening to)| que (?:estaba|estoy) "
        r"(?:viendo|escuchando|reproduciendo))?"
        r"(?: please| por favor)?",
        value,
    ):
        semantic_operations = ["media.control"]
        semantic_rule = "explicit_current_audio_or_video_control"
    elif re.fullmatch(
        r"(?:continua|sigue|keep|continue)(?: (?:la musica|the music))? "
        r"(?:tocando|reproduciendo|playing)",
        value,
    ):
        semantic_operations = ["media.control"]
        semantic_rule = "explicit_current_media_resume"
    elif re.fullmatch(
        r"(?:(?:que|cuales) (?:eventos )?(?:tengo )?"
        r"(?:agendad[oa]s?|en (?:mi )?agenda|scheduled) "
        r"(?:para |for )?(?:hoy|today|manana|tomorrow|esta semana|this week)|"
        r"que tengo agendado (?:hoy|today|manana|tomorrow|esta semana|this week)|"
        r"what (?:events )?do i have scheduled (?:hoy|today|manana|tomorrow|esta semana|this week))",
        value,
    ):
        semantic_operations = ["calendar.event.list"]
        semantic_rule = "explicit_relative_calendar_inventory"
    elif re.fullmatch(
        r"(?:cuando|cuante) (?:yo |te )?(?:diga|dija) .+ "
        r"(?:(?:quiero que|(?:es )?para que) .+)?"
        r"(?:parar(?:/| y )reanudar|pausa o reproduce|play or pause).+",
        value,
    ):
        semantic_operations = ["routine.phrase.create"]
        semantic_rule = "grounded_phrase_media_routine"
    elif re.fullmatch(
        r"(?:cuando|cuante) (?:yo )?(?:diga|dija) .+ "
        r"(?:quiero que|(?:es )?para que) .+"
        r"(?:captura de pantalla|captura|pantallazo|screenshot).+",
        value,
    ):
        semantic_operations = ["routine.phrase.create"]
        semantic_rule = "grounded_phrase_capture_routine"
    elif re.fullmatch(
        r"(?:ver|view|check|listar|lista|list|mostrar|muestra|show) "
        r"(?:los |the |all )?(?:(?:activos|active|running) )?"
        r"(?:procesos|processes)(?: (?:activos|running))?(?: (?:ahora|now))?",
        value,
    ):
        semantic_operations = ["system.process.list"]
        semantic_rule = "explicit_local_process_inventory"
    elif re.fullmatch(r"(?:que estoy escuchando|what am i listening to)", value):
        semantic_operations = ["media.status"]
        semantic_rule = "explicit_current_media_status"
    elif re.fullmatch(
        r"(?:abre|abri|open)(?: me)? (?:el |the )?(?:"
        r"(?:ultimo|last|most recent|mas reciente) (?:archivo|file) "
        r"(?:que )?(?:descargue|descargado|downloaded)(?: file)?|"
        r"(?:ultimo|last|most recent|mas reciente) (?:downloaded|descargado) (?:archivo|file))",
        value,
    ):
        semantic_operations = ["filesystem.file.open.latest"]
        semantic_rule = "explicit_latest_known_folder_file_open"
    elif (
        re.search(r"\b(?:precio|precios|price|prices|cost|costs|deals?|ofertas?)\b", value)
        and re.search(r"\b(?:actual|actuales|current|latest|hoy|today)\b", value)
        and not re.search(r"\b(?:uso|usage|vram|temperatura|temperature|mi gpu|my gpu)\b", value)
    ):
        semantic_operations = ["web.search"]
        semantic_rule = "current_product_prices_require_public_search"
    elif re.fullmatch(
        r"(?:(?:anota|apunta)(?: que)?|toma nota de que|note down|write down) .+",
        value,
    ):
        semantic_operations = ["note.create"]
        semantic_rule = "explicit_private_note_creation"
    elif re.fullmatch(
        r"(?:que|cual|what) version (?:de |of )?.+ "
        r"(?:tengo instalada|tengo instalado|is installed|do i have installed)",
        value,
    ):
        semantic_operations = ["app.installed"]
        semantic_rule = "installed_application_version_inventory"
    elif re.fullmatch(
        r"(?:volve|regresa|retrocede|go back) (?:a |to )?(?:la |the )?"
        r"(?:(?:pagina|page) (?:anterior|previous)|previous page)",
        value,
    ):
        semantic_operations = ["browser.control"]
        semantic_rule = "explicit_browser_history_back"
    elif (
        re.search(r"\b(?:cuando|when)\b", value)
        and re.search(r"\b(?:sale|estrena|estreno|release|released|coming out)\b", value)
    ):
        semantic_operations = ["web.search"]
        semantic_rule = "current_release_date_requires_public_search"
    elif re.fullmatch(r"(?:bloquea|lock) (?:el |the |my |mi )?(?:pc|computer|equipo)", value):
        semantic_operations = ["system.power"]
        semantic_rule = "explicit_local_session_lock"
    elif re.fullmatch(
        r"(?:busca|buscar|investiga|search(?: for)?|look up) "
        r"(?:informacion (?:sobre|acerca de) |information (?:about|on) )?"
        r".+?(?: y explicamelo| and explain it(?: to me)?)",
        value,
    ):
        semantic_operations = ["web.search"]
        semantic_rule = "explicit_public_research_and_explanation"

    if re.fullmatch(
        r"(?:no (?:abras|abran|open) (?:nada|anything|ninguna app|any app) )?"
        r"(?:solo |just )?(?:dime|decime|tell me|comprueba|check) si "
        r".+ (?:esta|is) instalad[oa]",
        value,
    ):
        semantic_operations = ["app.installed"]
        semantic_rule = "negative_open_constraint_application_inventory"
    elif (
        re.fullmatch(
            r"(?:busca|search(?: for)?|look up) .+ (?:y dime|and tell me) "
            r"(?:quien|who|que|what|como|how) .+",
            value,
        )
        or (
            re.search(
                r"\b(?:investiga|investigar|research (?:for|about|whether|if)|look up)\b",
                value,
            )
            and not re.search(r"\b(?:archivo|file|carpeta|folder|nota|note)\b", value)
            and not re.search(
                r"\b(?:saved|guardad[oa]s?|source|fuente|snapshot|materials?|"
                r"materiales?|steam games?|steam library)\b",
                value,
            )
            and not re.search(r"\b(?:whatsapp|discord|send|envia|manda)\b", value)
        )
        or (
            re.search(r"\b(?:mejor|best|lowest|menor) (?:precio|price|oferta|deal)\b", value)
            and re.search(r"\b(?:donde|where|comprar|buy|conseguir|get)\b", value)
        )
    ):
        semantic_operations = ["web.search"]
        semantic_rule = "explicit_public_research_or_price_comparison"
    elif re.fullmatch(
        r"(?:si|whether) (?:hay|there is) (?:algo|something) (?:sonando|playing)|"
        r"(?:hay|is there) (?:algo|something) (?:sonando|playing)",
        value,
    ):
        semantic_operations = ["media.status"]
        semantic_rule = "explicit_current_media_presence_query"
    elif (
        re.search(r"\b(?:clipboard|portapapeles)\b", value)
        and re.search(r"\b(?:que|cual|donde|what|which|where)\b", value)
        and not re.search(r"\b(?:escribe|write|copia|copy|pon|put|pega|paste|borra|clear)\b", value)
    ):
        semantic_operations = ["clipboard.read.text"]
        semantic_rule = "telegraphic_clipboard_read_query"
    elif re.fullmatch(
        r"(?:(?:puedes|podrias|can you|could you) )?"
        r"(?:lee|leeme|read|describe|describeme|extrae|extract) .+ "
        r"(?:en|de|from|on) (?:la |the )?(?:pantalla|screen)|"
        r"(?:(?:puedes|podrias|can you|could you) )?"
        r"(?:lee|leeme|read|describe|describeme) (?:lo que dice |what(?:'s| is) on )?"
        r"(?:la |the )?(?:actual |current |visible )?(?:pagina|page)"
        r"(?: actual| current| visible)?",
        value,
    ):
        semantic_operations = ["capture.screenshot", "vision.describe"]
        semantic_rule = "explicit_visible_screen_read_request"
    elif re.fullmatch(
        r"(?:(?:puedes|podrias|can you|could you) )?"
        r"(?:abre|abri|open|ver|ve|view|muestra|show)(?: me)?(?: my| mi| la)? "
        r"(?:carpeta (?:de )?)?(?:descargas|downloads|documentos|documents|"
        r"escritorio|desktop|imagenes|pictures)(?: folder| carpeta)?",
        value,
    ):
        semantic_operations = ["filesystem.folder.open"]
        semantic_rule = "explicit_known_folder_view"
    elif re.fullmatch(
        r"(?:borr|borra|borrar|elimina|eliminar|delete|remove) "
        r"(?:el |the )?(?:archivo |file )?"
        r"[a-z0-9_() -]+ (?:txt|pdf|docx?|xlsx?|csv|json|log|md|ps1|zip)"
        r"(?: (?:del|de|from) (?:el |the )?(?:escritorio|desktop))?",
        value,
    ):
        semantic_operations = ["filesystem.known.trash.named"]
        semantic_rule = "explicit_named_known_folder_file_trash"
    elif re.fullmatch(r"(?:pull up|open up|launch) [a-z0-9 ._-]+", value):
        semantic_operations = ["app.open"]
        semantic_rule = "explicit_named_application_open_colloquial"
    elif re.fullmatch(
        r"(?:que notas tengo(?: guardadas| almacenadas)?|lista(?:me)? mis notas|"
        r"muestra(?:me)? mis notas|what notes do i have(?: (?:saved|stored)(?: locally)?)?)",
        value,
    ):
        semantic_operations = ["note.list"]
        semantic_rule = "explicit_private_note_inventory"
    if semantic_operations is not None:
        return expectation(
            "semantic_review",
            "semantic",
            semantic_operations,
            review_rule=semantic_rule,
        )
    return None


def _review_trace_and_runtime_maps(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review trace requests and exact exhaustive runtime maps."""

    if re.fullmatch(
        r"(?:muestra|show)(?: el| the)? "
        r"(?:turn[ _]trace|tool[ _]trace|router[ _]trace|planner[ _]trace)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="internal_trace_name_is_not_a_user_file_or_effect",
        )
    if re.fullmatch(
        r"(?:(?:te|you) )?(?:inventaste|invenstaste|invented|fabricated|made up) "
        r"(?:ese|el|that|the) (?:link|enlace)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="link_accuracy_challenge_requires_context_not_a_new_effect",
        )
    if re.fullmatch(
        r"(?:abre|abri|open|launch) (?:el|la|the) "
        r"(?:mejor|best|primero|first|ultimo|last|anterior|previous)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="underspecified_open_target_requires_context",
        )
    if re.fullmatch(
        r"(?:powerpoint|word|excel|office|documento|document|presentacion|presentation)"
        r"[,]? (?:necesito|i need|help|ayuda)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            [],
            review_rule="application_or_document_mentioned_without_requested_action",
        )
    application_window_status = re.fullmatch(
        r"(?:is|esta) (?:the |la |el )?(.+?)(?: app| application| aplicacion)? "
        r"(?:open|opened|closed|running|abiert[oa]|cerrad[oa]|corriendo|en ejecucion)",
        value,
    )
    if application_window_status is None:
        application_window_status = re.fullmatch(
            r"(?:the |la |el )?(.+?)(?: app| application| aplicacion)? "
            r"(?:is|esta|sigue) "
            r"(?:open|opened|closed|running|abiert[oa]|cerrad[oa]|corriendo|en ejecucion)",
            value,
        )
    if application_window_status is not None:
        application_name = application_window_status.group(1).strip()
        if application_name not in {"app", "application", "aplicacion", "program", "programa"}:
            return expectation(
                "semantic_review",
                "semantic",
                ["window.application.status"],
                review_rule="named_application_visible_window_status",
            )
    if re.fullmatch(
        r"(?:abre|abri|open|launch|offne|starte|apri|avvia) "
        r"(?:el |the |il |den |o )?(?:browser|navegador)",
        value,
    ):
        return expectation(
            "semantic_review",
            "semantic",
            ["app.open"],
            review_rule="explicit_default_browser_application_open",
        )
    reviewed_operations = {
        "mandale a musica que ya voy": "message.send",
        "mandale a letras hola": "message.send",
        "puedes poner algo de jazz": "media.play.query",
        "steam esta cerrado": "window.resolve",
        "is steam open right now": "window.resolve",
        "is steam running right now": "window.resolve",
        "donde estan mis copias de seguridad": "backup.list",
        "can you open steam for me": "app.open",
        "ve la pagina de steam del nuevo juego de batman que salio hace poco": "web.search",
        "que tamano tiene la ventana activa": "window.active",
        "lee mi memory md y resume": "filesystem.search",
        "que tema esta sonando": "media.status",
        "cuando dija tiempo es para que aprietes al tecla de parar y reanudar videos o musica en mi pc": "routine.phrase.create",
        "go back": "browser.control",
        "open my downloads folder": "filesystem.folder.open",
        "what is the weather today": "web.search",
        "when is gta 6 coming out": "web.search",
        "decime que cancion es esta": "media.status",
        "regresa": "browser.control",
        "volve atras en el navegador": "browser.control",
        "selecciona todo el texto de esta ventana": "input.select.all",
        "acabas de reanudar el video youtube pero yo queria de opera gx": "media.control",
        "scroll abajo": "browser.control",
        "what song is playing": "media.status",
        "que wifi estoy usando ahora": "network.status",
        "abre el navegador ya": "app.open",
        "decime que ves": "vision.describe",
        "estoy viendo pushiner la pelicula nueva puedes investigar si es buena o mala": "web.search",
        "el notas por favor": "app.open",
        "no abras spotify solo decime si esta instalado": "app.installed",
        "what s currently on my clipboard": "clipboard.read.text",
        "cierra solo la pestana que abriste": "browser.control",
        "close current tab": "browser.control",
        "puedes abrir el archivo de log de hoy": "filesystem.search",
        "what is the disk usage": "system.status",
        "resumime la pagina actual": "vision.describe",
        "resume la pagina actual": "vision.describe",
        "resumime esta pagina": "vision.describe",
        "summarize current page": "vision.describe",
        "scroll down": "browser.control",
        "i want to listen to rosalia": "media.play.query",
        "i want to listen to michael jackson": "media.play.query",
        "pon la musica a pausa": "media.control",
        "is the wifi on": "network.status",
    }
    if value in reviewed_operations:
        return expectation(
            "semantic_review",
            "literal",
            [reviewed_operations[value]],
            review_rule="exhaustive_runtime_verified_operation",
        )

    reviewed_no_effect = {
        "what are they made of", "who invented this rhyme",
        "mandale a mama que ya llego", "calendar devil", "pero buscalo en mi explorador",
        "si no hay evidencia marca unverified", "que me escribio mama", "mirala denuevo",
        "messaj para jorge", "el calor se va de la atmosfera se va no se queda a diferencia de los que lo absorben y como lo absorben no te queda el calor",
        "buscalo en mi explorador", "recordame llamar a mama", "sync datos si", "checa esa pagina",
        "si hay archivos", "donde esta el reporte", "sync data please", "mostrame las fotos de mi carpeta",
        "escribete a mi para que lo quiero mucho en whatsapp", "reducir la calidad si", "extrair todo lo que hay",
        "traceroute to the corporate website please", "apreeso la carpeta", "que me escribio mama",
        "audio", "resumime", "rutina hacer algo", "puedes hacer un ping a ese servidor",
        "que pasa con el mercado", "triggers que hago", "poderias buscarme el horario de trenes",
        "mi perfil es ema", "wapp abre el chat", "calendario ahora dame", "como configuro una rutina cron",
        "mensaje rapido ahora", "what s the weather there", "mandale a sofi que ya salgo para alla",
        "abre brave si es mi navegador por defecto", "la vignette ok", "anda a la pestana anterior",
        "necesito jugar ahora", "find mi telefono", "anterior", "busca en biblioteca y dime si no aparece",
        "sync necesito", "precios actuales de una gpu", "no me referia a la app", "directorio actual",
        "mandale a amor que la amo", "negro", "can you remind me when the package arrives",
        "avisame si esta pagina cambia",
    }
    if value in reviewed_no_effect:
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="exhaustive_runtime_conversation_or_missing_authority",
        )
    return None


def _review_historical_literal_rules(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review contiguous historical literal rules."""

    if re.fullmatch(
        r"(?:steam|abrime el photoshop|ouvre itunes|apri itunes|open itunes|"
        r"abre vs code|abri la configuracion de windows|abrime la calculadora dale|"
        r"abre las opciones de wifi|"
        r"offne den browser|starte den browser)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_application_or_default_browser_open",
        )
    if re.fullmatch(
        r"(?:offne google com|abre youtube|vai su youtube)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_public_site_navigation",
        )
    if re.fullmatch(
        r"(?:bring mir chrome nach vorne|bring chrome to the front|minimize opera)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["window.focus" if "bring" in value else "window.minimize"],
            review_rule="explicit_named_window_action",
        )
    if re.fullmatch(r"close notepad", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.resolve", "app.close"],
            review_rule="explicit_named_application_close",
        )
    if re.fullmatch(
        r"(?:answer in a bullet list|respond in spanish|responde en una frase corta|"
        r"echo \d+\s*[+*\-/]\s*\d+|combates rapidos y desafios creativos)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="explicit_conversation_or_response_preference",
        )
    if re.fullmatch(
        r"(?:che musica e questa|what song is this|"
        r"regarde quelle video je suis en train de regarder)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["media.status"],
            review_rule="explicit_current_media_status_read",
        )
    if re.fullmatch(r"(?:abrime spotify|spotify|firefox)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_bare_or_colloquial_application_open",
        )
    if re.fullmatch(
        r"(?:me ayudas a abrir steam|digema,? abre steam|xupalo care abre steam|"
        r"alter,? mach schnell steam auf|abre configuracion de windows|open settings)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_colloquial_application_open",
        )
    if re.fullmatch(r"(?:puedes abrir youtube|o youtube)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_named_public_site_navigation",
        )
    if re.fullmatch(r"dame el contenido del portapapeles", value):
        return expectation(
            "semantic_review",
            "literal",
            ["clipboard.read.text"],
            review_rule="explicit_clipboard_text_read",
        )
    if re.fullmatch(
        r"(?:brillance max|mets la luminosite au maximum|coloca o brilho no maximo|"
        r"subi el brillo al maximo|erhohe die helligkeit auf das maximum)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["system.settings.set"],
            review_rule="explicit_absolute_brightness_setting",
        )
    if re.fullmatch(
        r"(?:esta instalado .+|abre steam y dime si .+ ya esta instalado)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["game.catalog.list"],
            review_rule="explicit_read_only_game_install_status",
        )
    if re.fullmatch(
        r"(?:pone un timer de (?:5|cinco) minutos|"
        r"ponme un temporizador de (?:10|diez) minutos|"
        r"pone una alarma en (?:2|dos) minutos|"
        r"recuerdame .+ en una hora|erinnerung,? in 1 stunde .+|"
        r"(?:ponme|pone|establece) una? alarma (?:a las|for) "
        r"(?:6|7|8|seis|siete|ocho|seven|eight)(?: de la manana| am)?|"
        r"set an alarm for (?:6|7|8|six|seven|eight)|"
        r"alexa,? schedule an alarm for seven am|"
        r"metti una sveglia per le 7 di mattina|"
        r"stell einen wecker auf 7 uhr|despertame manana a las 6|"
        r"tocar alarma manana ocho|cria um alarme para as 7(?::| )00)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["notification.schedule"],
            review_rule="explicit_resolvable_future_reminder_or_alarm",
        )
    if re.fullmatch(r"switch to the previous window", value):
        return expectation(
            "semantic_review",
            "literal",
            ["input.key.press"],
            review_rule="explicit_previous_window_chord",
        )
    if re.fullmatch(r"cierra (?:la ventana de )?youtube", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.resolve", "app.close"],
            review_rule="explicit_baxy_youtube_player_close",
        )
    if re.fullmatch(r"que app esta activa ahora", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.active"],
            review_rule="explicit_foreground_window_status",
        )
    if re.fullmatch(r"recordame comprar pan", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="reminder_due_time_missing",
        )
    if re.fullmatch(r"show me the files in this directory", value):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.list"],
            review_rule="explicit_sandbox_directory_inventory",
        )
    if re.fullmatch(r"tira uma captura de ecra", value):
        return expectation(
            "semantic_review",
            "literal",
            ["capture.screenshot"],
            review_rule="explicit_full_desktop_capture",
        )
    if re.fullmatch(
        r"(?:decile a .+ en discord .+|escribile a .+ por discord .+|"
        r"message .+ on discord saying .+|manda pro .+ no discord dizendo .+)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["message.send"],
            review_rule="explicit_discord_message_with_recipient_and_text",
        )
    if re.fullmatch(
        r"(?:in (?:whatsapp|discord) open the conversation with .+|"
        r"va ao (?:whatsapp|discord) e abra a conversa com .+|"
        r"ponte en el chat de .+ en (?:whatsapp|discord|telegram)|"
        r"anda a whatsapp al chat de .+|"
        r"type .+ in (?:notepad|word)|in (?:notepad|word|el bloc de notas) "
        r"(?:write|escribe) .+(?: and press enter)?|"
        r"ouvre la calculatrice et tape .+|"
        r"abri la calculadora,? escribi .+ y apreta enter|"
        r"escribi .+ en el bloc de notas|"
        r"mouse drag that window|"
        r"close (?:the )?current window|type my email here)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["gui"],
            review_rule="explicit_gui_action_without_safe_public_target",
        )
    if re.fullmatch(r"check that the budget\.xlsx file exists on my desktop", value):
        return expectation(
            "semantic_review",
            "literal",
            ["gui"],
            review_rule="external_desktop_file_search_outside_sandbox",
        )
    if re.fullmatch(r"list all the environment variables for this process", value):
        return expectation(
            "semantic_review",
            "literal",
            ["env"],
            review_rule="private_process_environment_not_exposed",
        )
    if re.fullmatch(r"lista servicios de windows en ejecucion", value):
        return expectation(
            "semantic_review",
            "literal",
            ["maintenance"],
            review_rule="windows_service_inventory_not_exposed",
        )
    if re.fullmatch(
        r"(?:set it to \d{1,3}|dame notas de eso|ping eso ahora|"
        r"leeme el ultimo mensaje|adiciona uma lembranca sobre isso|"
        r"olvida todo lo que sabes|wie ist die ip|"
        r"mandale a mi amiga que la quiero mucho|hazme flashcards de esto|"
        r"libreria de tim|escribe esto ya|show me that page|"
        r"respondele que despues hablamos|zipar eso rapidito|e a tokyo|"
        r"baisse la luminosite de l ecran|responde ao joao que sim|"
        r"y gemma puedes instalarlo|daruber noch etwas|fug es ein|"
        r"donde esta la info)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="underspecified_followup_requires_context",
        )
    if re.fullmatch(r"chatgpt", value):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_named_public_site_navigation",
        )
    if re.fullmatch(
        r"(?:can you put this in my contacts|close that window bitte)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["gui"],
            review_rule="unsupported_gui_or_contacts_target",
        )
    if re.fullmatch(r"cancel the running export job,? it'?s stuck", value):
        return expectation(
            "semantic_review",
            "literal",
            ["job_manager"],
            review_rule="external_export_job_not_exposed",
        )
    if re.fullmatch(
        r"usa web_open_url para abrir https?://[^ ]+ en el navegador",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_public_url_navigation",
        )
    if re.fullmatch(
        r"si batman no esta en biblioteca,? dime eso sin comprar nada",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["game.catalog.list"],
            review_rule="explicit_read_only_game_library_check",
        )
    if re.fullmatch(r"porta spotify davanti a tutto", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.focus"],
            review_rule="explicit_named_window_focus",
        )
    if re.fullmatch(r"escribile a .+ por (?:whatsapp|wsp) .+", value):
        return expectation(
            "semantic_review",
            "literal",
            ["message.send"],
            review_rule="explicit_whatsapp_message_with_recipient_and_text",
        )
    if re.fullmatch(
        r"(?:list all running processes|(?:regarde|liste|affiche|montre|mostra|lista|listar|muestra|muestrame|mostrame|"
        r"list|show me|show|what processes are|cuantos procesos hay)"
        r"(?: (?:les|los|all|the|todos|me|my))? "
        r"(?:processus|procesos|processes|processos)"
        r"(?: (?:actifs|activos|active|running|corriendo|que mas consumen|"
        r"por cpu|por ram))?)(?: please| por favor)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["system.process.list"],
            review_rule="explicit_bounded_process_inventory",
        )
    if re.fullmatch(
        r"(?:como esta o wifi|a que wifi estoy conectado|decime si el wifi esta prendido|"
        r"check the wifi connection status|en que wifi estoy conectado)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["network.status"],
            review_rule="explicit_privacy_preserving_network_status",
        )
    if re.fullmatch(
        r"(?:what notes do i have saved locally|que notas tengo guardadas localmente|"
        r"such nach allen notizen von gestern|notas que hay)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["note.list"],
            review_rule="explicit_local_note_inventory",
        )
    if re.fullmatch(
        r"(?:(?:mi puedes mostrar notas sobre|busca notas sobre|"
        r"puedes buscar notas de|potresti trovare la nota sul) .+)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["note.search"],
            review_rule="explicit_local_note_search",
        )
    if re.fullmatch(r"olvida lo anterior de esta conversacion", value):
        return expectation(
            "semantic_review",
            "literal",
            ["memory.forget"],
            review_rule="explicit_session_memory_forget",
        )
    if re.fullmatch(
        r"(?:olvida todo lo de .+|borra tus recuerdos sobre mi)", value
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["memory.forget"],
            review_rule="explicit_private_memory_forget",
        )
    if re.fullmatch(r"(?:estado del bluetooth|bluetooth status)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["bluetooth.device.list"],
            review_rule="explicit_bluetooth_device_status_inventory",
        )
    if re.fullmatch(
        r"(?:muestra mi directorio actual|voire les fichiers|"
        r"pode me mostrar o conteudo da pasta atual)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.list"],
            review_rule="explicit_sandbox_directory_inventory",
        )
    if re.fullmatch(r"muestra contenido de \.env", value):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.read.text"],
            review_rule="explicit_sandbox_text_file_read",
        )
    if re.fullmatch(r"qu y a t il dans le clipboard", value):
        return expectation(
            "semantic_review",
            "literal",
            ["clipboard.read.text"],
            review_rule="explicit_clipboard_text_read",
        )
    if re.fullmatch(r"muy bi+en,? puedes saber que serie estoy viendo", value):
        return expectation(
            "semantic_review",
            "literal",
            ["vision.describe"],
            review_rule="explicit_visible_screen_description",
        )
    if re.fullmatch(
        r"(?:che gemma )?que hora es|que dia es hoy|现在几点|date and time",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["system.time"],
            review_rule="explicit_current_local_time_or_date",
        )
    if re.fullmatch(
        r"abre un navegador que tengas instalado y busca windows 11 settings"
        r"(?: tier 16gb stack split)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_public_search_with_malformed_historical_quoting",
        )
    if re.fullmatch(r"wie ist der akku", value):
        return expectation(
            "semantic_review",
            "literal",
            ["system.status"],
            review_rule="explicit_battery_status",
        )
    if re.fullmatch(
        r"(?:esta spotify abierto|est ce que word est ouvert|la calcolatrice e aperta)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["window.resolve"],
            review_rule="explicit_visible_application_status",
        )
    if re.fullmatch(r"me abri el navegador", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.resolve"],
            review_rule="explicit_default_browser_window_status",
        )
    if re.fullmatch(r"show current directory", value):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.list"],
            review_rule="explicit_sandbox_directory_inventory",
        )
    if re.fullmatch(r"que suena ahora", value):
        return expectation(
            "semantic_review",
            "literal",
            ["media.status"],
            review_rule="explicit_current_media_status",
        )
    if re.fullmatch(r"jouer la radio de france s il te plait", value):
        return expectation(
            "semantic_review",
            "literal",
            ["media.play.exact"],
            review_rule="explicit_named_media_playback",
        )
    if re.fullmatch(r"pode me dar o que esta copiado", value):
        return expectation(
            "semantic_review",
            "literal",
            ["clipboard.read.text"],
            review_rule="explicit_clipboard_text_read",
        )
    if re.fullmatch(r"que hay copiado ahora mismo", value):
        return expectation(
            "semantic_review",
            "literal",
            ["clipboard.read.text"],
            review_rule="explicit_clipboard_text_read",
        )
    if re.fullmatch(r"quejos tenho", value):
        return expectation(
            "semantic_review",
            "literal",
            ["game.catalog.list"],
            review_rule="historical_asr_owned_game_inventory",
        )
    if re.fullmatch(r"was habe ich in steam", value):
        return expectation(
            "semantic_review",
            "literal",
            ["game.catalog.list"],
            review_rule="explicit_owned_game_inventory",
        )
    if re.fullmatch(r"trouve discord", value):
        return expectation(
            "semantic_review",
            "literal",
            ["window.focus"],
            review_rule="explicit_find_and_focus_visible_application",
        )
    if re.fullmatch(
        r"(?:dime que elementos clicables ves|leeme la conversacion|que hace este programa)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["vision.describe"],
            review_rule="explicit_visible_screen_inspection",
        )
    if re.fullmatch(r"pode ler este texto por favor", value):
        return expectation(
            "semantic_review",
            "literal",
            ["ocr.read"],
            review_rule="explicit_visible_screen_text_read",
        )
    if re.fullmatch(
        r"(?:lee changelog y residual y dime si puedo (?:pasar a fase|hacer) 13b|"
        r"revisa residual md clasifica bugs y no toques codigo)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.read.text"],
            review_rule="explicit_named_sandbox_file_inspection",
        )
    if re.fullmatch(
        r"(?:che cosa c e di nuovo|o que esta acontecendo no mundo|"
        r"conoces el nuevo juego de batman|viste la nueva peli de michael jackson|"
        r"cuando sale gta 6|what(?:'s| is) the weather like today|latest news please|"
        r"puedes buscar el correo electronico de soporte|"
        r"parlami di superman vs batman e un bel film o sara che cosa dice la critica)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_current_public_information_request",
        )
    if re.fullmatch(r"que alarmas tengo puestas", value):
        return expectation(
            "semantic_review",
            "literal",
            ["reminder.list"],
            review_rule="explicit_local_alarm_inventory",
        )
    if re.fullmatch(r"puedes buscar archivos de mi trabajo", value):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.search"],
            review_rule="explicit_local_work_file_search",
        )
    if re.fullmatch(r"podrias buscar un problema con mi raton", value):
        return expectation(
            "semantic_review",
            "literal",
            ["peripheral.list"],
            review_rule="explicit_connected_mouse_diagnostic",
        )
    if re.fullmatch(
        r"(?:podrias buscar el campo de nombre de usuario|"
        r"can you search my contacts for sarah)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "unsupported",
            "review_rule": "requested_capability_not_present_in_public_catalog",
        }
    if re.fullmatch(
        r"(?:can you search for discord winget|de que trata esa pelicula nueva)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "exact_package_or_movie_identity_missing",
        }
    if re.fullmatch(r"ve a la pagina de marvel rivals de steam", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_public_steam_store_lookup",
        )
    if re.fullmatch(
        r"(?:digema amor en whatsapp que la amo mucho|"
        r"escreve pro cba yeah no zap que ele e um gordo|"
        r"escribe a vicent(?: u)? que es muy tonto en wsp|"
        r"escribe a vicente u que es un crack en wsp|"
        r"escribile en wsp a amor que la amo|"
        r"fala pro amor no zap que eu amo ela|"
        r"(?:gemma )?dis a maman qu est ce qu elle fait sur whatsapp|"
        r"fala pra mae que eu amo muito ela no whatsapp|"
        r"sag mama auf whatsapp dass ich sie sehr lieb hab)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["message.send"],
            review_rule="explicit_channel_recipient_and_message",
        )
    if re.fullmatch(
        r"(?:contame que es el machine learning|contame un dato curioso sobre los pulpos|"
        r"de que trata dune|do que se trata duna|de que trata la pelicula dune|"
        r"de que trata la pelicula inception|"
        r"explicame brevemente que es python|explicame que es la fotosintesis|"
        r"explicame que es una api(?: rest)?|parle moi de superman|"
        r"have you seen the movie .+|hablame un poco de marvel vs capcom|"
        r"quiero comprarme un juego pero aun no se cual|"
        r"quiero jugar los juegos de batman arkham pero no se cual jugar 1ero cual deberia jugar 1ero|"
        r"conoce los juegos de mortal kombat|de que se trata el juego arkriders|"
        r"i m using visual c on windows 11 is there anything i should know or do specifically or any differences in how the code needs to be written to work on vc|"
        r"la ventana activa dice spotify dime quien eres|mon profil c est ema|"
        r"le notas|reinicia tu cabeza|estas a ver os meus arquivos de trabalho|"
        r"soll ich diese datei umbenennen|wie richte ich eine cron routine ein|"
        r"quiero saber de que se trata marvel rivals|cosa scrivere adesso)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_conversation_or_advice_without_runtime_effect",
        )
    if re.fullmatch(
        r"(?:agenda che cosa|antworte ihm mit ja|che cosa c e li|"
        r"digli su whatsapp che gli voglio tanto bene|"
        r"dile a amor que de verdad que la amo demasiado que la amo amo amo demasiadooo|"
        r"dile a mi amiga que la amo mucho|il faut extraire tout|"
        r"j ai besoin de faire un ping a ce site|le copias|leeme los mensajes|"
        r"mandale a mi amiga que la amo|mandale a mi amiga que la quiero un monton|"
        r"me abres un link para verla|me lembra de ligar pra mae|"
        r"meu calendario ai|mi documento per favore|mute what devices|"
        r"no modifiques ningun archivo solo inspecciona|ou est le document|"
        r"pode ajustar o audio e normalizar o volume|por favor busca algo|"
        r"puis je avoir des informations sur|que tiempo hace hoy|quel est ce fichier|"
        r"quelles sont les ideas principales ici|quiero que lo veas y de que se trata|"
        r"que cambio desde la ultima ronda|que parte quedo pendiente|"
        r"rappelle moi d acheter du pain|regel fur alles|reponds lui que oui|"
        r"sabe quien es el|they are bp games|whatsapp a mi hermano|"
        r"wie war das gestern|zip dame uno|was sind die wichtigsten punkte in diesem dokument|"
        r"cuales son los puntos clave de este informe|resumir os slides desta apresentacao por favor|"
        r"dime que dice el texto|gibt es termine in meinem kalender|"
        r"peux tu resumer les diapositives pour moi|"
        r"dis quelque chose a mon amour sur whatsapp|manda pra minha namorada que eu amo ela|"
        r"in whatsapp pronto|puedes cambiar el dispositivo|como que las 10 xd|"
        r"compara dos archivos|dns lookup dame|lauter ich hor nichts|hazme una copya|"
        r"peux tu ouvrir un lien rapide|"
        r"mandale a amor que la amo muchisimo gracias por todo|"
        r"bluetooths lo otro tambien|graba lo que voy a dictar|"
        r"le docx lo puedes abrir|peux tu configurer une automatisation manuelle|"
        r"puoi cercarlo|ouvrir ce programme|ya lo tengo comprado|abre el mensaje|"
        r"que temperatura hace afuera|zip dame un|"
        r"pourrais tu ouvrir un lien specifique|yeah go ahead|quel link ese|"
        r"despues revisa routing de hora|"
        r"check the status of my delivery order|"
        r"resumeme las diapositivas de la presentacion|"
        r"vor der bestellung welche kosten fallen an|notes o office|"
        r"kannst du diesen link offnen|darf du machen das|quelques jeux la|"
        r"si dale|su mejor amigo quien es|documento me passa|"
        r"puedes ir a la pagina de steam para verlo|mi rutina que|"
        r"pode me lembrar de ligar amanha|"
        r"le lire le texte|abrilo|"
        r"sincroniza ahora|sincroniza los archivos|o el otro tambien|"
        r"va a llover manana|"
        r"notas buscar documentos|"
        r"die datei suche bitte|die date suche bitte|decime cuales son grandes|"
        r"que tengo en mi pc ahora mismo|"
        r"but why was he medicating himself|pero porque se medicaba|mira mis chats)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "historical_request_missing_identity_destination_time_or_scope",
        }
    if re.fullmatch(
        r"(?:cuando diga anterior quiero que aprieten la tecla para poner la cancion anterior|"
        r"cuando diga banana|cuando diga buenos dias (?:abri|abre) spotify|"
        r"cuando diga pantallazo saca una captura|cuantas pestanas tengo abiertas|"
        r"geh zuruck zur vorherigen seite|vuelve a la pestana anterior|"
        r"haz un ping rapido a dominio com|run ifconfig|traceroute dame datos|"
        r"how are my backups currently set up|list all the backups i ve made so far|"
        r"limpia el texto de busqueda de biblioteca|que hay en descargas|"
        r"que quedo abierto|que resolucion tengo|how many monitors do i have|"
        r"combien de moniteurs ai je|"
        r"puedes buscar el paquete ms office|"
        r"elenca i file nei download|"
        r"puedes cambiar el dispositivo e audio|tenes guardado el contacto de mi mama|"
        r"qual e o nome do ultimo arquivo copiado|resume la pagina actual|quelle est mon ip|"
        r"我的ip是什么|"
        r"ejecuta taskkill f a steam|puoi cliccare sul pulsante di acquisto|"
        r"ouvre l onglet precedent|volta pra pagina anterior|summarize current page|"
        r"como esta el traceroute a mi router|find all the fields in this web form for me|"
        r"reviens a la page d avant|reviens a la page precedente|cierra el tab ese|"
        r"quais sao os dispositivos de audio|ejecuta ipconfig|"
        r"peux tu verifier mon adresse ip publique|que redes wifi hay|"
        r"open about blank|quantos cartoes eu tenho para revisar|"
        r"quero saber a minha adresse ip|"
        r"show me active network connections now)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "unsupported",
            "review_rule": "requested_capability_not_present_in_public_catalog",
        }
    if re.fullmatch(
        r"por las buenas yo me presente por la buena pero ahi vienes a meterme y a decir un monton de malas no no no tu me ha empezado esta argo y a empezar a decir cosas es que no mira bueno la neta la neta yo yo te estaba",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="asr_conversation_fragment_without_runtime_effect",
        )
    if re.fullmatch(r"no ejecutaste nada", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="user_feedback_without_new_runtime_effect",
        )
    if re.fullmatch(r"queen es sub zero", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="historical_asr_stable_knowledge_question",
        )
    if re.fullmatch(
        r"no se el comun senor eso no se el comun no se el comun usted tener un dia de descanso domingo dia de descanso todo trabajar trabajar todo",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="asr_conversation_fragment_without_runtime_effect",
        )
    return None


def _review_normalized_literal_rules(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review literal rules that also require minimally normalized raw text."""

    raw_value = text.casefold().strip()
    if re.fullmatch(
        r"(?:abre|abr[ií]|open|ouvre|apri|[öo]ffne|vai (?:a|su)) "
        r"(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?(?:/\S*)?",
        raw_value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_local_url_navigation",
        )
    if re.fullmatch(
        r"(?:abre|abr[ií]|entra a|open|ouvre|apri|[öo]ffne|vai (?:a|su|pro)|geh auf|navigier zu) "
        r"(?:o |el |la |le |die )?(?:google(?:[- ]startseite)?|facebook|twitter|x|"
        r"reddit|linkedin|github|gmail|twitch|disney plus|spotify(?: web|\.com)|"
        r"wikipedia(?:\.org)?|instagram|chatgpt)(?: no navegador| in einem neuen tab| in a new tab)?",
        raw_value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_named_site_navigation",
        )
    if re.search(
        r"\b(?:new tab|nouvel onglet|browserverlauf|browser history|"
        r"navigation privee|private browsing)\b",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "unsupported",
            "review_rule": "browser_tab_history_private_mode_not_in_catalog",
        }
    if re.fullmatch(
        r"(?:bitte zeig mir diese url|ouvrir cette page|ouvre dans le navigateur)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "browser_destination_missing",
        }
    if re.fullmatch(
        r"(?:queres ver (?:um exemplo de python|o youtube agora)|"
        r"capisci i dettagli del mio ordine, per favore)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="conversation_question_without_browser_action",
        )
    if re.fullmatch(
        r"(?:quiero hacer un app web,? que me recomiendas|have you seen the movie .+|"
        r"hablame un poco de marvel vs[.]? capcom|"
        r"solo gracias por todo,? de verdad que me encanta como esta funcionando todo\.? gracias\.?|"
        r"si detectas fallback scripted en respuesta simple,? reporta bug y evidencia)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="conversation_or_engineering_instruction_without_runtime_effect",
        )
    if re.fullmatch(
        r"(?:que parte quedo pendiente|m+h+ y porque|le copias|antworte ihm mit ja|"
        r"regel fur alles|whatsapp a mi hermano|por favor busca algo|il faut extraire tout)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "historical_follow_up_or_action_missing_required_context",
        }
    if re.fullmatch(
        r"(?:list all the backups i ve made so far|cuando diga buenos dias abri spotify|"
        r"traceroute dame datos|que quedo abierto)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "unsupported",
            "review_rule": "requested_inventory_or_trigger_not_in_public_catalog",
        }
    if re.fullmatch(
        r"(?:was sind die wichtigsten punkte in diesem dokument|"
        r"quelles sont les idees principales ici)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "document_identity_missing",
        }
    if re.fullmatch(
        r"(?:(?:puedes|podr[ií]as|pode|podes|puoi|tu peux|can you|could you) "
        r"(?:abrir|aprire|ouvrir|open|launch|lancer)|fammi aprire)"
        r"(?: el| la| lo| the| le| il| o| a)? "
        r"(?:notepad|bloc de notas|calculadora|calculator|paint|steam|spotify|discord|"
        r"word|microsoft word|excel|powerpoint|chrome|edge|firefox|opera|whatsapp|vlc|"
        r"administrador de tareas|gerenciador de tarefas|gestionnaire des t[aâ]ches|"
        r"task manager|file explorer|explorador de archivos|explorador de arquivos|"
        r"prompt dei comandi|command prompt)(?: adesso| ahora)?(?: por favor| please)?",
        raw_value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_polite_application_open",
        )
    if re.search(r"\b(?:ip publico|ip pubblico|public ip|meine ip|mi ip)\b", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "public_network_status_does_not_expose_ip_addresses",
        }
    if re.search(r"\b(?:power plan|plan de energia)\b", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "power_plan_read_not_in_public_catalog",
        }
    if re.fullmatch(
        r"(?:fasse|resume|summarize) (?:die|the|la) "
        r"(?:prasentation|presentation)(?: zusammen)?",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "presentation_identity_missing",
        }
    if re.fullmatch(
        r"(?:could you )?(?:sort|ordena) (?:the |las )?(?:words|palabras) "
        r"(?:from longest to shortest|de mayor a menor)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "word_list_missing",
        }
    if re.fullmatch(r"busca informacion sobre (?:la|el) reunion", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "search_scope_missing",
        }
    if re.fullmatch(
        r"silenzia(?: il| l)? ?(?:audio|suono|volume)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["audio.mute"],
            review_rule="explicit_audio_mute",
        )
    if re.fullmatch(
        r"(?:abre|abri|offne|trova)(?: el| la| die| il)? photoshop",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_installed_application_open",
        )
    if re.fullmatch(
        r"(?:abre|open)(?: el| the)? editor",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_text_editor_open",
        )
    if re.fullmatch(
        r"(?:entra a|abre) (?:opera|chrome|edge|firefox) y busca .+",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_browser_web_search",
        )
    if re.fullmatch(r"abre portal desde steam", value):
        return expectation(
            "semantic_review",
            "literal",
            ["game.launch"],
            review_rule="explicit_steam_game_launch",
        )
    if re.fullmatch(r"(?:ve a|abre) portal una(?:b)?", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_web_portal_lookup",
        )
    if re.fullmatch(
        r"(?:can you check the file signature|"
        r"quali sono i punti chiave di questo file|"
        r"powerpoint (?:sim|si) (?:isso|esto))",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "document_identity_or_action_missing",
        }
    if re.fullmatch(
        r"(?:bluetooth (?:aus|an)|(?:turn|switch) bluetooth (?:off|on)|"
        r"(?:conect|conecta|connect)(?: el| the)? bluetooth|"
        r"(?:apaga|desactiva|enciende|activa) (?:el )?bluetooth|"
        r"(?:spegni|accendi|disattiva|riaccendi) (?:il )?bluetooth|"
        r"(?:schalte|aktiviere) (?:den |das )?bluetooth (?:aus|an)|"
        r"(?:allume|active) (?:le )?bluetooth|(?:liga|ative|desliga|prende) o bluetooth|"
        r"bluetooths? (?:on|off)(?: please)?)"
        r"(?: bitte| please| por favor| per favore)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["bluetooth.radio.set"],
            review_rule="explicit_bluetooth_radio_state_change",
        )
    if re.fullmatch(r"(?:vea|ver|muestra|show) (?:el )?chat de .+", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "messaging_application_or_channel_missing",
        }
    if re.fullmatch(r"quiero restaurar mi informacion antigua", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "restore_resource_scope_missing",
        }
    if re.fullmatch(
        r"(?:dame|dime|decime)? ?(?:que )?(?:la )?(?:hora|fecha)(?: exacta)?(?: es)?|"
        r"what(?:'s| is) (?:the )?(?:time|date)(?: right now)?|"
        r"what is today s date|quelle heure est il|wie spat ist es|che ore sono|"
        r"mi puoi dire che ore sono|(?:cual es |diga )?la fecha (?:de )?hoy",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["system.time"],
            review_rule="explicit_local_time_or_date_read",
        )
    if re.search(
        r"\b(?:app|aplicacion|process|proceso|programme|programma)\b.{0,24}"
        r"\b(?:ram|memoria|memory|memoire)\b|"
        r"\b(?:ram|memoria|memory|memoire)\b.{0,24}"
        r"\b(?:app|aplicacion|process|proceso|programme|programma)\b",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "per_process_memory_measurement_not_in_public_catalog",
        }
    if not re.match(
        r"^(?:que es|what is|what does|explain|explica|was ist|qu est ce que)\b",
        value,
    ) and not re.match(
        r"^(?:recuerda|remember|guarda|acordate|lembra|lembre|souviens|merk dir|"
        r"ricorda|borra la memoria|olvida|forget)\b",
        value,
    ) and re.search(
        r"\b(?:ram|memoria|memory|memoire|arbeitsspeicher|cpu|procesador|processor|"
        r"bateria|battery|batterie|batteria|disco|disk|spazio|espaco|espace disque|windows)\b",
        value,
    ) and re.search(
        r"\b(?:cuant[oa]|quanta|quanto|combien|how much|using|nivel|niveau|level|livello|libre|free|"
        r"usad[oa]|used|uso|usage|utilisation|cargad[oa]|charging|charger|caricando|pourcentage|"
        r"percentuale|porcentaje|queda|reste|resta|version|instalad[oa])\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["system.status"],
            review_rule="explicit_local_system_measurement",
        )
    if re.fullmatch(
        r"(?:el )?(?:volumen|volume)(?: check| actual| ahora| status| estado)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["audio.status"],
            review_rule="explicit_output_audio_status_read",
        )
    if re.match(
        r"^(?:recuerda (?:temporalmente )?que|recuerda mi|remember (?:my|that)|save my|acordate que|guarda que|"
        r"lembra que|lembre que|souviens-toi que|merk dir dass|ricorda che)\b",
        value,
    ) or re.fullmatch(
        r"(?:como me llamo|what is my name|quien soy yo|"
        r"qual e o meu nome|meu nome qual era|"
        r"que sabes de mis preferencias|tienes memoria|"
        r"was ist mein name noch mal|was ist meine bevorzugte einstellung)",
        value,
    ) or (
        "comment je m appelle" in value
        and re.search(r"\bqu est ce que tu peux faire\b", value)
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["memory"],
            review_rule="explicit_private_memory_request",
        )
    if re.fullmatch(
        r"parla in inglese da adesso in poi",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["memory.save"],
            review_rule="explicit_persistent_language_preference",
        )
    if re.fullmatch(
        r"(?:stop using emojis|use emojis|usa (?:los? )?emojis?|usa le emoji|be more formal|"
        r"usa un tono formal|responde m[aá]s (?:breve|corto)|antworte k[uü]rzer|"
        r"habla en (?:espa[nñ]ol|ingl[eé]s)(?: a partir de ahora)?|"
        r"modo corto)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="session_response_preference_is_conversation",
        )
    if re.fullmatch(
        r"(?:what did you do before|qu[eé] te dije hace un rato)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="session_history_question_is_conversation",
        )
    if re.fullmatch(r"save my current window layout please", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="window_layout_persistence_not_in_catalog",
        )
    if re.match(r"^(?:anota|apunta|take a note|create a note)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["note"],
            review_rule="explicit_local_note_creation",
        )
    if re.fullmatch(r"(?:el )?(?:volumen|volume) (?:que pasa|what is happening)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["audio.status"],
            review_rule="explicit_output_audio_status_read",
        )
    if re.fullmatch(
        r"(?:que (?:esta sonando|se esta reproduciendo)(?: ahora)?|"
        r"what(?:'s| is) (?:on|playing)(?: right now| now)?|now playing|"
        r"wie heisst dieses lied|welches lied ist das|"
        r"quelle chanson est[- ]?ce|che canzone e questa|wer singt das|"
        r"c est quoi cette chanson)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["media.status"],
            review_rule="explicit_current_media_status_read",
        )
    if re.fullmatch(
        r"(?:spring zum nachsten lied|mach mit dem nachsten album weiter|"
        r"nachstes lied abspielen|spiel den nachsten song|"
        r"(?:pon|pasa|salta|cambia|reproduce|play|skip)(?: a| to)?(?: la| the)? "
        r"(?:siguiente|next) (?:cancion|pista|album|song|track))",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["media.control"],
            review_rule="explicit_next_media_control",
        )
    if re.fullmatch(
        r"(?:reanuda|continua)(?: ya| ahora| la reproduccion)|"
        r"(?:resume|continue)(?: now| playback)|go back one|previous track|"
        r"previous song|pista anterior|cancion anterior",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["media.control"],
            review_rule="explicit_media_transport_control",
        )
    if re.fullmatch(r"(?:pausa|pause) (?:la )?(?:musica|music|cancion|song)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["media.control"],
            review_rule="explicit_media_pause",
        )
    if re.fullmatch(
        r"(?:(?:pode|puedes|puoi|can you|could you) )?"
        r"(?:cierra|cerra|close|ferme|schliess|schliesse|chiudi|chiudere|fecha|fechar|"
        r"encerra|beende|quit)(?: la| el| the| le| die| das| il| o| a)? "
        r"(?:app |aplicacion |ventana de )?(?:spotify|word|steam|discord|chrome|vlc|"
        r"paint|calculadora|calcolatrice|obs|explorador de archivos|"
        r"explorador de arquivos|file explorer|media player)(?:,? por favor|,? please)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.close"],
            review_rule="explicit_known_application_close",
        )
    if re.fullmatch(r"abre mi correo", value):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_mail_application_open",
        )
    if re.fullmatch(r"es heisst .+ aber das solltest du doch schon wissen", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="conversation_context_correction",
        )
    return None


def _review_broad_domain_rules(
    text: str,
    value: str,
) -> dict[str, Any] | None:
    """Review broad public-domain and verified local-operation rules."""

    raw_value = text.casefold().strip()
    has_public_domain = re.search(
        r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\."
        r"(?:com|org|net|io|cl|es|de|fr|it)(?:/|\b)",
        raw_value,
    ) is not None
    if has_public_domain and re.match(
        r"^(?:ve a|naveg[aá] a|open|abre|abr[ií])\b",
        raw_value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_public_url_navigation",
        )
    if re.search(r"\b(?:clima|weather|meteo|wetter)\b", value) and re.search(
        r"\b(?:busca|buscar|search|find|google|cherche|cerca)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_weather_web_search",
        )
    if re.match(
        r"^(?:busca|buscar|search|find|google|cherche|cerca|pesquisa|procura|such|suche)\b",
        value,
    ) and not re.search(
        r"(?:\.[a-z0-9]{1,8}\b|\b(?:archiv\w*|files?|datei|fichier|notas?|notes?|"
        r"apuntes?|carpeta|folder|proceso|process|repo|repository|repositorio|"
        r"biblioteca|library|steam|juegos?|games?|discord|spotify|notepad|"
        r"calculator|calculadora|esto literal|pdf|docx?|xlsx?|txt|csv|json|log|"
        r"md|ps1|document\w*|dokument\w*)\b)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_public_web_search",
        )
    if re.fullmatch(r"[a-z0-9 .'-]{2,80} (?:clima|weather|wetter|meteo)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_location_weather_search",
        )
    if re.search(r"\b(?:usb|dispositivos? usb|usb devices?)\b", value) and re.search(
        r"\b(?:que|cuales|what|which|tengo|conectad|connected|list|lista)\w*\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["peripheral.list"],
            review_rule="explicit_connected_usb_inventory",
        )
    if re.fullmatch(
        r"(?:(?:can you|could you|please|puedes|podrias) )?"
        r"(?:send|press|presiona|aprieta|pulsa) (?:the |la |el )?"
        r"(?:(?:key|tecla) )?"
        r"(?:page down|page up|arrow down|arrow left|arrow right|arrow up|"
        r"pagina abajo|pagina arriba|flecha abajo|flecha izquierda|flecha derecha|"
        r"flecha arriba|backspace|retroceso|delete|suprimir|escape|esc|enter|intro|"
        r"home|inicio|end|fin|space|espacio|tab|tabulador)"
        r"(?: (?:key|tecla|hotkey))?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["input.key.press"],
            review_rule="explicit_allowed_navigation_key_press",
        )
    if re.fullmatch(
        r"(?:(?:que|cual) (?:mouse|raton|teclado) (?:tengo|esta conectado)|"
        r"(?:what|which) (?:mouse|keyboard) (?:do i have|is connected))",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["peripheral.list"],
            review_rule="explicit_input_peripheral_inventory",
        )
    if re.match(r"^(?:busca|search) (?:en )?(?:mis )?(?:notas|apuntes)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["note.search"],
            review_rule="explicit_local_note_search",
        )
    if re.search(
        r"\b[a-z0-9_-]+\.(?:pdf|docx?|xlsx?|txt|csv|json|log|md|ps1)\b",
        raw_value,
    ) and re.search(r"\b(?:que es|what is|was ist)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.read.text"],
            review_rule="explicit_local_file_question",
        )
    if re.search(r"\byoutube\b", value) and re.search(
        r"\b(?:pon|pone|poner|play|reproduce|toca)\b.*"
        r"\b(?:video|musica|music|cancion|song|gatos|cats)\b|"
        r"\b(?:video|musica|music|cancion|song|gatos|cats)\b.*\b(?:en|on) youtube\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["media.play.youtube"],
            review_rule="explicit_youtube_playback",
        )
    if re.fullmatch(
        r"(?:abre|open)(?: la| el| the| web de)? youtube(?: aunque exista app parcial)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["streaming.navigate"],
            review_rule="explicit_youtube_navigation",
        )
    if re.fullmatch(r"(?:abre o netflix|voce pode abrir o site da netflix)", value):
        return expectation(
            "semantic_review",
            "literal",
            ["streaming.navigate"],
            review_rule="explicit_netflix_navigation",
        )
    if re.match(r"^(?:abre |open )?youtube.*\b(?:busca|search)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_youtube_search_without_playback",
        )
    if re.fullmatch(
        r"abre steam,? ve a biblioteca,? busca .+ y dime si esta instalado|"
        r"abre steam y (?:ejecuta|lanza) el juego instalado .+",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["game"],
            review_rule="explicit_steam_library_workflow",
        )
    if re.search(r"\b(?:juegos?|games?) instalad[oa]s?\b", value) and re.search(
        r"\b(?:busca|buscar|search|find)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["game.catalog.list"],
            review_rule="explicit_installed_game_catalog_search",
        )
    if re.search(r"\bapp id\b.*\b(?:api|publica|public)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="explicit_public_game_metadata_search",
        )
    if has_public_domain and re.match(
        r"^(?:abre|open) (?:chrome|edge|firefox|opera)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["browser.navigate"],
            review_rule="explicit_browser_navigation_workflow",
        )
    if re.search(r"\b(?:ofertas?|deals?|precio|price)\b", value) and re.search(
        r"\b(?:juegos?|games?)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="public_game_offer_search",
        )
    if re.search(r"\ben steam sin (?:abrir|ejecutar) (?:el )?juego\b", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "steam_store_or_local_library_scope_missing",
        }
    if re.search(r"\b(?:busca|buscar|search)\b.*\b(?:juego|game)\b", value) \
            and not re.search(r"\b(?:instalad[oa]|biblioteca|library)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="public_game_search_without_local_library_scope",
        )
    if re.search(r"\b(?:videos?|cancion|song)\b", value) and re.search(
        r"\b(?:busca|buscar|search)\b",
        value,
    ) and not re.search(r"\b(?:reproduce|play)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["web.search"],
            review_rule="public_media_search_without_playback",
        )
    if re.match(
        r"^(?:y |e |and |et |und |quando aconteceu esse evento|y de que trata|"
        r"explicame mejor el segundo|danke sag mal|o outro|quel autre)",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "follow_up_requires_session_context",
        }
    if re.match(
        r"^(?:qual e|c est quoi|as tu vu|quero fazer (?:um|un) app web|"
        r"kannst du mir sagen wie das funktioniert|do you know who|"
        r"que forma .+ poderosa|quale forma .+ potente)",
        value,
    ) and not re.search(
        r"\b(?:latest|ultimo|hoy|today|actual|current|precio|price|busca|search|google)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_question_is_conversation",
        )
    if re.match(
        r"^(?:tell me about|habla(?:me)? de|h[aá]blame de|do you know who|"
        r"habla sobre|conoces a|describe what .+ based on what you(?:'ve| have) observed)\b",
        value,
    ) and not re.search(
        r"\b(?:latest|[uú]ltim[oa]|hoy|today|actual|current|precio|price|"
        r"d[oó]nde ver|where to watch|busca|search|google|fuente|source)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_topic_request_is_conversation",
        )
    stable_question = re.match(
        r"^(?:que es|que son|what is|what are|what does .+ (?:stand for|mean)|"
        r"explica|explica|explain|quien|who|por que|why|cual es|which|"
        r"como funciona|how does)\b",
        value,
    )
    if re.match(r"^(?:quiero saber|quiero saver|dime) (?:quien|que es)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_knowledge_question_is_conversation",
        )
    dynamic_or_personal = re.search(
        r"\b(?:actual|ahora|right now|current|currently|latest|ultimo|hoy|today|"
        r"precio|price|clima|weather|hora|time|fecha|date|screen|pantalla|"
        r"clipboard|portapapeles|mi nombre|my name|soy yo|about me|"
        r"usage|uso|status|estado|nivel|level|libre|free|cargad[oa]|charging|"
        r"bateria|battery|disco|disk|windows version)\b",
        value,
    )
    explicit_retrieval = re.search(
        r"\b(?:busca|buscar|search|google|verifica|verify|fuente|source)\b",
        value,
    )
    if stable_question and not dynamic_or_personal and not explicit_retrieval:
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_knowledge_question_is_conversation",
        )
    if re.match(
        r"^(?:what is (?:a|an|the)|what are (?:a|the)|que es (?:un|una|el|la)|"
        r"que son (?:los|las)|qu est ce que|was ist (?:ein|eine|der|die|das)|"
        r"cos e|o que e (?:um|uma|o|a))\b",
        value,
    ) and not re.search(
        r"\b(?:weather|clima|meteo|wetter|time|hora|price|precio|status|estado|"
        r"usage|uso|current|actual)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="stable_definition_is_conversation",
        )
    if re.search(
        r"^(?:(?:conoces|conoce|conosci|(?:voce )?conhece|connais|kennst du|do you know)\b.*"
        r"(?:musica|music|songs?|cancion|canzone|chansons?|lied|lieder|"
        r"pel.?cula|film|serie).*|"
        r"(?:has escuchado|have you heard)\b.*(?:cancion|songs?|music).*|"
        r"(?:has visto|voce ja viu|have you seen)\b.*(?:pel.?cula|film|serie).*|"
        r"conoces a [a-z0-9 .'-]+)$",
        value,
    ) and not re.search(
        r"\b(?:latest|ultima|ultimo|hoy|today|actual|current|precio|price|"
        r"donde ver|where to watch)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="knowledge_question_is_conversation",
        )
    if re.match(r"^quiero hablar de .+", value):
        return expectation(
            "semantic_review",
            "literal",
            [],
            review_rule="conversation_topic_request",
        )
    if re.search(r"\b(?:whatsapp|wsp|email|correo)\b", value) and re.search(
        r"\b(?:manda|mandale|envia|envi[aá]|escribele|escr[ií]bele|dile|decile|"
        r"tell|message|write|send|scrivi|[eé]cris|schick|di)\b",
        value,
    ) and not re.search(r"\b(?:lee|read|lis|leggi).{0,32}\b(?:mensaje|message)\b", value):
        return expectation(
            "semantic_review",
            "literal",
            ["message.send"],
            review_rule="explicit_messaging_request",
        )
    if re.search(r"\b(?:lee|read|lis|leggi).{0,32}\b(?:mensaje|message)\b", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "message_read_not_in_public_catalog",
        }
    if re.match(
        r"^(?:contesta(?:le)?|responde(?:le)?|reply|answer)(?: que| that)?\b",
        value,
    ):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "message_follow_up_requires_session_context",
        }
    if re.fullmatch(
        r"(?:manda(?:le)? un mensaje a .+ en (?:whatsapp|wsp) que diga .+|"
        r"dile a .+ que .+ en (?:whatsapp|wsp))",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["message.send"],
            review_rule="explicit_whatsapp_message",
        )
    if (
        re.search(
            r"\b(?:ella|him|her|it|this|that|esto|eso|isso|questa|celui|aqui|here)\b",
            value,
        )
        and len(value.split()) <= 12
    ) or re.match(r"^(?:y|and|et|und|e) en? \w+", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "deictic_or_follow_up_requires_session_context",
        }
    if re.search(r"\b(?:port|puerto|porta)\b", value) \
            and not re.search(r"\b[0-9]{1,5}\b", value):
        return {
            "source": "semantic_review",
            "match": "literal",
            "labels": [],
            "families": [],
            "unknown_labels": [],
            "expected_effect": "review_required",
            "review_rule": "network_port_identity_missing",
        }
    if re.search(
        r"\b(?:busca|buscar|find|search|such|suche|cherche|cerca|procura)\b",
        value,
    ) and re.search(
        r"\b(?:archivos?|files?|datei|fichier|pdf|docx?|xlsx?|txt|csv|json|log|md|ps1|zip|"
        r"repo|repository|repositorio|sandbox)\b",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem"],
            review_rule="explicit_local_file_search",
        )
    if re.match(r"^(?:renombra|renombra|rename)\b", value) and re.search(
        r"\b[a-z0-9_-]+\.[a-z0-9]{1,8}\b",
        raw_value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["filesystem.move"],
            review_rule="explicit_sandbox_file_rename",
        )
    if re.fullmatch(
        r"(?:abre|abri|inicia|lanza|ejecuta|open|launch|start|ouvre|lance|"
        r"offne|starte|apri|avvia|abra|trova|finde|procura)(?: el| la| lo| the| le| den| der| das| il| o| a| as)? "
        r"(?:notepad|bloc de notas|coso de notas|calculadora|calculator|steam|spotify|"
        r"chrome(?: chrome){0,2}|google chrome|discord|word|microsoft word|edge|"
        r"firefox|opera|whatsapp|excel|powerpoint|vlc|configuracoes do windows|"
        r"windows settings|impostazioni|paint|obs|prompt dei comandi|command prompt|simbolo del sistema|"
        r"administrador de tareas|gerenciador de tarefas|gestionnaire des taches|task manager|"
        r"file explorer|explorador de archivos|explorador de arquivos|editor de fotos|correo)"
        r"(?: por favor| please| but don t say it s done if you can t verify it)?",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app"],
            review_rule="explicit_installed_application_open",
        )
    if re.fullmatch(
        r"(?:mach mir firefox auf|abre (?:el |o )?navegador(?: pls| please)?)",
        value,
    ):
        return expectation(
            "semantic_review",
            "literal",
            ["app.open"],
            review_rule="explicit_browser_application_open",
        )
    return None


ORDERED_REVIEWERS: tuple[SemanticReviewer, ...] = (
    _review_explicit_guardrails,
    _review_semantic_operations,
    _review_trace_and_runtime_maps,
    _review_historical_literal_rules,
    _review_normalized_literal_rules,
    _review_broad_domain_rules,
)


def reviewed_semantic_expectation(text: str) -> dict[str, Any] | None:
    """Correct obvious historical label omissions without consulting runtime.

    Some frozen corpora called every unmatched request "conversation", even
    when its literal text unambiguously requested a local file or app. These
    ordered, narrow corrections remain independent from planner output.
    """

    value = normalize(text)
    for reviewer in ORDERED_REVIEWERS:
        result = reviewer(text, value)
        if result is not None:
            return result
    return None


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--output", type=Path, default=LEDGER / "runtime_oracle.jsonl")
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=LEDGER / "runtime_oracle_summary.json",
    )
    args = parser.parse_args()

    baseline_exact, baseline_normalized = baseline_indexes()
    tool_exact, tool_normalized = tool2vec_indexes()
    existing_exact, existing_normalized = existing_indexes()
    frozen_exact, frozen_normalized = frozen_oracle_indexes()
    indexes = [
        ("baseline", baseline_exact, baseline_normalized),
        ("tool2vec", tool_exact, tool_normalized),
        ("frozen_oracle", frozen_exact, frozen_normalized),
        ("existing", existing_exact, existing_normalized),
    ]

    rows = []
    for case in read_jsonl(args.cases):
        if not is_runtime(case):
            continue
        authority, expectations = choose_expectations(case["text_literal"], indexes)
        semantic = reviewed_semantic_expectation(case["text_literal"])
        if semantic is not None:
            authority = "semantic_review"
            expectations = [semantic]
        signatures = {
            (item["expected_effect"], tuple(item["families"]))
            for item in expectations
        }
        selected = expectations[0] if len(signatures) == 1 else None
        rows.append(
            {
                "case_id": case["case_id"],
                "text_sha256": case["text_sha256"],
                "text_literal": case["text_literal"],
                "authority": authority,
                "expected_effect": (
                    selected["expected_effect"] if selected else "review_required"
                ),
                "expected_families": selected["families"] if selected else [],
                "expectations": expectations,
                "runtime_occurrence_count": case["occurrence_count"],
            }
        )

    authority_counts = Counter(row["authority"] for row in rows)
    effect_counts = Counter(row["expected_effect"] for row in rows)
    summary = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "independent_expected_outcome_for_every_exact_runtime_case",
        "unique_runtime_cases": len(rows),
        "by_authority": dict(sorted(authority_counts.items())),
        "by_expected_effect": dict(sorted(effect_counts.items())),
        "independently_grounded": sum(
            row["authority"] != "unreviewed" for row in rows
        ),
        "review_required": sum(
            row["expected_effect"] == "review_required" for row in rows
        ),
        "all_cases_accounted": len(rows) == len({row["case_id"] for row in rows}),
        "oracle_case_ids_sha256": hashlib.sha256(
            "\n".join(row["case_id"] for row in rows).encode("utf-8")
        ).hexdigest(),
    }
    write_jsonl(args.output, rows)
    write_json(args.summary_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["all_cases_accounted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
