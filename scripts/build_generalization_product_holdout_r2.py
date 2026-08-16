"""Build and preregister BAXY's ownership-aware R2 blind product holdout.

The cut is deterministic, execution-inert, lexically disjoint from R1 and the
current development review, and sealed before either the Mind sidecar or the
App-private memory parser sees it.  It includes single actions, safe missing-
channel clarification, and cross-family compositions.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
    catalog_identity,
    file_sha256,
    normalize_text,
    scenario,
    write_jsonl_atomic,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v2.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r2_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r2_mind.raw.jsonl"
)
MEMORY_TRX = (
    REPO / "artifacts/holdout/generalization_product_holdout_r2_memory.trx"
)
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r2_product.json"
)
DEVELOPMENT_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
)
POLICY_SOURCES = (
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/router.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/turn_evidence.py",
    REPO / "src/baxy_mind/planner.py",
    REPO / "src/baxy_mind/__main__.py",
    REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs",
    REPO / "src/Baxy.Kernel/Operations/ProductCatalog.cs",
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_surface_holdout.py",
)


SCENARIOS: dict[str, Scenario] = {
    "app": scenario(
        ("app.installed",),
        "Verifica si la Calculadora figura entre las aplicaciones instaladas",
        "Confirma si VLC está disponible como programa instalado",
        "See if Calculator is present in my installed apps",
        "Inspect the installed applications for VLC",
        "Confirma si Calculator is installed aquí",
    ),
    "audio": scenario(
        ("audio.status",),
        "Reporta el estado vigente del volumen y el sonido",
        "Revisa la configuración activa de salida de audio",
        "Report the active sound configuration",
        "Give me the current volume and audio state",
        "Revisa current sound status",
    ),
    "backup": scenario(
        ("backup.list",),
        "Revisa qué respaldos tengo disponibles",
        "Consulta el catálogo de copias privadas",
        "Show which backup snapshots are available",
        "Inspect the private backup list",
        "Muéstrame my backup snapshots",
    ),
    "bluetooth": scenario(
        ("bluetooth.device.list",),
        "Revisa qué aparatos Bluetooth detecta el equipo",
        "Enumera los accesorios visibles por Bluetooth",
        "Show every Bluetooth device the PC can see",
        "Inspect the detected Bluetooth hardware",
        "Muéstrame detected Bluetooth gear",
    ),
    "browser": scenario(
        ("browser.tabs.list",),
        "Revisa qué pestañas tengo abiertas",
        "Enumera las páginas abiertas en el navegador",
        "Show every tab currently open in the browser",
        "Inspect my current browser tab list",
        "Muéstrame open browser tabs",
    ),
    "calendar": scenario(
        ("calendar.event.list",),
        "Consulta qué citas aparecen hoy en mi agenda",
        "Enumera las reuniones de mañana en el calendario",
        "Show the appointments on today's calendar",
        "Review tomorrow's scheduled events",
        "Revisa tomorrow's calendar events",
    ),
    "capture": scenario(
        ("capture.screenshot",),
        "Genera una captura del monitor actual",
        "Saca un pantallazo del escritorio",
        "Grab an image of the current screen",
        "Create a desktop screen capture",
        "Toma a screen capture now",
    ),
    "clipboard": scenario(
        ("clipboard.read.text",),
        "Consulta el contenido textual copiado",
        "Recupera el texto actual del portapapeles",
        "Show the text currently copied",
        "Inspect the clipboard's text content",
        "Muéstrame copied clipboard text",
    ),
    "email": scenario(
        ("email.latest.read",),
        "Abre y lee el mensaje más nuevo de correo",
        "Consulta el email que llegó último al buzón",
        "Read the newest message in my mailbox",
        "Show what arrived most recently by email",
        "Lee newest inbox mail",
    ),
    "filesystem": scenario(
        ("filesystem.known.search",),
        "Localiza presentación final dentro de Documentos",
        "Revisa Descargas buscando archivos con nombre factura",
        "Locate a file called final presentation in Documents",
        "Look through Downloads for files named invoice",
        "Find invoice files dentro de Downloads",
    ),
    "game": scenario(
        ("game.catalog.list",),
        "Enumera los títulos instalados de mi biblioteca Steam",
        "Revisa qué juegos hay en mi catálogo local",
        "Show the locally available games from Steam",
        "Inspect my Steam library catalogue",
        "Muéstrame my local Steam library",
    ),
    "input": scenario(
        ("input.keyboard.status",),
        "Reporta qué distribución de teclado está seleccionada",
        "Consulta el lenguaje activo del teclado",
        "Show the keyboard layout selected right now",
        "Inspect the active keyboard language",
        "Muéstrame current keyboard layout",
    ),
    "media": scenario(
        ("media.status",),
        "Reporta la reproducción multimedia activa",
        "Revisa qué pista o video suena ahora",
        "Show the active media playback",
        "Inspect what the media session is playing",
        "Muéstrame current media playback",
    ),
    "memory": scenario(
        ("memory.status",),
        "Revisa el estado operativo de la memoria local de Baxy",
        "Comprueba si tus recuerdos locales están habilitados",
        "Tell me the current status of local memory",
        "Review whether Baxy's memory is enabled",
        "Checkea si local memory está enabled",
    ),
    "message": scenario(
        ("message.recipient.resolve", "message.send"),
        "Por WhatsApp, envía a Lucía el texto «R2 listo»",
        "Dile por Discord a Mateo que empiezo a las nueve",
        "Send Nora on WhatsApp the message R2 ready",
        "Tell Ethan via Discord that the build is finished",
        "Mándale a Sol via WhatsApp que voy saliendo",
    ),
    "network": scenario(
        ("network.status",),
        "Reporta si hay conectividad de red",
        "Revisa la conexión general de este equipo",
        "Show whether this computer has network connectivity",
        "Inspect the current network connection",
        "Muéstrame current network connectivity",
    ),
    "note": scenario(
        ("note.list",),
        "Enumera las notas almacenadas localmente",
        "Revisa qué apuntes tengo guardados",
        "Show all notes stored on this device",
        "Inspect my saved local notes",
        "Muéstrame saved local notes",
    ),
    "notification": scenario(
        ("notification.list.due",),
        "Enumera los avisos que ya están vencidos",
        "Revisa notificaciones pendientes cuya hora pasó",
        "Show alerts that are already overdue",
        "Inspect due notifications still pending",
        "Muéstrame overdue alerts",
    ),
    "ocr": scenario(
        ("capture.screenshot", "ocr.read"),
        "Captura el monitor y transcribe las palabras visibles",
        "Toma una captura de pantalla y reconoce el texto",
        "Capture the display and transcribe its visible words",
        "Take a screen capture, then extract the writing",
        "Captura screen y extract visible words",
    ),
    "office": scenario(
        ("office.document.create",),
        "Genera un archivo Word titulado Resumen R2",
        "Prepara un libro Excel llamado Gastos R2",
        "Make a Word document titled R2 Summary",
        "Build an Excel workbook named R2 Expenses",
        "Crea an Excel workbook called Gastos R2",
    ),
    "package": scenario(
        ("package.install.prepare",),
        "Deja listo para instalar Mozilla.Firefox",
        "Resuelve el paquete 7zip.7zip y prepara su instalación",
        "Get Mozilla.Firefox ready for installation",
        "Resolve 7zip.7zip and stage its install",
        "Prepara Mozilla.Firefox for install",
    ),
    "peripheral": scenario(
        ("peripheral.list",),
        "Enumera el hardware periférico conectado",
        "Revisa qué accesorios USB están enchufados",
        "Show all attached peripheral hardware",
        "Inspect the USB accessories plugged in",
        "Muéstrame connected USB hardware",
    ),
    "reminder": scenario(
        ("reminder.list",),
        "Enumera los recordatorios que tengo agendados",
        "Revisa mis avisos recordatorios aún pendientes",
        "Show every reminder I have scheduled",
        "Inspect my outstanding reminder list",
        "Muéstrame scheduled reminders",
    ),
    "routine": scenario(
        ("routine.list",),
        "Enumera las automatizaciones rutinarias guardadas",
        "Revisa las rutinas disponibles en Baxy",
        "Show all routines saved in Baxy",
        "Inspect my stored routine list",
        "Muéstrame saved Baxy routines",
    ),
    "streaming": scenario(
        ("streaming.play.named",),
        "Inicia The Crown desde Netflix",
        "Encuentra Black Mirror en Netflix y reprodúcela",
        "Start The Crown on Netflix",
        "Locate Black Mirror on Netflix and play it",
        "Play The Crown desde Netflix",
    ),
    "system": scenario(
        ("system.status",),
        "Reporta el estado general de esta computadora",
        "Revisa la salud actual del sistema",
        "Report this computer's overall status",
        "Show the system's current health",
        "Muéstrame current computer health",
    ),
    "task": scenario(
        ("task.list",),
        "Enumera todo lo que tengo pendiente",
        "Revisa la lista de tareas abiertas",
        "Show every task still open",
        "Inspect my pending task list",
        "Muéstrame open tasks",
    ),
    "vision": scenario(
        ("capture.screenshot", "vision.describe"),
        "Captura el monitor e interpreta la escena visible",
        "Toma una captura de pantalla y explica qué muestra",
        "Capture the display and explain the visible scene",
        "Take a screen capture, then interpret what is shown",
        "Captura screen y explain what's visible",
    ),
    "web": scenario(
        ("web.search",),
        "Consulta en la web reseñas de binoculares",
        "Investiga online volcanes de la Patagonia",
        "Search online for binocular reviews",
        "Look on the web for Patagonian volcanoes",
        "Busca online binocular reviews",
    ),
    "wifi": scenario(
        ("wifi.status",),
        "Reporta si la conexión Wi-Fi está activa",
        "Revisa la conectividad inalámbrica actual",
        "Show whether the Wi-Fi connection is active",
        "Inspect current wireless connectivity",
        "Muéstrame current Wi-Fi connection",
    ),
    "window": scenario(
        ("window.active",),
        "Reporta qué ventana tiene el foco",
        "Revisa la aplicación visible en primer plano",
        "Show which window currently has focus",
        "Inspect the application in the foreground",
        "Muéstrame focused window",
    ),
}


CLARIFICATIONS = scenario(
    ("message.send",),
    "Dile a Ana que R2 está listo",
    "Mándale a Pedro el texto llego pronto",
    "Tell Morgan that R2 is ready",
    "Message Riley and say I am arriving",
    "Dile a Sam que I'm on my way",
)


@dataclass(frozen=True)
class Composition:
    operations: tuple[str, ...]
    utterance: Utterance


COMPOSITIONS = (
    Composition(
        ("system.status", "network.status"),
        Utterance("es", "Revisa el estado del sistema y después el estado de la red"),
    ),
    Composition(
        ("task.list", "reminder.list"),
        Utterance("es", "Muéstrame las tareas abiertas y los recordatorios pendientes"),
    ),
    Composition(
        ("note.list", "clipboard.read.text"),
        Utterance("es", "Enumera mis notas y después lee el texto del portapapeles"),
    ),
    Composition(
        ("bluetooth.device.list", "peripheral.list"),
        Utterance("es", "Lista los equipos Bluetooth y también los periféricos conectados"),
    ),
    Composition(
        ("browser.tabs.list", "window.active"),
        Utterance("en", "Show the active window and then list the browser tabs"),
    ),
    Composition(
        ("email.latest.read", "calendar.event.list"),
        Utterance("en", "Read the newest email and review today's calendar appointments"),
    ),
    Composition(
        ("audio.status", "media.status"),
        Utterance("en", "Check the sound state and what the media session is playing"),
    ),
    Composition(
        ("wifi.status", "network.status"),
        Utterance("en", "Inspect Wi-Fi connectivity and the overall network status"),
    ),
    Composition(
        ("web.search", "filesystem.known.search"),
        Utterance("spanglish", "Busca binocular reviews online y find factura en Downloads"),
    ),
    Composition(
        ("app.installed", "game.catalog.list"),
        Utterance("spanglish", "Confirma si Steam is installed y lista my local game catalog"),
    ),
)


def addressed_surface(utterance: Utterance) -> str:
    core = utterance.text.rstrip().rstrip(".?!")
    core = core[:1].lower() + core[1:]
    prefix = {
        "es": "Hola Baxy: ",
        "en": "Hey Baxy, ",
        "spanglish": "Hola Baxy: ",
    }[utterance.language]
    return f"{prefix}{core}."


def _surface_rows(
    *,
    case_prefix: str,
    family: str,
    case_type: str,
    owner: str,
    outcome: str,
    operations: tuple[str, ...],
    utterances: Iterable[Utterance],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    effect_sets = [list(operations)] if outcome == "action" else [[]]
    for index, utterance in enumerate(utterances, start=1):
        for surface, text in (
            ("plain", utterance.text),
            ("addressed", addressed_surface(utterance)),
        ):
            rows.append(
                {
                    "schema": "baxy.generalization-product-holdout.v2",
                    "case_id": f"{case_prefix}-{index:02d}-{surface}",
                    "family": family,
                    "case_type": case_type,
                    "owner": owner,
                    "language": utterance.language,
                    "surface": surface,
                    "text": text,
                    "outcome": outcome,
                    "compatible_terminal_operation_sets": [list(operations)],
                    "compatible_effect_operation_sets": effect_sets,
                    "execution_authority": False,
                    "blind_holdout": True,
                }
            )
    return rows


def build_rows(capabilities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    capability_rows = list(capabilities)
    catalog_names = {str(item["name"]) for item in capability_rows}
    catalog_families = {name.split(".", 1)[0] for name in catalog_names}
    if catalog_families != set(SCENARIOS):
        raise RuntimeError(
            "R2 family coverage drifted: "
            f"missing={sorted(catalog_families - set(SCENARIOS))} "
            f"stale={sorted(set(SCENARIOS) - catalog_families)}"
        )

    rows: list[dict[str, Any]] = []
    for family, value in SCENARIOS.items():
        missing = sorted(set(value.operations) - catalog_names)
        if missing:
            raise RuntimeError(f"{family} names unauthenticated operations: {missing}")
        rows.extend(
            _surface_rows(
                case_prefix=f"r2-{family}",
                family=family,
                case_type="single_action",
                owner=(
                    "app_private_memory_parser"
                    if family == "memory"
                    else "mind_sidecar"
                ),
                outcome="action",
                operations=value.operations,
                utterances=value.utterances,
            )
        )

    rows.extend(
        _surface_rows(
            case_prefix="r2-message-clarify",
            family="message",
            case_type="clarification",
            owner="mind_sidecar",
            outcome="clarify",
            operations=CLARIFICATIONS.operations,
            utterances=CLARIFICATIONS.utterances,
        )
    )
    for index, value in enumerate(COMPOSITIONS, start=1):
        missing = sorted(set(value.operations) - catalog_names)
        if missing:
            raise RuntimeError(f"composition {index} names unauthenticated operations: {missing}")
        rows.extend(
            _surface_rows(
                case_prefix=f"r2-composition-{index:02d}",
                family="composition",
                case_type="composition",
                owner="mind_sidecar",
                outcome="action",
                operations=value.operations,
                utterances=(value.utterance,),
            )
        )

    normalized = [normalize_text(str(row["text"])) for row in rows]
    if len(rows) != 340 or len(set(normalized)) != len(rows):
        raise RuntimeError("R2 population must contain 340 unique surfaces")
    return rows


def development_texts() -> set[str]:
    texts: set[str] = set()
    for path in DEVELOPMENT_CORPORA:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                texts.add(normalize_text(str(json.loads(line)["text"])))
    return texts


def build(args: argparse.Namespace) -> dict[str, Any]:
    paths = (
        args.output,
        args.preregistration,
        MIND_OUTPUT,
        MIND_AUDIT,
        MEMORY_TRX,
        PRODUCT_OUTPUT,
    )
    for path in paths:
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing R2 state: {path}")
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    rows = build_rows(capabilities)
    overlap = sorted(
        {normalize_text(str(row["text"])) for row in rows} & development_texts()
    )
    if overlap:
        raise RuntimeError(f"R2 overlaps a prior development or holdout text: {overlap}")
    write_jsonl_atomic(args.output, rows)

    catalog_sha256, operation_count = catalog_identity(capabilities)
    zero_failure_lower = math.pow(0.05, 1.0 / len(rows))
    manifest = {
        "schema": "baxy.generalization-product-preregistration.v2",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": "turn_decision_and_private_parser_evaluation_only",
        "method": {
            "matrix": (
                "31_families_x_5_lexical_bases_x_2_surfaces_plus_"
                "5_clarifications_x_2_surfaces_plus_10_compositions_x_2_surfaces"
            ),
            "test_types": [
                "minimum_functionality",
                "surface_invariance",
                "safe_clarification",
                "cross_family_composition",
            ],
            "minimum_cases": 300,
            "minimum_exact_turn_accuracy": 0.99,
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
            "public_families": len(SCENARIOS),
            "owners": {
                owner: sum(row["owner"] == owner for row in rows)
                for owner in ("mind_sidecar", "app_private_memory_parser")
            },
            "case_types": {
                case_type: sum(row["case_type"] == case_type for row in rows)
                for case_type in ("single_action", "clarification", "composition")
            },
            "languages": {
                language: sum(row["language"] == language for row in rows)
                for language in ("es", "en", "spanglish")
            },
            "surfaces": {
                surface: sum(row["surface"] == surface for row in rows)
                for surface in ("plain", "addressed")
            },
            "normalized_prior_overlap": 0,
        },
        "catalog": {"operations": operation_count, "sha256": catalog_sha256},
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": file_sha256(Path(__file__).resolve()),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "development_corpora_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in DEVELOPMENT_CORPORA
            },
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
            "mind_output": str(MIND_OUTPUT.relative_to(REPO)),
            "mind_raw_audit": str(MIND_AUDIT.relative_to(REPO)),
            "memory_trx": str(MEMORY_TRX.relative_to(REPO)),
            "product_output": str(PRODUCT_OUTPUT.relative_to(REPO)),
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
