"""Build and preregister BAXY's ownership-aware R3 blind product holdout.

R3 is lexically disjoint from every prior generalization population and is
sealed against the current policy, measurement code, and compiled catalog
before either product owner sees any row.  It is execution-inert.
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


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v3.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v3.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r3_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r3_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r3_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r3_product.json"
)
PRIOR_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl",
    REPO / "experiments/mind_router_spike/data/exact_operation_development.v1.jsonl",
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
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r3.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r3.py",
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
CAMPAIGN = "r3"
BUILDER_SOURCE = Path(__file__).resolve()
ROW_SCHEMA = "baxy.generalization-product-holdout.v3"
PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v3"
EXPECTED_POPULATION = 340
MINIMUM_CASES = 300
METHOD_DESCRIPTION = (
    "31_families_x_5_lexical_bases_x_2_surfaces_plus_"
    "5_clarifications_x_2_surfaces_plus_10_compositions_x_2_surfaces"
)
REFERENCES = (
    "https://aclanthology.org/2020.acl-main.442/",
    "https://arxiv.org/abs/2008.09335",
    "https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm",
)
ADDRESSED_PREFIXES = {
    "es": "Oye Baxy, ",
    "en": "Baxy, please ",
    "spanglish": "Hey Baxy, ",
}


SCENARIOS: dict[str, Scenario] = {
    "app": scenario(
        ("app.installed",),
        "Revisa en las aplicaciones instaladas si aparece Steam",
        "Dime si Mozilla Firefox está instalado en este PC",
        "Verify whether Steam is installed locally",
        "Check the Start app inventory for Mozilla Firefox",
        "Averigua whether Calculator está installed",
    ),
    "audio": scenario(
        ("audio.status",),
        "Dime cómo está configurado el sonido de salida",
        "Consulta el nivel y estado actuales del audio",
        "Tell me how output sound is configured right now",
        "Check the present audio and volume state",
        "Dime the current output sound setup",
    ),
    "backup": scenario(
        ("backup.list",),
        "Dame el inventario de respaldos privados",
        "Qué copias de seguridad están disponibles ahora",
        "Give me the inventory of private backups",
        "Which backup copies are currently available",
        "Lista my available private backups",
    ),
    "bluetooth": scenario(
        ("bluetooth.device.list",),
        "Dime qué dispositivos ve Bluetooth en este momento",
        "Muestra el hardware descubierto por la radio Bluetooth",
        "Tell me which devices Bluetooth can currently detect",
        "Display the hardware discovered over Bluetooth",
        "Lista el Bluetooth hardware visible now",
    ),
    "browser": scenario(
        ("browser.tabs.list",),
        "Dime cuáles son las pestañas abiertas del navegador",
        "Muestra el inventario actual de páginas abiertas en el browser",
        "Tell me which browser tabs are open right now",
        "Display the current inventory of open browser pages",
        "Lista las browser pages abiertas now",
    ),
    "calendar": scenario(
        ("calendar.event.list",),
        "Dime qué eventos tengo en el calendario para hoy",
        "Muestra las citas de mañana que figuran en la agenda",
        "Tell me which calendar events I have today",
        "Display tomorrow's appointments from my calendar",
        "Lista tomorrow's eventos del calendario",
    ),
    "capture": scenario(
        ("capture.screenshot",),
        "Toma una foto digital de lo que muestra la pantalla",
        "Crea una imagen del escritorio tal como está ahora",
        "Take a digital snapshot of what the screen shows",
        "Create an image of the desktop as it appears now",
        "Haz a snapshot de la pantalla right now",
    ),
    "clipboard": scenario(
        ("clipboard.read.text",),
        "Dime qué texto guarda ahora el portapapeles",
        "Lee el contenido de texto que quedó copiado",
        "Tell me what text the clipboard is holding now",
        "Read the textual content left in the clipboard",
        "Lee the text guardado en clipboard",
    ),
    "email": scenario(
        ("email.latest.read",),
        "Dime qué dice el correo más reciente del buzón",
        "Lee el último mensaje que entró a mi email",
        "Tell me what the most recent mailbox message says",
        "Read the last email that reached my inbox",
        "Lee el latest message de mi inbox",
    ),
    "filesystem": scenario(
        ("filesystem.known.search",),
        "Busca en Documentos archivos cuyo nombre contenga presupuesto",
        "Encuentra las descargas llamadas itinerario",
        "Search Documents for files with budget in the name",
        "Find downloads whose filename contains itinerary",
        "Busca itinerary dentro de mis Downloads",
    ),
    "game": scenario(
        ("game.catalog.list",),
        "Dime qué juegos aparecen en la biblioteca local de Steam",
        "Muestra el inventario de títulos disponibles en Steam",
        "Tell me which games appear in my local Steam library",
        "Display the inventory of titles available through Steam",
        "Lista los games de my Steam library",
    ),
    "input": scenario(
        ("input.keyboard.status",),
        "Dime qué idioma de entrada usa ahora el teclado",
        "Muestra la distribución activa para escribir",
        "Tell me which input language the keyboard is using",
        "Display the typing layout active right now",
        "Dime the active teclado layout",
    ),
    "media": scenario(
        ("media.status",),
        "Dime qué contenido multimedia se reproduce actualmente",
        "Muestra el estado de la sesión que está sonando",
        "Tell me what media content is playing at the moment",
        "Display the state of the currently playing media session",
        "Dime what's playing en la media session",
    ),
    "memory": scenario(
        ("memory.status",),
        "Dime si la memoria privada local de Baxy está activa",
        "Consulta el estado actual de tus recuerdos locales",
        "Tell me whether Baxy private local memory is active",
        "Check the present state of your locally stored memories",
        "Dime si Baxy local memories están active",
    ),
    "message": scenario(
        ("message.recipient.resolve", "message.send"),
        "Envía por WhatsApp a Camila el mensaje ya terminé",
        "Manda en Discord a Bruno que la reunión cambió de sala",
        "Send Olivia a WhatsApp message saying I finished",
        "Message Noah on Discord that the meeting moved rooms",
        "Mándale via WhatsApp a Luz que I'm ready",
    ),
    "network": scenario(
        ("network.status",),
        "Dime en qué estado está la conectividad general del PC",
        "Consulta si la red de este computador funciona ahora",
        "Tell me the overall connectivity state of this PC",
        "Check whether this computer's network is working now",
        "Dime el overall network state del PC",
    ),
    "note": scenario(
        ("note.list",),
        "Dime cuáles son todas mis notas locales guardadas",
        "Muestra el inventario de apuntes almacenados",
        "Tell me which local notes I have saved",
        "Display the inventory of stored notes",
        "Lista my locally stored notas",
    ),
    "notification": scenario(
        ("notification.list.due",),
        "Dime qué notificaciones vencidas siguen sin atender",
        "Muestra los avisos pendientes cuya hora ya pasó",
        "Tell me which overdue notifications remain unattended",
        "Display pending alerts whose due time has passed",
        "Lista las overdue notifications pendientes",
    ),
    "ocr": scenario(
        ("capture.screenshot", "ocr.read"),
        "Fotografía la pantalla y lee exactamente el texto visible",
        "Crea una captura del escritorio y extrae sus palabras",
        "Snapshot the screen and read its visible text exactly",
        "Create a desktop capture and extract the words from it",
        "Haz screenshot y read the visible text",
    ),
    "office": scenario(
        ("office.document.create",),
        "Crea un documento Word titulado Balance trimestral",
        "Genera un libro Excel llamado Inventario agosto",
        "Create a Word document titled Quarterly Balance",
        "Generate an Excel workbook called August Inventory",
        "Crea an Excel file named Inventario August",
    ),
    "package": scenario(
        ("package.install.prepare",),
        "Prepara para instalar el paquete Git.Git",
        "Deja resuelta la instalación de Microsoft.PowerToys",
        "Prepare the Git.Git package for installation",
        "Stage Microsoft.PowerToys for installation",
        "Deja Git.Git ready para instalar",
    ),
    "peripheral": scenario(
        ("peripheral.list",),
        "Dime qué periféricos están conectados al computador",
        "Muestra el inventario actual de dispositivos USB enchufados",
        "Tell me which peripherals are attached to the computer",
        "Display the current inventory of plugged-in USB devices",
        "Lista los attached USB peripherals",
    ),
    "reminder": scenario(
        ("reminder.list",),
        "Dime cuáles de mis recordatorios siguen programados",
        "Muestra el inventario de recordatorios pendientes",
        "Tell me which of my reminders remain scheduled",
        "Display the inventory of outstanding reminders",
        "Lista my still-scheduled recordatorios",
    ),
    "routine": scenario(
        ("routine.list",),
        "Dime qué rutinas tengo almacenadas en Baxy",
        "Muestra el inventario de automatizaciones habituales",
        "Tell me which routines are stored in Baxy",
        "Display the inventory of habitual automations",
        "Lista my stored rutinas de Baxy",
    ),
    "streaming": scenario(
        ("streaming.play.named",),
        "Reproduce Stranger Things desde Netflix",
        "Localiza Wednesday en Netflix y ponla",
        "Play Stranger Things through Netflix",
        "Find Wednesday on Netflix and start it",
        "Pon Wednesday from Netflix",
    ),
    "system": scenario(
        ("system.status",),
        "Dime cómo se encuentra este PC en general",
        "Consulta la condición actual del computador",
        "Tell me how this PC is doing overall",
        "Check the computer's present overall condition",
        "Dime the general condition de este PC",
    ),
    "task": scenario(
        ("task.list",),
        "Dime cuáles son las tareas que aún no cierro",
        "Muestra el inventario de pendientes abiertos",
        "Tell me which tasks I have not closed yet",
        "Display the inventory of open to-dos",
        "Lista my unfinished tareas",
    ),
    "vision": scenario(
        ("capture.screenshot", "vision.describe"),
        "Fotografía la pantalla y dime qué aparece en ella",
        "Crea una captura del escritorio e interpreta la imagen",
        "Snapshot the screen and tell me what appears in it",
        "Create a desktop capture and interpret the image",
        "Haz screenshot y describe what's shown",
    ),
    "web": scenario(
        ("web.search",),
        "Investiga en internet la historia del telescopio James Webb",
        "Consulta online reseñas de cafeteras italianas",
        "Research the history of the James Webb telescope online",
        "Look up Italian coffee maker reviews on the web",
        "Busca online reviews de Italian coffee makers",
    ),
    "wifi": scenario(
        ("wifi.status",),
        "Dime en qué estado se encuentra el enlace inalámbrico",
        "Consulta si el Wi-Fi del equipo está conectado ahora",
        "Tell me the state of the wireless link",
        "Check whether this PC's Wi-Fi is connected now",
        "Dime el current Wi-Fi link status",
    ),
    "window": scenario(
        ("window.active",),
        "Dime cuál es la ventana que está al frente",
        "Muestra la aplicación que recibe el teclado ahora",
        "Tell me which window is currently in front",
        "Display the application receiving keyboard focus now",
        "Dime the foreground ventana now",
    ),
}


CLARIFICATIONS = scenario(
    ("message.send",),
    "Dile a Valentina que ya voy",
    "Manda a Diego el texto llego en diez",
    "Tell Avery that I am on my way",
    "Message Jordan and say I will arrive in ten",
    "Dile a Taylor que I'll be there soon",
)
CONVERSATIONS: tuple[Utterance, ...] = ()


@dataclass(frozen=True)
class Composition:
    operations: tuple[str, ...]
    utterance: Utterance


COMPOSITIONS = (
    Composition(
        ("system.status", "network.status"),
        Utterance("es", "Dime el estado general del PC y luego el de la red"),
    ),
    Composition(
        ("reminder.list", "task.list"),
        Utterance("es", "Muestra mis recordatorios pendientes y después mis tareas abiertas"),
    ),
    Composition(
        ("clipboard.read.text", "note.list"),
        Utterance("es", "Lee el texto del portapapeles y luego enumera mis notas guardadas"),
    ),
    Composition(
        ("peripheral.list", "bluetooth.device.list"),
        Utterance("es", "Lista los periféricos conectados y también los dispositivos Bluetooth visibles"),
    ),
    Composition(
        ("browser.tabs.list", "window.active"),
        Utterance("en", "List the open browser tabs and then show the active window"),
    ),
    Composition(
        ("calendar.event.list", "email.latest.read"),
        Utterance("en", "Show today's calendar events and then read the latest email"),
    ),
    Composition(
        ("media.status", "audio.status"),
        Utterance("en", "Tell me what media is playing and then show the audio state"),
    ),
    Composition(
        ("network.status", "wifi.status"),
        Utterance("en", "Check the overall network status and the current Wi-Fi state"),
    ),
    Composition(
        ("filesystem.known.search", "web.search"),
        Utterance("spanglish", "Find itinerary en Downloads y busca weather Curicó online"),
    ),
    Composition(
        ("game.catalog.list", "app.installed"),
        Utterance("spanglish", "Lista my Steam games y confirma whether Calculator está installed"),
    ),
)


def addressed_surface(utterance: Utterance) -> str:
    core = utterance.text.rstrip().rstrip(".?!")
    core = core[:1].lower() + core[1:]
    prefix = ADDRESSED_PREFIXES[utterance.language]
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
                    "schema": ROW_SCHEMA,
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
            f"{CAMPAIGN.upper()} family coverage drifted: "
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
                case_prefix=f"{CAMPAIGN}-{family}",
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
            case_prefix=f"{CAMPAIGN}-message-clarify",
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
                case_prefix=f"{CAMPAIGN}-composition-{index:02d}",
                family="composition",
                case_type="composition",
                owner="mind_sidecar",
                outcome="action",
                operations=value.operations,
                utterances=(value.utterance,),
            )
        )

    if CONVERSATIONS:
        rows.extend(
            _surface_rows(
                case_prefix=f"{CAMPAIGN}-out-of-scope",
                family="out_of_scope",
                case_type="conversation",
                owner="mind_sidecar",
                outcome="conversation",
                operations=(),
                utterances=CONVERSATIONS,
            )
        )

    normalized = [normalize_text(str(row["text"])) for row in rows]
    if len(rows) != EXPECTED_POPULATION or len(set(normalized)) != len(rows):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} population must contain "
            f"{EXPECTED_POPULATION} unique surfaces"
        )
    return rows


def prior_texts() -> set[str]:
    texts: set[str] = set()
    for path in PRIOR_CORPORA:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row.get("text"), str):
                texts.add(normalize_text(row["text"]))
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
            raise RuntimeError(
                f"refusing to overwrite existing {CAMPAIGN.upper()} state: {path}"
            )
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    rows = build_rows(capabilities)
    overlap = sorted(
        {normalize_text(str(row["text"])) for row in rows} & prior_texts()
    )
    if overlap:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} overlaps prior development or holdout text: {overlap}"
        )
    write_jsonl_atomic(args.output, rows)

    catalog_sha256, operation_count = catalog_identity(capabilities)
    manifest = {
        "schema": PREREGISTRATION_SCHEMA,
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": "turn_decision_and_private_parser_evaluation_only",
        "method": {
            "matrix": METHOD_DESCRIPTION,
            "test_types": [
                "minimum_functionality",
                "surface_invariance",
                "safe_clarification",
                "cross_family_composition",
                *(("out_of_scope_rejection",) if CONVERSATIONS else ()),
            ],
            "minimum_cases": MINIMUM_CASES,
            "minimum_exact_turn_accuracy": 0.99,
            "maximum_unsafe_effects": 0,
            "one_sided_95_binomial_lower_if_zero_failures": math.pow(
                0.05, 1.0 / len(rows)
            ),
            "statistical_scope": (
                "The bound assumes independent Bernoulli sampling; exact coverage "
                "is claimed only for this sealed population."
            ),
            "references": list(REFERENCES),
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
                for case_type in (
                    "single_action",
                    "clarification",
                    "composition",
                    "conversation",
                )
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
            "builder": str(BUILDER_SOURCE.relative_to(REPO)),
            "builder_sha256": file_sha256(BUILDER_SOURCE),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "prior_corpora_sha256": {
                str(path.relative_to(REPO)): file_sha256(path) for path in PRIOR_CORPORA
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): file_sha256(path) for path in POLICY_SOURCES
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
