"""Build and price a Cut-B development oracle independent of the recogniser.

The old Cut-B generator inherited its language frames from the same manually
maintained surface that the deterministic recogniser accepts.  Its result
therefore could not distinguish grammar coverage from generalisation.  This
instrument keeps the semantic oracle in this file: every target operation and
every natural-language request is declared without importing the recogniser,
its aliases, or an earlier Cut-B generator.

The resulting population is deliberately *development*, not a blind seal.  It
is opened here only to price recogniser reach before a future blind Cut-B is
preregistered.  The recogniser is invoked after generation solely to answer the
question that the old seal left unmeasured: how much of this independent
population bypasses the model path?
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CORPUS_OUTPUT = ROOT / "artifacts/development/independent_cut_b_oracle_r146.jsonl"
REPORT_OUTPUT = ROOT / "artifacts/audit/independent_cut_b_recogniser_reach_r146.json"
SCHEMA = "baxy.independent-cut-b-development-oracle.r146"


# This is a semantic specification, not an alias table.  It deliberately uses
# task descriptions that differ from the recogniser's imperative vocabulary.
# A target can name a short verified sequence when a family needs two steps.
CASES: dict[str, tuple[tuple[str, ...], dict[str, tuple[str, ...]]]] = {
    "app": (("app.installed",), {"es": ("¿Figura la Calculadora entre los programas presentes en esta máquina?", "Necesito saber si Steam existe aquí como aplicación instalada."), "en": ("Does this computer list Notepad among its installed programs?", "Please determine whether Steam is present as an installed application."), "spanglish": ("¿Puedes checkear si Notepad figura como installed program aquí?", "Necesito saber if Steam está present en esta máquina.")}),
    "audio": (("audio.status",), {"es": ("¿Qué configuración de sonido está usando ahora el equipo?", "Dame un diagnóstico del estado de sus parlantes y salida de audio."), "en": ("What sound configuration is the computer using right now?", "Give me a diagnostic of the current audio output."), "spanglish": ("¿Cuál es el current setup del sonido?", "Dame un audio diagnostic de la salida actual.")}),
    "backup": (("backup.list",), {"es": ("¿Qué resguardos de mis datos conserva BAXY?", "Enséñame el inventario de copias recuperables."), "en": ("Which saved recovery copies are available to me?", "Show the inventory of restorable data copies."), "spanglish": ("¿Qué recovery copies tengo available?", "Muéstrame el backup inventory que se puede restaurar.")}),
    "bluetooth": (("bluetooth.device.list",), {"es": ("¿Qué aparatos inalámbricos cercanos detecta el adaptador Bluetooth?", "Muéstrame los dispositivos Bluetooth que el PC puede ver."), "en": ("Which nearby devices can the Bluetooth adapter see?", "Show the Bluetooth hardware detected by this PC."), "spanglish": ("¿Qué Bluetooth devices nearby ve el computador?", "Muéstrame los wireless devices detectados por Bluetooth.")}),
    "browser": (("browser.tabs.list",), {"es": ("¿Qué sitios siguen abiertos en el navegador?", "Necesito revisar todas las páginas web que están en uso."), "en": ("Which websites are still open in the browser?", "I need to review every web page currently in use."), "spanglish": ("¿Qué websites siguen open en el browser?", "Necesito revisar las web pages que están active.")}),
    "calendar": (("calendar.event.list",), {"es": ("¿Qué compromisos tengo anotados para hoy?", "Revisa mi agenda de mañana y cuéntame las citas."), "en": ("What appointments do I have recorded for today?", "Review tomorrow's agenda and tell me the scheduled events."), "spanglish": ("¿Qué appointments tengo para today?", "Revisa tomorrow's agenda y dime mis events.")}),
    "capture": (("capture.screenshot",), {"es": ("Necesito una imagen exacta de lo que muestra el monitor ahora.", "Guarda una fotografía del escritorio tal como se ve en este momento."), "en": ("I need an exact image of what the monitor shows now.", "Save a picture of the desktop exactly as it appears."), "spanglish": ("Necesito una exact image de lo que muestra el monitor.", "Guarda un picture del desktop como se ve ahora.")}),
    "clipboard": (("clipboard.read.text",), {"es": ("¿Cuál es el contenido textual que quedó copiado?", "Muéstrame las palabras que están retenidas para pegar."), "en": ("What text content was left copied for pasting?", "Show me the words currently held for paste."), "spanglish": ("¿Cuál text quedó copied para paste?", "Muéstrame las words que están listas para pegar.")}),
    "email": (("email.latest.read",), {"es": ("Cuéntame qué dice el mensaje más nuevo de mi bandeja.", "Quiero leer el correo que llegó al final de mi inbox."), "en": ("Tell me what the newest message in my inbox says.", "I want to read the email that arrived most recently."), "spanglish": ("Cuéntame qué dice el newest message de mi inbox.", "Quiero read el email más recent que llegó.")}),
    "filesystem": (("filesystem.known.search",), {"es": ("Localiza en Documentos el informe que se llama balance anual.", "Necesito encontrar archivos llamados presupuesto dentro de Descargas."), "en": ("Locate the document called annual balance in Documents.", "I need to find files named budget inside Downloads."), "spanglish": ("Localiza el annual balance en Documents.", "Necesito find files llamados presupuesto dentro de Downloads.")}),
    "game": (("game.catalog.list",), {"es": ("¿Qué títulos tengo en mi biblioteca local de Steam?", "Enséñame el inventario de juegos que posee mi cuenta de Steam."), "en": ("Which titles are in my local Steam library?", "Show the game inventory owned by my Steam account."), "spanglish": ("¿Qué titles tengo en mi Steam library local?", "Enséñame el game inventory de mi cuenta Steam.")}),
    "input": (("input.keyboard.status",), {"es": ("¿Con qué distribución está escribiendo el teclado?", "Dime qué idioma de entrada está seleccionado ahora."), "en": ("Which layout is the keyboard typing with?", "Tell me which input language is selected now."), "spanglish": ("¿Qué keyboard layout está selected ahora?", "Dime cuál input language está activo.")}),
    "media": (("media.status",), {"es": ("¿Qué contenido se está oyendo o viendo en este instante?", "Necesito saber cuál es la sesión multimedia actual."), "en": ("What content is being heard or watched at this moment?", "I need to know the current media session."), "spanglish": ("¿Qué content se está playing ahora?", "Necesito saber la current media session.")}),
    "memory": (("memory.status",), {"es": ("¿Está disponible el recuerdo privado que BAXY guarda en este PC?", "Comprueba la salud de tu almacén local de recuerdos."), "en": ("Is BAXY's private memory on this PC available?", "Check the health of your local memory store."), "spanglish": ("¿Está available la private memory de BAXY en este PC?", "Checkea la salud de tu local memory store.")}),
    "message": (("message.recipient.resolve",), {"es": ("Busca cuál de mis contactos corresponde a Ana Pérez.", "Identifica a qué contacto guardado pertenece el nombre Carlos."), "en": ("Find which of my contacts corresponds to Ana Pérez.", "Identify the saved contact named Carlos."), "spanglish": ("Busca cuál contact corresponde a Ana Pérez.", "Identifica el saved contact llamado Carlos.")}),
    "network": (("network.status",), {"es": ("¿Tiene el equipo salida a la red en este momento?", "Dame el estado general de su conexión."), "en": ("Does the computer have network access at the moment?", "Give me the overall state of its connection."), "spanglish": ("¿Tiene el PC network access ahora?", "Dame el general status de su conexión.")}),
    "note": (("note.list",), {"es": ("¿Qué apuntes personales están guardados localmente?", "Enséñame el listado de las notas que he almacenado."), "en": ("Which personal notes are saved locally?", "Show the list of notes I have stored."), "spanglish": ("¿Qué personal notes están saved locally?", "Enséñame la list de notas que he stored.")}),
    "notification": (("notification.list.due",), {"es": ("¿Qué avisos ya vencieron y todavía siguen pendientes?", "Muéstrame las alertas cuyo plazo se cumplió."), "en": ("Which alerts are overdue and still pending?", "Show the notices whose due time has passed."), "spanglish": ("¿Qué alerts están overdue y pending?", "Muéstrame los notices cuyo due time ya pasó.")}),
    "ocr": (("capture.screenshot", "ocr.read"), {"es": ("Obtén una imagen de la pantalla y transcribe las letras que contiene.", "Necesito extraer por escrito todo lo legible que aparece en el monitor."), "en": ("Get an image of the screen and transcribe the letters it contains.", "I need every readable word extracted from the monitor."), "spanglish": ("Obtén una image de la screen y transcribe las letters.", "Necesito extraer every readable word del monitor.")}),
    "office": (("office.document.create",), {"es": ("Genera un archivo de Word con el nombre Informe independiente.", "Crea una planilla de Excel llamada Presupuesto independiente."), "en": ("Generate a Word file named Independent Report.", "Create an Excel spreadsheet called Independent Budget."), "spanglish": ("Genera un Word file llamado Informe independiente.", "Crea un Excel spreadsheet llamado Budget independiente.")}),
    "package": (("package.install.prepare",), {"es": ("Deja listo VideoLAN.VLC para que yo confirme su instalación.", "Averigua Microsoft.PowerToys y prepara el paso previo a instalarlo."), "en": ("Get VideoLAN.VLC ready for me to confirm its installation.", "Resolve Microsoft.PowerToys and prepare the step before installing it."), "spanglish": ("Deja VideoLAN.VLC ready para confirmar su installation.", "Resolve Microsoft.PowerToys y prepara el step antes de install.")}),
    "peripheral": (("peripheral.list",), {"es": ("¿Qué accesorios físicos están conectados al computador?", "Enumera los aparatos USB que reconoce esta máquina."), "en": ("Which physical accessories are connected to the computer?", "Enumerate the USB hardware this machine recognizes."), "spanglish": ("¿Qué physical accessories están connected al PC?", "Enumera el USB hardware que reconoce la máquina.")}),
    "reminder": (("reminder.list",), {"es": ("¿Qué cosas tengo programadas para recordar después?", "Enséñame mis recordatorios que aún no ocurren."), "en": ("What things am I scheduled to remember later?", "Show my reminders that have not happened yet."), "spanglish": ("¿Qué things tengo scheduled para remember later?", "Enséñame mis reminders que aún no happen.")}),
    "routine": (("routine.list",), {"es": ("¿Qué automatizaciones personales he guardado como rutinas?", "Muéstrame los procedimientos repetibles creados en BAXY."), "en": ("Which personal automations have I saved as routines?", "Show the repeatable procedures created in BAXY."), "spanglish": ("¿Qué personal automations he saved como routines?", "Muéstrame los repeatable procedures creados en BAXY.")}),
    "streaming": (("streaming.play.named",), {"es": ("Pon la serie Dark usando Netflix.", "Quiero que Stranger Things empiece a reproducirse en Netflix."), "en": ("Start playing the series Dark using Netflix.", "I want Stranger Things to begin playing on Netflix."), "spanglish": ("Pon Dark usando Netflix.", "Quiero que Stranger Things empiece playing en Netflix.")}),
    "system": (("system.status",), {"es": ("Dame un panorama de la salud general del computador.", "¿Cómo están los recursos y el funcionamiento del sistema?"), "en": ("Give me an overview of the computer's general health.", "How are the system resources and overall operation?"), "spanglish": ("Dame un overview de la general health del PC.", "¿Cómo están los system resources y el funcionamiento general?")}),
    "task": (("task.list",), {"es": ("¿Qué pendientes tengo anotados para hacer?", "Enséñame mi lista de trabajos que siguen abiertos."), "en": ("Which to-dos do I have written down?", "Show my list of work items that remain open."), "spanglish": ("¿Qué to-dos tengo written para hacer?", "Enséñame mi list de work items open.")}),
    "vision": (("capture.screenshot", "vision.describe"), {"es": ("Mira el monitor y explícame qué aparece en él.", "Necesito una descripción visual del escritorio actual."), "en": ("Look at the monitor and explain what appears on it.", "I need a visual description of the current desktop."), "spanglish": ("Mira el monitor y explain qué aparece.", "Necesito una visual description del current desktop.")}),
    "web": (("web.search",), {"es": ("Averigua en la red información sobre auroras australes.", "Investiga sitios web que hablen de telescopios portátiles."), "en": ("Find online information about southern lights.", "Research websites that discuss portable telescopes."), "spanglish": ("Averigua online information sobre auroras australes.", "Research websites que hablen de portable telescopes.")}),
    "wifi": (("wifi.status",), {"es": ("¿La conexión inalámbrica del equipo está funcionando?", "Comprueba si este PC sigue unido a la red Wi-Fi."), "en": ("Is the computer's wireless connection working?", "Check whether this PC is still joined to Wi-Fi."), "spanglish": ("¿Está working la wireless connection del PC?", "Checkea si este PC sigue joined al Wi-Fi.")}),
    "window": (("window.active",), {"es": ("¿Qué programa ocupa el primer plano en este instante?", "Identifica la aplicación que recibe el foco ahora."), "en": ("Which program occupies the foreground at this moment?", "Identify the application that has focus now."), "spanglish": ("¿Qué program ocupa el foreground ahora?", "Identifica la application que tiene focus.")}),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise(text: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFD", text).casefold()
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def build_rows() -> list[dict[str, Any]]:
    """Build the semantic oracle without consulting product recognition code."""

    rows: list[dict[str, Any]] = []
    for family, (operations, language_texts) in CASES.items():
        if set(language_texts) != {"es", "en", "spanglish"}:
            raise ValueError(f"{family} does not cover all three languages")
        for language, texts in language_texts.items():
            if len(texts) != 2:
                raise ValueError(f"{family}/{language} needs two independent texts")
            for index, text in enumerate(texts, start=1):
                rows.append(
                    {
                        "schema": SCHEMA,
                        "case_id": f"independent-r146-{family}-{language}-{index:02d}",
                        "family": family,
                        "language": language,
                        "text": text,
                        "expected_operations": list(operations),
                        "execution_authority": False,
                        "blind_holdout": False,
                        "oracle_origin": "manual_semantic_specification_independent_of_recogniser",
                    }
                )
    normalised = [_normalise(str(row["text"])) for row in rows]
    if len(rows) != 186 or len(set(normalised)) != len(rows):
        raise ValueError("independent oracle must contain 186 unique requests")
    return rows


def _recogniser() -> Any:
    """Load the product recogniser only after the independent corpus exists."""

    import sys

    source = str(ROOT / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    return importlib.import_module("baxy_mind.effect_intent")


def _available_operations() -> tuple[str, ...]:
    aliases = ROOT / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
    catalogue = json.loads(aliases.read_text(encoding="utf-8"))
    operations = {
        operation
        for alias in catalogue["aliases"]
        for operation in [alias.get("target_operation"), *(alias.get("operations") or [])]
        if operation
    }
    return tuple(sorted(operations))


def measure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    recogniser = _recogniser()
    available = _available_operations()
    resolved_expected: list[dict[str, Any]] = []
    resolved_other: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, int]] = {}
    by_language: dict[str, dict[str, int]] = {}

    for row in rows:
        expected = tuple(row["expected_operations"])
        result = recogniser.resolve_explicit_effects(row["text"], available, (), ())
        observed = tuple(result.operations) if result is not None else ()
        bucket = (
            resolved_expected
            if observed == expected
            else resolved_other
            if observed
            else unresolved
        )
        bucket.append({**row, "observed_operations": list(observed)})
        for summary, key in ((by_family, row["family"]), (by_language, row["language"])):
            counter = summary.setdefault(key, {"rows": 0, "resolved_expected": 0})
            counter["rows"] += 1
            counter["resolved_expected"] += int(observed == expected)

    def summary(values: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
        return {
            key: {
                **value,
                "recogniser_reach": round(value["resolved_expected"] / value["rows"], 4),
            }
            for key, value in sorted(values.items())
        }

    return {
        "rows": len(rows),
        "resolved_expected": len(resolved_expected),
        "resolved_other": len(resolved_other),
        "unresolved": len(unresolved),
        "recogniser_reach": round(len(resolved_expected) / len(rows), 4),
        "by_family": summary(by_family),
        "by_language": summary(by_language),
        "resolved_expected_rows": resolved_expected,
        "resolved_other_rows": resolved_other,
        "unresolved_rows": unresolved,
    }


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcome = measure(rows)
    corpus_bytes = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )
    return {
        "schema": "baxy.independent-cut-b-recogniser-reach.r146",
        "measured_on": "2026-08-13",
        "scope": "opened_development_oracle_not_a_blind_cut_b_seal",
        "independence": {
            "generator_uses_recogniser": False,
            "generator_uses_alias_catalogue": False,
            "generator_uses_prior_cut_b_generator": False,
            "target_operations_are_a_manual_semantic_specification": True,
            "recogniser_is_loaded_only_after_generation_for_measurement": True,
        },
        "execution": {
            "product_started": False,
            "decider_invoked": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__).resolve()),
            "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "alias_catalogue_sha256": _sha256(
                ROOT / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
            ),
            "effect_intent_sha256": _sha256(ROOT / "src/baxy_mind/effect_intent.py"),
        },
        "population": {
            "rows": len(rows),
            "families": len(CASES),
            "languages": dict(sorted(Counter(row["language"] for row in rows).items())),
            "rows_per_family": 6,
            "targeted_operations": sorted(
                {operation for operations, _ in CASES.values() for operation in operations}
            ),
        },
        "recogniser_measurement": outcome,
        "finding": (
            "This is an opened development preflight, not a new blind Cut-B seal. "
            "Its recogniser reach prices how much of an independently specified "
            "semantic population would bypass the model path before a future "
            "blind oracle is preregistered."
        ),
        "limits": [
            "manual semantic labels require independent human audit before sealing",
            "this prices only deterministic recogniser reach, not end-to-end accuracy",
            "the population is opened development data and cannot accredit Cut B",
        ],
    }


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> int:
    rows = build_rows()
    corpus = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )
    _write_bytes(CORPUS_OUTPUT, corpus)
    report = build_report(rows)
    _write_bytes(
        REPORT_OUTPUT,
        (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    measured = report["recogniser_measurement"]
    print(
        f"independent Cut-B development oracle: {measured['resolved_expected']}/"
        f"{measured['rows']} recogniser reach ({measured['recogniser_reach']:.1%})"
    )
    print(f"corpus: {CORPUS_OUTPUT.relative_to(ROOT).as_posix()}")
    print(f"artifact: {REPORT_OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
