"""Build and preregister BAXY's first blind generalization surface holdout.

The population is deterministic and runtime-inert.  It covers one authenticated
capability in every public family with unseen Spanish, English, and Spanglish
surfaces.  The generated rows never grant execution authority and must be
sealed before the product probe is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.preregistration.json"
)
CURRENT_REVIEW = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl"
)
PROBE_OUTPUT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.json"
PROBE_AUDIT = (
    REPO / "artifacts/holdout/generalization_surface_holdout_r1.raw.jsonl"
)
POLICY_SOURCES = (
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/router.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/turn_evidence.py",
    REPO / "src/baxy_mind/planner.py",
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_surface_holdout.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
)


@dataclass(frozen=True)
class Utterance:
    language: str
    text: str


@dataclass(frozen=True)
class Scenario:
    operations: tuple[str, ...]
    utterances: tuple[Utterance, ...]


def scenario(
    operations: tuple[str, ...],
    es_one: str,
    es_two: str,
    en_one: str,
    en_two: str,
    spanglish: str,
) -> Scenario:
    return Scenario(
        operations,
        (
            Utterance("es", es_one),
            Utterance("es", es_two),
            Utterance("en", en_one),
            Utterance("en", en_two),
            Utterance("spanglish", spanglish),
        ),
    )


SCENARIOS: dict[str, Scenario] = {
    "app": scenario(
        ("app.installed",),
        "Comprueba si el Bloc de notas está instalado",
        "Averigua si tengo Steam instalado en este equipo",
        "Check whether Notepad is installed",
        "Find out if Steam is installed on this computer",
        "Checkea si tengo Steam installed",
    ),
    "audio": scenario(
        ("audio.status",),
        "Dime cómo está el audio",
        "Consulta el estado actual del sonido",
        "Check the current audio status",
        "Tell me how the sound is configured",
        "Checkea el estado del audio",
    ),
    "backup": scenario(
        ("backup.list",),
        "Lista las copias de seguridad disponibles",
        "Muéstrame el inventario de respaldos privados",
        "List the available backups",
        "Show me the private backup inventory",
        "Lista my available backups",
    ),
    "bluetooth": scenario(
        ("bluetooth.device.list",),
        "Lista los dispositivos Bluetooth visibles",
        "Muéstrame los equipos Bluetooth detectados",
        "List the visible Bluetooth devices",
        "Show me the detected Bluetooth devices",
        "Lista my Bluetooth devices",
    ),
    "browser": scenario(
        ("browser.tabs.list",),
        "Lista las pestañas abiertas del navegador",
        "Muéstrame las pestañas web actuales",
        "List the open browser tabs",
        "Show the current web tabs",
        "Lista my browser tabs",
    ),
    "calendar": scenario(
        ("calendar.event.list",),
        "Muéstrame los eventos de hoy",
        "Revisa mi calendario para mañana",
        "List today's calendar events",
        "Show my calendar events for tomorrow",
        "Checkea my calendar events de hoy",
    ),
    "capture": scenario(
        ("capture.screenshot",),
        "Haz una captura de pantalla",
        "Captura el escritorio ahora",
        "Take a screenshot",
        "Capture the desktop now",
        "Haz un screenshot del desktop",
    ),
    "clipboard": scenario(
        ("clipboard.read.text",),
        "Lee el texto del portapapeles",
        "Dime qué texto hay copiado",
        "Read the clipboard text",
        "Tell me what text is in the clipboard",
        "Read el texto del clipboard",
    ),
    "email": scenario(
        ("email.latest.read",),
        "Lee mi correo más reciente",
        "Muéstrame el último mensaje del buzón",
        "Read my latest email",
        "Show the most recent inbox message",
        "Lee my latest email",
    ),
    "filesystem": scenario(
        ("filesystem.known.search",),
        "Busca el archivo informe trimestral en Documentos",
        "Encuentra archivos llamados presupuesto en Descargas",
        "Search Documents for a file named quarterly report",
        "Find files named budget in Downloads",
        "Busca budget files en Downloads",
    ),
    "game": scenario(
        ("game.catalog.list",),
        "Lista mi catálogo local de Steam",
        "Muéstrame los juegos de Steam que tengo",
        "List my local Steam catalog",
        "Show the Steam games in my library",
        "Lista my Steam game catalog",
    ),
    "input": scenario(
        ("input.keyboard.status",),
        "Dime el idioma actual del teclado",
        "Comprueba la distribución activa del teclado",
        "Tell me the current keyboard language",
        "Check the active keyboard layout",
        "Checkea el keyboard layout actual",
    ),
    "media": scenario(
        ("media.status",),
        "Dime qué se está reproduciendo",
        "Consulta el estado multimedia actual",
        "Tell me what is currently playing",
        "Check the current media session",
        "Dime what's playing ahora",
    ),
    "memory": scenario(
        ("memory.status",),
        "Dime cómo está la memoria local de Baxy",
        "Consulta el estado de tus recuerdos locales",
        "Show the status of Baxy's local memory",
        "Check whether local memory is enabled",
        "Checkea el estado de Baxy memory",
    ),
    "message": scenario(
        ("message.recipient.resolve", "message.send"),
        "Mándale a Ana el mensaje holdout cuarenta y cinco",
        "Dile a Carlos por WhatsApp que llego a las ocho",
        "Send Ana the message holdout forty five",
        "Tell Carlos on WhatsApp that I arrive at eight",
        "Mándale a Ana on WhatsApp que ya voy",
    ),
    "network": scenario(
        ("network.status",),
        "Dime si la red está conectada",
        "Consulta el estado general de la red",
        "Check the network status",
        "Tell me whether the network is connected",
        "Checkea el network status",
    ),
    "note": scenario(
        ("note.list",),
        "Lista mis notas locales",
        "Muéstrame las notas que tengo guardadas",
        "List my local notes",
        "Show me the notes I have saved",
        "Lista my saved notes",
    ),
    "notification": scenario(
        ("notification.list.due",),
        "Lista las notificaciones vencidas",
        "Muéstrame los avisos pendientes que ya vencieron",
        "List overdue notifications",
        "Show due alerts that have not been dismissed",
        "Lista my overdue notifications",
    ),
    "ocr": scenario(
        ("capture.screenshot", "ocr.read"),
        "Haz una captura y lee el texto que aparece",
        "Captura la pantalla y extrae todo el texto visible",
        "Take a screenshot and read the visible text",
        "Capture the screen, then run OCR on it",
        "Haz un screenshot y read the text",
    ),
    "office": scenario(
        ("office.document.create",),
        "Crea un documento de Word llamado Informe R45",
        "Crea una hoja de Excel llamada Presupuesto R45",
        "Create a Word document named R45 Report",
        "Create an Excel workbook called R45 Budget",
        "Crea un Word doc called Informe R45",
    ),
    "package": scenario(
        ("package.install.prepare",),
        "Prepara la instalación del paquete VideoLAN.VLC",
        "Busca y prepara instalar Microsoft.PowerToys",
        "Prepare the VideoLAN.VLC package installation",
        "Resolve Microsoft.PowerToys and prepare its installation",
        "Prepara install VideoLAN.VLC",
    ),
    "peripheral": scenario(
        ("peripheral.list",),
        "Lista los periféricos conectados",
        "Muéstrame los dispositivos USB conectados",
        "List connected peripherals",
        "Show the connected USB devices",
        "Lista my connected peripherals",
    ),
    "reminder": scenario(
        ("reminder.list",),
        "Lista mis recordatorios programados",
        "Muéstrame los recordatorios pendientes",
        "List my scheduled reminders",
        "Show my pending reminders",
        "Lista my reminders pendientes",
    ),
    "routine": scenario(
        ("routine.list",),
        "Lista mis rutinas guardadas",
        "Muéstrame las rutinas creadas en Baxy",
        "List my saved routines",
        "Show the routines created in Baxy",
        "Lista my Baxy routines",
    ),
    "streaming": scenario(
        ("streaming.play.named",),
        "Reproduce Dark en Netflix",
        "Busca Stranger Things en Netflix y ponla",
        "Play Dark on Netflix",
        "Find Stranger Things on Netflix and play it",
        "Pon Dark on Netflix",
    ),
    "system": scenario(
        ("system.status",),
        "Dime cómo está el equipo",
        "Muéstrame un resumen del sistema",
        "Show me the computer status",
        "Give me a system health summary",
        "Dime el system status",
    ),
    "task": scenario(
        ("task.list",),
        "Lista mis tareas",
        "Muéstrame las tareas pendientes",
        "List my tasks",
        "Show my open tasks",
        "Lista my pending tasks",
    ),
    "vision": scenario(
        ("capture.screenshot", "vision.describe"),
        "Haz una captura y describe lo que ves",
        "Captura la pantalla y dime qué aparece",
        "Take a screenshot and describe what you see",
        "Capture the screen, then describe it",
        "Haz un screenshot y describe what you see",
    ),
    "web": scenario(
        ("web.search",),
        "Busca en internet auroras australes",
        "Haz una búsqueda web de telescopios portátiles",
        "Search the web for southern lights",
        "Look up portable telescopes online",
        "Busca online portable telescopes",
    ),
    "wifi": scenario(
        ("wifi.status",),
        "Dime si el wifi está conectado",
        "Consulta el estado actual del Wi-Fi",
        "Check the Wi-Fi status",
        "Tell me whether Wi-Fi is connected",
        "Checkea si el wifi está connected",
    ),
    "window": scenario(
        ("window.active",),
        "Dime cuál es la ventana activa",
        "Consulta la ventana que está en primer plano",
        "Tell me which window is active",
        "Inspect the foreground window",
        "Dime cuál window está active",
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def normalize_text(value: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFD", value).casefold()
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def catalog_identity(capabilities: Iterable[dict[str, Any]]) -> tuple[str, int]:
    rows = sorted(
        (
            {
                "name": str(capability["name"]),
                "description": str(capability["description"]),
                "argumentsSchema": capability["argumentsSchema"],
                "risk": str(capability["risk"]),
            }
            for capability in capabilities
        ),
        key=lambda capability: capability["name"],
    )
    return canonical_hash(rows), len(rows)


def addressed_surface(utterance: Utterance) -> str:
    core = utterance.text.rstrip().rstrip(".?!")
    core = core[:1].lower() + core[1:]
    prefix = {
        "es": "Baxy, por favor: ",
        "en": "Baxy, please: ",
        "spanglish": "Baxy, porfa: ",
    }[utterance.language]
    return f"{prefix}{core}."


def build_rows(capabilities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    capability_rows = list(capabilities)
    catalog_names = {str(item["name"]) for item in capability_rows}
    catalog_families = {name.split(".", 1)[0] for name in catalog_names}
    if catalog_families != set(SCENARIOS):
        raise RuntimeError(
            "holdout family coverage drifted: "
            f"missing={sorted(catalog_families - set(SCENARIOS))} "
            f"stale={sorted(set(SCENARIOS) - catalog_families)}"
        )
    rows: list[dict[str, Any]] = []
    for family, value in SCENARIOS.items():
        missing = sorted(set(value.operations) - catalog_names)
        if missing:
            raise RuntimeError(f"{family} names unauthenticated operations: {missing}")
        for index, utterance in enumerate(value.utterances, start=1):
            for surface, text in (
                ("plain", utterance.text),
                ("addressed_polite", addressed_surface(utterance)),
            ):
                rows.append(
                    {
                        "schema": "baxy.generalization-surface-holdout.v1",
                        "case_id": f"{family}-{index:02d}-{surface}",
                        "family": family,
                        "language": utterance.language,
                        "surface": surface,
                        "text": text,
                        "outcome": "action",
                        "compatible_terminal_operation_sets": [
                            list(value.operations)
                        ],
                        "compatible_effect_operation_sets": [list(value.operations)],
                        "execution_authority": False,
                        "blind_holdout": True,
                    }
                )
    normalized = [normalize_text(str(row["text"])) for row in rows]
    if len(rows) < 300 or len(set(normalized)) != len(rows):
        raise RuntimeError("holdout population is too small or has duplicate surfaces")
    return rows


def development_texts() -> set[str]:
    return {
        normalize_text(str(json.loads(line)["text"]))
        for line in CURRENT_REVIEW.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    if partial.exists():
        raise RuntimeError(f"stale partial output exists: {partial}")
    try:
        with partial.open("x", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()


def build(args: argparse.Namespace) -> dict[str, Any]:
    for path in (args.output, args.preregistration, PROBE_OUTPUT, PROBE_AUDIT):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing holdout state: {path}")
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    rows = build_rows(capabilities)
    overlap = sorted(
        {normalize_text(str(row["text"])) for row in rows} & development_texts()
    )
    if overlap:
        raise RuntimeError(f"holdout overlaps development text: {overlap}")
    write_jsonl_atomic(args.output, rows)
    catalog_sha256, operation_count = catalog_identity(capabilities)
    language_counts = {
        language: sum(row["language"] == language for row in rows)
        for language in ("es", "en", "spanglish")
    }
    family_counts = {
        family: sum(row["family"] == family for row in rows)
        for family in SCENARIOS
    }
    zero_failure_lower = math.pow(0.05, 1.0 / len(rows))
    manifest = {
        "schema": "baxy.generalization-surface-preregistration.v1",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": "turn.decide_evaluation_only_no_execution_authority",
        "method": {
            "capability_matrix": "31_public_families_x_5_lexical_bases_x_2_surfaces",
            "test_types": ["minimum_functionality", "invariance"],
            "minimum_cases": 300,
            "minimum_exact_turn_accuracy": 0.95,
            "trajectory_target": 0.99,
            "maximum_unsafe_effects": 0,
            "one_sided_95_binomial_lower_if_zero_failures": zero_failure_lower,
            "statistical_scope": (
                "The bound assumes independent Bernoulli sampling; exact coverage "
                "is claimed only for this sealed population."
            ),
            "references": [
                "https://aclanthology.org/2020.acl-main.442/",
                "https://arxiv.org/abs/2008.09335",
                "https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm",
            ],
        },
        "population": {
            "cases": len(rows),
            "families": len(SCENARIOS),
            "cases_per_family": family_counts,
            "languages": language_counts,
            "surfaces": {
                surface: sum(row["surface"] == surface for row in rows)
                for surface in ("plain", "addressed_polite")
            },
            "normalized_development_overlap": 0,
        },
        "catalog": {
            "operations": operation_count,
            "sha256": catalog_sha256,
        },
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": file_sha256(Path(__file__).resolve()),
            "current_development_corpus_sha256": file_sha256(CURRENT_REVIEW),
            "policy_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in POLICY_SOURCES
            },
            "measurement_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in MEASUREMENT_SOURCES
            },
        },
        "output": {
            "path": str(args.output.relative_to(REPO)),
            "sha256": file_sha256(args.output),
            "rows": len(rows),
        },
        "planned_measurement": {
            "output": str(PROBE_OUTPUT.relative_to(REPO)),
            "raw_audit": str(PROBE_AUDIT.relative_to(REPO)),
            "effects_executed": 0,
        },
    }
    write_json_atomic(args.preregistration, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION)
    args = parser.parse_args()
    manifest = build(args)
    print(json.dumps(manifest["population"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
