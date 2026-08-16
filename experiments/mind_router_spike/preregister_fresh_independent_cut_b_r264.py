"""Seal a fresh Cut-B population without using recogniser or R196 language."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
R196 = REPO / "artifacts/development/r196_full_provenance_classifier_training.jsonl"
CORPUS = REPO / "artifacts/development/fresh_independent_cut_b_r264.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/development/fresh_independent_cut_b_r264.preregistration.json"
)
SCHEMA = "baxy.fresh-independent-cut-b.r264.v1"


# Each row is a manually specified semantic request.  Generation must never
# inspect aliases, recogniser code, earlier Cut-B builders, or R196 language.
# The catalogue is read only to reject a stale operation name before sealing.
CASES: tuple[dict[str, object], ...] = (
    {
        "case": "app.open",
        "family": "app",
        "operations": ("app.open",),
        "texts": {
            "es": "Abre la Calculadora para que pueda usarla ahora.",
            "en": "Launch Notepad so I can use it now.",
            "spanglish": "Abre Paint para que lo pueda use ahora.",
        },
    },
    {
        "case": "audio.status",
        "family": "audio",
        "operations": ("audio.status",),
        "texts": {
            "es": "¿Por qué salida se escucha el sonido del equipo en este momento?",
            "en": "Which output is the computer using for sound right now?",
            "spanglish": "¿Qué sound output está usando el PC ahora?",
        },
    },
    {
        "case": "backup.list",
        "family": "backup",
        "operations": ("backup.list",),
        "texts": {
            "es": "Muéstrame las copias de respaldo que puedo recuperar.",
            "en": "Show the backup copies that I can restore.",
            "spanglish": "Muéstrame los backup copies que puedo restore.",
        },
    },
    {
        "case": "bluetooth.device.list",
        "family": "bluetooth",
        "operations": ("bluetooth.device.list",),
        "texts": {
            "es": "¿Qué dispositivos Bluetooth cercanos detecta esta máquina?",
            "en": "Which nearby Bluetooth devices can this machine detect?",
            "spanglish": "¿Qué Bluetooth devices nearby detecta esta máquina?",
        },
    },
    {
        "case": "browser.tabs.list",
        "family": "browser",
        "operations": ("browser.tabs.list",),
        "texts": {
            "es": "Enumera los sitios que todavía tengo abiertos en el navegador.",
            "en": "List the sites that I still have open in the browser.",
            "spanglish": "List los sites que todavía tengo open en el browser.",
        },
    },
    {
        "case": "calendar.event.list",
        "family": "calendar",
        "operations": ("calendar.event.list",),
        "texts": {
            "es": "Revisa las citas que tengo registradas para mañana.",
            "en": "Review the appointments that I have recorded for tomorrow.",
            "spanglish": "Review las appointments que tengo recorded para tomorrow.",
        },
    },
    {
        "case": "capture.screenshot",
        "family": "capture",
        "operations": ("capture.screenshot",),
        "texts": {
            "es": "Guarda una imagen exacta de la pantalla como está ahora.",
            "en": "Save an exact image of the screen as it is now.",
            "spanglish": "Guarda una exact image de la screen como está ahora.",
        },
    },
    {
        "case": "clipboard.read.text",
        "family": "clipboard",
        "operations": ("clipboard.read.text",),
        "texts": {
            "es": "¿Qué texto quedó listo para pegar?",
            "en": "What text is currently ready to paste?",
            "spanglish": "¿Qué text quedó ready para paste?",
        },
    },
    {
        "case": "email.latest.read",
        "family": "email",
        "operations": ("email.latest.read",),
        "texts": {
            "es": "Lee el correo más reciente de mi bandeja de entrada.",
            "en": "Read the most recent email in my inbox.",
            "spanglish": "Read el email más recent de mi inbox.",
        },
    },
    {
        "case": "filesystem.known.search",
        "family": "filesystem",
        "operations": ("filesystem.known.search",),
        "texts": {
            "es": "Encuentra el archivo llamado cuentas de marzo en Documentos.",
            "en": "Find the file named March accounts in Documents.",
            "spanglish": "Find el file llamado March accounts en Documents.",
        },
    },
    {
        "case": "game.catalog.list",
        "family": "game",
        "operations": ("game.catalog.list",),
        "texts": {
            "es": "¿Qué juegos reconoce mi biblioteca local de Steam?",
            "en": "Which games does my local Steam library recognize?",
            "spanglish": "¿Qué games reconoce mi local Steam library?",
        },
    },
    {
        "case": "input.keyboard.status",
        "family": "input",
        "operations": ("input.keyboard.status",),
        "texts": {
            "es": "¿Qué distribución está activa para escribir en el teclado?",
            "en": "Which keyboard layout is active for typing?",
            "spanglish": "¿Qué keyboard layout está active para typing?",
        },
    },
    {
        "case": "media.status",
        "family": "media",
        "operations": ("media.status",),
        "texts": {
            "es": "¿Qué reproducción multimedia está en curso ahora?",
            "en": "Which media playback is currently underway?",
            "spanglish": "¿Cuál media playback está currently underway?",
        },
    },
    {
        "case": "memory.status",
        "family": "memory",
        "operations": ("memory.status",),
        "texts": {
            "es": "Comprueba si tu memoria privada local está disponible.",
            "en": "Check whether your local private memory is available.",
            "spanglish": "Checkea si tu local private memory está available.",
        },
    },
    {
        "case": "message.recipient.resolve",
        "family": "message",
        "operations": ("message.recipient.resolve",),
        "texts": {
            "es": "Averigua cuál de mis contactos corresponde a Sofía Rojas.",
            "en": "Determine which saved contact corresponds to Sofia Rojas.",
            "spanglish": "Determine cuál saved contact corresponde a Sofía Rojas.",
        },
    },
    {
        "case": "network.status",
        "family": "network",
        "operations": ("network.status",),
        "texts": {
            "es": "¿Puede este computador comunicarse con la red ahora?",
            "en": "Can this computer communicate with the network now?",
            "spanglish": "¿Este computer puede communicate con la network ahora?",
        },
    },
    {
        "case": "note.list",
        "family": "note",
        "operations": ("note.list",),
        "texts": {
            "es": "Enséñame los apuntes personales que guardé aquí.",
            "en": "Show the personal notes that I saved here.",
            "spanglish": "Show los personal notes que guardé aquí.",
        },
    },
    {
        "case": "notification.list.due",
        "family": "notification",
        "operations": ("notification.list.due",),
        "texts": {
            "es": "¿Qué avisos ya vencieron y todavía están pendientes?",
            "en": "Which alerts are overdue and still pending?",
            "spanglish": "¿Qué alerts están overdue y todavía pending?",
        },
    },
    {
        "case": "ocr.read",
        "family": "ocr",
        "operations": ("capture.screenshot", "ocr.read"),
        "texts": {
            "es": "Transcribe el texto que aparece ahora en la pantalla.",
            "en": "Transcribe the text that is now visible on the screen.",
            "spanglish": "Transcribe el text que ahora está visible en la screen.",
        },
    },
    {
        "case": "office.document.create",
        "family": "office",
        "operations": ("office.document.create",),
        "texts": {
            "es": "Crea un documento Office nuevo llamado Informe de julio.",
            "en": "Create a new Office document named July report.",
            "spanglish": "Create un nuevo Office document llamado July report.",
        },
    },
    {
        "case": "office.document.read",
        "family": "office",
        "operations": ("office.document.read",),
        "texts": {
            "es": "Lee el contenido del documento Office que está abierto.",
            "en": "Read the content of the Office document that is open.",
            "spanglish": "Read el contenido del Office document que está open.",
        },
    },
    {
        "case": "office.word.append",
        "family": "office",
        "operations": ("office.word.append",),
        "texts": {
            "es": "Añade al final del Word abierto la frase Acuerdo revisado.",
            "en": "Append the sentence Agreement reviewed to the open Word document.",
            "spanglish": "Append la frase Agreement reviewed al Word document open.",
        },
    },
    {
        "case": "office.word.close",
        "family": "office",
        "operations": ("office.word.close",),
        "texts": {
            "es": "Cierra el documento Word activo si no tiene cambios pendientes.",
            "en": "Close the active Word document if it has no pending changes.",
            "spanglish": "Close el active Word document si no tiene pending changes.",
        },
    },
    {
        "case": "office.word.discard",
        "family": "office",
        "operations": ("office.word.discard",),
        "confirmation_required": True,
        "texts": {
            "es": "Descarta sin guardar los cambios del documento Word actual.",
            "en": "Discard the unsaved changes in the current Word document.",
            "spanglish": "Discard los unsaved changes del current Word document.",
        },
    },
    {
        "case": "office.word.save",
        "family": "office",
        "operations": ("office.word.save",),
        "texts": {
            "es": "Guarda el documento Word que estoy editando.",
            "en": "Save the Word document that I am editing.",
            "spanglish": "Save el Word document que estoy editing.",
        },
    },
    {
        "case": "office.word.start",
        "family": "office",
        "operations": ("office.word.start",),
        "texts": {
            "es": "Inicia Word visible con un documento nuevo.",
            "en": "Start visible Word with a new document.",
            "spanglish": "Start Word visible con un new document.",
        },
    },
    {
        "case": "office.word.status",
        "family": "office",
        "operations": ("office.word.status",),
        "texts": {
            "es": "Dime el nombre, tamaño y guardado del Word que está activo.",
            "en": "Tell me the name, length, and save state of active Word.",
            "spanglish": "Dime el name, length y save state del active Word.",
        },
    },
    {
        "case": "package.install.prepare",
        "family": "package",
        "operations": ("package.install.prepare",),
        "texts": {
            "es": "Deja preparada la instalación de VideoLAN.VLC para que yo confirme.",
            "en": "Prepare VideoLAN.VLC for installation so that I can confirm it.",
            "spanglish": "Prepare VideoLAN.VLC para installation y yo confirmo.",
        },
    },
    {
        "case": "peripheral.list",
        "family": "peripheral",
        "operations": ("peripheral.list",),
        "texts": {
            "es": "Enumera los accesorios físicos conectados a este computador.",
            "en": "List the physical accessories connected to this computer.",
            "spanglish": "List los physical accessories connected a este computer.",
        },
    },
    {
        "case": "reminder.list",
        "family": "reminder",
        "operations": ("reminder.list",),
        "texts": {
            "es": "¿Qué recordatorios futuros tengo guardados?",
            "en": "Which future reminders do I have saved?",
            "spanglish": "¿Qué future reminders tengo saved?",
        },
    },
    {
        "case": "routine.list",
        "family": "routine",
        "operations": ("routine.list",),
        "texts": {
            "es": "Muéstrame las rutinas personales que dejé configuradas.",
            "en": "Show the personal routines that I configured.",
            "spanglish": "Show las personal routines que dejé configured.",
        },
    },
    {
        "case": "streaming.play.named",
        "family": "streaming",
        "operations": ("streaming.play.named",),
        "texts": {
            "es": "Reproduce la serie Dark en Netflix.",
            "en": "Play the series Dark on Netflix.",
            "spanglish": "Play la serie Dark en Netflix.",
        },
    },
    {
        "case": "system.status",
        "family": "system",
        "operations": ("system.status",),
        "texts": {
            "es": "Dame un panorama del estado general de este equipo.",
            "en": "Give me an overview of this computer's general state.",
            "spanglish": "Dame un overview del general state de este computer.",
        },
    },
    {
        "case": "task.list",
        "family": "task",
        "operations": ("task.list",),
        "texts": {
            "es": "¿Qué tareas todavía tengo anotadas por hacer?",
            "en": "Which tasks do I still have noted to do?",
            "spanglish": "¿Qué tasks todavía tengo noted por hacer?",
        },
    },
    {
        "case": "vision.describe",
        "family": "vision",
        "operations": ("capture.screenshot", "vision.describe"),
        "texts": {
            "es": "Mira la pantalla y descríbeme la escena actual.",
            "en": "Look at the screen and describe the current scene.",
            "spanglish": "Look at la screen y describe la current scene.",
        },
    },
    {
        "case": "web.search",
        "family": "web",
        "operations": ("web.search",),
        "texts": {
            "es": "Busca información en la web sobre cultivos hidropónicos.",
            "en": "Search the web for information about hydroponic crops.",
            "spanglish": "Search la web por información sobre hydroponic crops.",
        },
    },
    {
        "case": "wifi.status",
        "family": "wifi",
        "operations": ("wifi.status",),
        "texts": {
            "es": "¿Sigue este computador conectado a la red inalámbrica?",
            "en": "Is this computer still connected to the wireless network?",
            "spanglish": "¿Este computer sigue connected a la wireless network?",
        },
    },
    {
        "case": "window.active",
        "family": "window",
        "operations": ("window.active",),
        "texts": {
            "es": "¿Qué aplicación está en primer plano ahora?",
            "en": "Which application is in the foreground now?",
            "spanglish": "¿Qué application está en foreground ahora?",
        },
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise(text: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFD", text).casefold()
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def current_catalogue_operations() -> set[str]:
    catalogue = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {
        str(capability["name"])
        for capability in catalogue["catalogue"]["capabilities"]
    }


def r196_normalised_texts() -> set[str]:
    return {
        normalise(str(json.loads(line)["text"]))
        for line in R196.read_text(encoding="utf-8").splitlines()
        if line
    }


def build_rows() -> list[dict[str, Any]]:
    if not CATALOG.is_file() or not R196.is_file():
        raise RuntimeError("R264 requires the current catalogue and R196 provenance")
    catalogue_operations = current_catalogue_operations()
    rows: list[dict[str, Any]] = []
    for case in CASES:
        texts = case["texts"]
        operations = case["operations"]
        if not isinstance(texts, dict) or set(texts) != {"es", "en", "spanglish"}:
            raise RuntimeError(f"R264 language contract failed for {case['case']}")
        if not isinstance(operations, tuple) or not set(operations) <= catalogue_operations:
            raise RuntimeError(f"R264 current catalogue contract failed for {case['case']}")
        for language, text in sorted(texts.items()):
            if not isinstance(text, str):
                raise RuntimeError(f"R264 text contract failed for {case['case']}")
            rows.append(
                {
                    "schema": SCHEMA,
                    "case_id": f"fresh-r264-{case['case']}-{language}",
                    "family": case["family"],
                    "language": language,
                    "text": text,
                    "expected_operations": list(operations),
                    "confirmation_required": bool(case.get("confirmation_required", False)),
                    "blind_holdout": True,
                    "execution_authority": False,
                    "oracle_origin": "manual_semantic_specification_independent_of_recogniser_and_r196",
                }
            )
    normalised = [normalise(str(row["text"])) for row in rows]
    if len(rows) != 114 or len(set(normalised)) != len(rows):
        raise RuntimeError("R264 requires 114 unique requests")
    if {str(row["family"]) for row in rows} != {
        str(capability).split(".", 1)[0] for capability in catalogue_operations
    }:
        raise RuntimeError("R264 must cover each current catalogue family")
    overlaps = set(normalised) & r196_normalised_texts()
    if overlaps:
        raise RuntimeError("R264 text overlaps R196; do not seal a reused request")
    return rows


def corpus_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )


def build() -> dict[str, object]:
    rows = build_rows()
    return {
        "schema": "baxy.fresh-independent-cut-b.r264-preregistration.v1",
        "authority": "sealed_before_recogniser_or_model_measurement",
        "population": {
            "rows": len(rows),
            "semantic_cases": len(CASES),
            "families": 31,
            "languages": {"es": 38, "en": 38, "spanglish": 38},
            "office_cases": 8,
            "confirmation_bound_cases": 3,
        },
        "independence": {
            "generator_imports_recogniser": False,
            "generator_imports_alias_catalogue": False,
            "generator_imports_prior_cut_b_builder": False,
            "generator_uses_r196_language": False,
            "generator_uses_current_catalogue_descriptions": False,
            "manual_semantic_specification": True,
        },
        "measurement_contract": {
            "first_measurement": "read-only recogniser reach through resolve_explicit_effects after this preregistration is committed unchanged",
            "recogniser_majority_limit": 0.5,
            "later_model_path_minimum": 0.95,
            "cause_buckets_required": ["retrieval", "decision", "veto"],
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
            ],
            "cannot_refute": "This preregistration alone cannot establish model-path success, OOS behavior, real provider effects, or latency.",
        },
        "constraints": {
            "recogniser_measured": False,
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "catalogue_sha256": sha256(CATALOG),
            "r196_sha256": sha256(R196),
            "corpus_sha256": hashlib.sha256(corpus_bytes(rows)).hexdigest(),
            "program_sha256": sha256(Path(__file__)),
        },
        "next_step": "Commit this preregistration unchanged, then run exactly one read-only recogniser-reach measurement before designing any model-path candidate.",
    }


def main() -> int:
    if CORPUS.exists() or PREREGISTRATION.exists():
        raise RuntimeError("R264 output already exists; refusing to reseal the population")
    rows = build_rows()
    CORPUS.write_bytes(corpus_bytes(rows))
    PREREGISTRATION.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
