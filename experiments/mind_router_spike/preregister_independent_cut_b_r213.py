"""Freeze a new Cut-B corpus that does not inherit recogniser grammar.

R146 is opened development data and was consumed by R186.  R213 is a separate
manual semantic specification: it never imports aliases, the recogniser, or an
earlier Cut-B builder while generating its request text.  A later runner may
measure recogniser reach exactly once; this module deliberately does not.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/independent_cut_b_r213.jsonl"
PREREGISTRATION = REPO / "artifacts/holdout/independent_cut_b_r213.preregistration.json"
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
PRIOR_SOURCES = (
    REPO / "artifacts/development/independent_cut_b_oracle_r146.jsonl",
    REPO / "artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json",
    REPO / "artifacts/holdout/generalization_product_current_tree_r28.jsonl",
    *sorted((REPO / "artifacts/holdout").glob("veto_reach_v*.json*")),
)


# The language is independently authored from a task's user-facing outcome.
# It is intentionally not sampled from aliases, recogniser phrases, or R146.
CASES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "app": (
        ("app.installed",),
        {
            "es": "¿Está instalada la calculadora en esta estación?",
            "en": "Can you tell whether Paint is present on this workstation?",
            "spanglish": "¿Puedes decirme if Calculator is present en esta workstation?",
        },
    ),
    "audio": (
        ("audio.status",),
        {
            "es": "¿Por dónde está saliendo el sonido del equipo?",
            "en": "Which output is this machine using for sound?",
            "spanglish": "¿Qué sound output está usando esta machine?",
        },
    ),
    "backup": (
        ("backup.list",),
        {
            "es": "¿Qué puntos de recuperación de datos puedo usar?",
            "en": "Which data recovery points can I use?",
            "spanglish": "¿Qué data recovery points tengo available?",
        },
    ),
    "bluetooth": (
        ("bluetooth.device.list",),
        {
            "es": "¿Qué equipos cercanos detecta el adaptador inalámbrico?",
            "en": "What nearby gear can the wireless adapter discover?",
            "spanglish": "¿Qué nearby gear puede discover el wireless adapter?",
        },
    ),
    "browser": (
        ("browser.tabs.list",),
        {
            "es": "Enumera las páginas que dejé abiertas para navegar.",
            "en": "List the pages I left open for browsing.",
            "spanglish": "List las pages que dejé open para browsing.",
        },
    ),
    "calendar": (
        ("calendar.event.list",),
        {
            "es": "Repasa los compromisos que tengo anotados para mañana.",
            "en": "Review the commitments I have noted for tomorrow.",
            "spanglish": "Review los commitments que tengo noted para tomorrow.",
        },
    ),
    "capture": (
        ("capture.screenshot",),
        {
            "es": "Necesito conservar una imagen de lo que se ve ahora mismo.",
            "en": "I need to preserve an image of what is visible right now.",
            "spanglish": "Necesito preserve una image de lo que está visible ahora.",
        },
    ),
    "clipboard": (
        ("clipboard.read.text",),
        {
            "es": "¿Qué palabras quedaron preparadas para insertarse?",
            "en": "What words are waiting to be inserted?",
            "spanglish": "¿Qué words quedaron waiting para insertarse?",
        },
    ),
    "email": (
        ("email.latest.read",),
        {
            "es": "Lee el mensaje que llegó último a mi bandeja.",
            "en": "Read the message that arrived last in my inbox.",
            "spanglish": "Read el message que llegó last a mi inbox.",
        },
    ),
    "filesystem": (
        ("filesystem.known.search",),
        {
            "es": "Encuentra el archivo llamado cuentas marzo en Documentos.",
            "en": "Find the file named March accounts in Documents.",
            "spanglish": "Find el file llamado March accounts en Documents.",
        },
    ),
    "game": (
        ("game.catalog.list",),
        {
            "es": "¿Qué juegos reconoce mi biblioteca de Steam?",
            "en": "Which games does my Steam library recognize?",
            "spanglish": "¿Qué games reconoce mi Steam library?",
        },
    ),
    "input": (
        ("input.keyboard.status",),
        {
            "es": "¿Qué distribución está activa para escribir?",
            "en": "Which layout is active for typing?",
            "spanglish": "¿Qué layout está active para typing?",
        },
    ),
    "media": (
        ("media.status",),
        {
            "es": "¿Cuál es la reproducción multimedia que está en curso?",
            "en": "Which media playback is currently underway?",
            "spanglish": "¿Cuál media playback está currently underway?",
        },
    ),
    "memory": (
        ("memory.status",),
        {
            "es": "Comprueba si tu recuerdo privado está sano en este computador.",
            "en": "Check whether your private recollection is healthy on this computer.",
            "spanglish": "Checkea si tu private recollection está healthy en este computer.",
        },
    ),
    "message": (
        ("message.recipient.resolve",),
        {
            "es": "Averigua cuál contacto guardado corresponde a Sofía Rojas.",
            "en": "Determine which saved contact corresponds to Sofia Rojas.",
            "spanglish": "Determine cuál saved contact corresponde a Sofía Rojas.",
        },
    ),
    "network": (
        ("network.status",),
        {
            "es": "¿El computador puede comunicarse con la red ahora?",
            "en": "Can this computer communicate with the network now?",
            "spanglish": "¿Este computer puede communicate con the network ahora?",
        },
    ),
    "note": (
        ("note.list",),
        {
            "es": "Muéstrame los apuntes personales que tengo guardados aquí.",
            "en": "Show the personal jottings I have saved here.",
            "spanglish": "Show los personal jottings que tengo saved aquí.",
        },
    ),
    "notification": (
        ("notification.list.due",),
        {
            "es": "¿Qué avisos ya pasaron de su fecha y siguen pendientes?",
            "en": "Which notices are past their date and still pending?",
            "spanglish": "¿Qué notices están past their date y still pending?",
        },
    ),
    "ocr": (
        ("capture.screenshot", "ocr.read"),
        {
            "es": "Extrae por escrito las letras que aparecen en la pantalla.",
            "en": "Extract in writing the letters appearing on the screen.",
            "spanglish": "Extract por escrito las letters que aparecen on screen.",
        },
    ),
    "office": (
        ("office.document.create",),
        {
            "es": "Crea un documento de Word titulado Informe de julio.",
            "en": "Create a Word document titled July report.",
            "spanglish": "Create un Word document titulado July report.",
        },
    ),
    "package": (
        ("package.install.prepare",),
        {
            "es": "Deja preparado 7zip.7zip para que yo decida instalarlo.",
            "en": "Prepare 7zip.7zip so that I can decide whether to install it.",
            "spanglish": "Prepare 7zip.7zip para que yo decide whether to install it.",
        },
    ),
    "peripheral": (
        ("peripheral.list",),
        {
            "es": "¿Qué accesorios físicos reconoce el ordenador conectado?",
            "en": "Which connected physical accessories does the computer recognize?",
            "spanglish": "¿Qué connected physical accessories reconoce el computer?",
        },
    ),
    "reminder": (
        ("reminder.list",),
        {
            "es": "Repasa las cosas que me pedí recordar más adelante.",
            "en": "Review the things I asked myself to remember later.",
            "spanglish": "Review las things que me pedí remember later.",
        },
    ),
    "routine": (
        ("routine.list",),
        {
            "es": "¿Qué secuencias automáticas personales dejé configuradas?",
            "en": "Which personal automatic sequences did I configure?",
            "spanglish": "¿Qué personal automatic sequences dejé configured?",
        },
    ),
    "streaming": (
        ("streaming.play.named",),
        {
            "es": "Reproduce la película Arrival mediante Netflix.",
            "en": "Play the film Arrival through Netflix.",
            "spanglish": "Play la película Arrival through Netflix.",
        },
    ),
    "system": (
        ("system.status",),
        {
            "es": "Dime cómo anda en conjunto esta máquina.",
            "en": "Tell me how this machine is doing overall.",
            "spanglish": "Dime how this machine está doing overall.",
        },
    ),
    "task": (
        ("task.list",),
        {
            "es": "¿Qué labores aún me quedan registradas?",
            "en": "Which chores do I still have recorded?",
            "spanglish": "¿Qué chores todavía tengo recorded?",
        },
    ),
    "vision": (
        ("capture.screenshot", "vision.describe"),
        {
            "es": "Observa el display y cuéntame la escena actual.",
            "en": "Observe the display and tell me the current scene.",
            "spanglish": "Observe el display y cuéntame the current scene.",
        },
    ),
    "web": (
        ("web.search",),
        {
            "es": "Busca información en internet sobre cultivos hidropónicos.",
            "en": "Look online for information about hydroponic crops.",
            "spanglish": "Look online por información sobre hydroponic crops.",
        },
    ),
    "wifi": (
        ("wifi.status",),
        {
            "es": "¿Sigue enlazado este equipo a la red inalámbrica?",
            "en": "Is this device still linked to the wireless network?",
            "spanglish": "¿Este device sigue linked a la wireless network?",
        },
    ),
    "window": (
        ("window.active",),
        {
            "es": "¿Qué aplicación está recibiendo las teclas en este momento?",
            "en": "Which application is receiving keystrokes at this moment?",
            "spanglish": "¿Qué application está receiving keystrokes ahora?",
        },
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise(text: str) -> str:
    folded = "".join(
        char
        for char in unicodedata.normalize("NFD", text).casefold()
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def _strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {_normalise(value)}
    if isinstance(value, list):
        return set().union(*(_strings(item) for item in value)) if value else set()
    if isinstance(value, dict):
        return (
            set().union(*(_strings(item) for item in value.values()))
            if value
            else set()
        )
    return set()


def _prior_normalised_texts() -> set[str]:
    texts: set[str] = set()
    for source in PRIOR_SOURCES:
        if not source.is_file():
            raise FileNotFoundError(f"r213_missing_prior_source:{source}")
        if source.suffix == ".jsonl":
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    texts.update(_strings(json.loads(line)))
        else:
            texts.update(_strings(json.loads(source.read_text(encoding="utf-8"))))
    return texts


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for family, (operations, translations) in sorted(CASES.items()):
        if set(translations) != {"es", "en", "spanglish"}:
            raise ValueError(f"r213_language_coverage:{family}")
        for language, text in sorted(translations.items()):
            rows.append(
                {
                    "schema": "baxy.independent-cut-b.r213.v1",
                    "case_id": f"independent-r213-{family}-{language}",
                    "family": family,
                    "language": language,
                    "text": text,
                    "expected_operations": list(operations),
                    "blind_holdout": True,
                    "execution_authority": False,
                    "oracle_origin": "manual_semantic_specification_independent_of_recogniser",
                }
            )
    normalised = [_normalise(row["text"]) for row in rows]
    if len(rows) != 93 or len(set(normalised)) != len(rows):
        raise ValueError("r213_unique_rows_contract")
    conflicts = sorted(set(normalised) & _prior_normalised_texts())
    if conflicts:
        raise ValueError(f"r213_textual_overlap:{conflicts[:3]}")
    return rows


def build() -> dict[str, Any]:
    rows = build_rows()
    corpus = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )
    return {
        "schema": "baxy.independent-cut-b.r213-preregistration.v1",
        "authority": "sealed_before_recogniser_or_model_measurement",
        "population": {
            "rows": len(rows),
            "families": len(CASES),
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "recogniser_majority_limit": 0.5,
        },
        "constraints": {
            "generator_imports_recogniser": False,
            "generator_imports_alias_catalogue": False,
            "prior_cut_b_builder_imported": False,
            "recogniser_measured": False,
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "catalog_sha256": _sha256(CATALOG),
            "prior_sources": {
                source.relative_to(REPO).as_posix(): _sha256(source)
                for source in PRIOR_SOURCES
            },
            "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        },
        "acceptance": {
            "recogniser_reach_must_be_less_than": 0.5,
            "end_to_end_exact_or_useful_clarification_minimum": 0.95,
            "cause_buckets_required": ["retrieval", "decision", "veto"],
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
            ],
        },
        "next_step": "Commit this preregistration unchanged, then run a separate read-only recogniser-reach measurement once before any model candidate is designed.",
    }


def main() -> None:
    rows = build_rows()
    CORPUS.write_bytes(
        b"".join(
            (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            for row in rows
        )
    )
    PREREGISTRATION.write_bytes(
        (
            json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )


if __name__ == "__main__":
    main()
