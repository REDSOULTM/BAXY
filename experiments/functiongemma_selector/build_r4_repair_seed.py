"""Build contract-authored contrastive rows for opened R4 failure families."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    family_operations,
    normalize_text,
    read_jsonl,
    selection_tools,
    sha256,
    write_jsonl,
)


OUTPUT = REPO / "artifacts/research/functiongemma_r4_repair_seed.v1.jsonl"
HELDOUTS = [
    REPO / "experiments/mind_router_spike/data/exact_operation_development.v1.jsonl",
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
]
R4 = REPO / "artifacts/fixes/mtop_product_validation_development_r4_current.json"

AUTHORED: dict[str, dict[str, list[str]]] = {
    "notification.cancel.latest": {
        "en": [
            "Cancel the alarm I set.",
            "Turn off my latest alarm.",
            "Deactivate the most recent alarm.",
            "Remove the alarm I scheduled.",
            "Delete my current alarm before it rings.",
            "Cancel my last reminder.",
            "Turn off the reminder I just created.",
            "Remove the latest BAXY alarm.",
        ],
        "es": [
            "Cancela la alarma que puse.",
            "Desactiva mi última alarma.",
            "Elimina la alarma más reciente.",
            "Quita la alarma que programé.",
            "Borra mi alarma antes de que suene.",
            "Cancela mi último recordatorio.",
            "Desactiva el recordatorio que acabo de crear.",
            "Anula la alarma más nueva.",
        ],
        "spanglish": [
            "Cancela my latest alarm.",
            "Turn off la alarma que puse.",
            "Delete mi último recordatorio.",
            "Desactiva the last alarm.",
        ],
    },
    "notification.dismiss": {
        "en": [
            "Stop the alarm that's ringing.",
            "Silence the alarm, I heard it.",
            "Dismiss this ringing alarm.",
            "Make that alarm stop ringing.",
            "Stop the alert sounding right now.",
            "I'm awake; silence it.",
            "I heard the alarm; dismiss it.",
            "Quiet the notification that just went off.",
        ],
        "es": [
            "Para la alarma que está sonando.",
            "Silencia la alarma, ya la oí.",
            "Descarta esta alarma activa.",
            "Haz que deje de sonar esa alarma.",
            "Detén el aviso que suena ahora.",
            "Ya desperté; silénciala.",
            "Ya oí la alarma; descártala.",
            "Calla la notificación que acaba de sonar.",
        ],
        "spanglish": [
            "Stop la alarma que está ringing.",
            "Silence esa alarma, ya la heard.",
            "I'm awake, para la alarma.",
            "Dismiss la notificación que just went off.",
        ],
    },
    "notification.schedule": {
        "en": [
            "Set a new alarm for seven tomorrow.",
            "Schedule an alarm for next Monday at nine.",
            "Create a reminder for noon today.",
            "Wake me with an alarm at six thirty.",
        ],
        "es": [
            "Pon una alarma nueva mañana a las siete.",
            "Programa una alarma el lunes a las nueve.",
            "Crea un recordatorio para hoy al mediodía.",
            "Despiértame con una alarma a las seis y media.",
        ],
        "spanglish": [
            "Set una alarma nueva para mañana a las seven.",
            "Recuérdame at noon que llame a Ana.",
        ],
    },
    "media.control": {
        "en": [
            "Skip to a different artist.",
            "Change to another artist in the current playback.",
            "Switch artists on what is playing.",
            "Move on from this artist.",
        ],
        "es": [
            "Cambia a otro artista en la reproducción actual.",
            "Pasa a un artista distinto.",
            "Cambia el artista de lo que suena.",
            "Salta a otro artista.",
        ],
        "spanglish": [
            "Switch a otro artista en lo que está playing.",
            "Skip este artist y pasa a otro.",
        ],
    },
    "media.play.query": {
        "en": [
            "Play a live set by Tesla.",
            "Put on a live performance by Tesla.",
            "Find and play Tesla in concert.",
            "Play some live music by Tesla.",
        ],
        "es": [
            "Pon un directo de Tesla.",
            "Reproduce una actuación en vivo de Tesla.",
            "Busca y pon a Tesla en concierto.",
            "Pon música en vivo de Tesla.",
        ],
        "spanglish": [
            "Play un live set de Tesla.",
            "Pon Tesla live en Spotify.",
        ],
    },
}


def build() -> dict[str, Any]:
    catalog = catalog_by_name()
    heldout_texts = {
        normalize_text(str(row["text"]))
        for path in HELDOUTS
        for row in read_jsonl(path)
    }
    r4_source = json.loads(R4.read_text(encoding="utf-8"))
    r4_texts = {
        normalize_text(str(row["text"])) for row in r4_source["samples"]
    }
    rows = []
    seen: set[str] = set()
    for operation, by_language in AUTHORED.items():
        family = operation.split(".", 1)[0]
        tools = selection_tools(
            catalog,
            [*family_operations(catalog, family), NO_ACTION_OPERATION],
        )
        for language, texts in by_language.items():
            for text in texts:
                normalized = normalize_text(text)
                if normalized in heldout_texts or normalized in r4_texts:
                    raise ValueError(f"authored repair overlaps evaluation: {text}")
                key = f"{family}:{normalized}"
                if key in seen:
                    raise ValueError(f"duplicate authored repair: {text}")
                seen.add(key)
                case_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
                rows.append(
                    {
                        "schema": "baxy.functiongemma-selection-row.v1",
                        "case_id": f"r4-repair-{case_hash}",
                        "language": language,
                        "text": text,
                        "operation": operation,
                        "family": family,
                        "source": "core-contract-authored-r4-repair-v1",
                        "tools": tools,
                    }
                )
    write_jsonl(OUTPUT, rows)
    report = {
        "schema": "baxy.functiongemma-r4-repair-seed.v1",
        "scope": "opened_development_repair_not_blind",
        "rows": len(rows),
        "operations": {
            operation: sum(len(texts) for texts in by_language.values())
            for operation, by_language in AUTHORED.items()
        },
        "heldouts": [
            {"path": str(path), "sha256": sha256(path)} for path in HELDOUTS
        ],
        "r4_selected_identity_sha256": r4_source["source"][
            "selected_identity_sha256"
        ],
        "exact_text_overlap": 0,
        "output": str(OUTPUT),
        "output_sha256": sha256(OUTPUT),
        "effects_executed": 0,
    }
    OUTPUT.with_suffix(".report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
