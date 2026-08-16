"""Seal a contract-missing-information Cut B before recogniser or model use."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CATALOGUE = REPO / "artifacts" / "development" / "current_core_catalog_snapshot_r219.json"
R196 = REPO / "artifacts" / "development" / "r196_full_provenance_classifier_training.jsonl"
R264 = REPO / "artifacts" / "development" / "fresh_independent_cut_b_r264.jsonl"
CORPUS = REPO / "artifacts" / "development" / "independent_clarification_cut_b_r270.jsonl"
PREREGISTRATION = (
    REPO / "artifacts" / "development" / "independent_clarification_cut_b_r270.preregistration.json"
)
SCHEMA = "baxy.independent-clarification-cut-b.r270.v1"


# These are manual requests for a real action whose required fact is absent.
# The text is specified without inspecting recogniser code, aliases, R196, R264,
# or catalogue descriptions. The read-only catalogue validates operation names.
CASES: tuple[dict[str, object], ...] = (
    {
        "case": "app.close",
        "family": "app",
        "operation": "app.close",
        "missing_facts": ("target_application",),
        "texts": {
            "es": "Cierra la aplicación que dejé abierta para ese trabajo.",
            "en": "Close the application I left open for that work.",
            "spanglish": "Close la app que dejé open para ese trabajo.",
        },
    },
    {
        "case": "audio.volume",
        "family": "audio",
        "operation": "audio.volume",
        "missing_facts": ("desired_volume",),
        "texts": {
            "es": "Pon el volumen como lo necesito para la reunión.",
            "en": "Set the volume the way I need it for the meeting.",
            "spanglish": "Setea el volume como lo necesito para la meeting.",
        },
    },
    {
        "case": "backup.restore",
        "family": "backup",
        "operation": "backup.restore",
        "missing_facts": ("backup_identity", "restore_destination"),
        "texts": {
            "es": "Recupera la copia que necesito en el lugar correcto.",
            "en": "Restore the backup I need to the right place.",
            "spanglish": "Restore el backup que necesito al lugar correcto.",
        },
    },
    {
        "case": "bluetooth.device.pair",
        "family": "bluetooth",
        "operation": "bluetooth.device.pair",
        "missing_facts": ("device_identity",),
        "texts": {
            "es": "Empareja mis audífonos Bluetooth.",
            "en": "Pair my Bluetooth headphones.",
            "spanglish": "Pair mis Bluetooth headphones.",
        },
    },
    {
        "case": "browser.navigate",
        "family": "browser",
        "operation": "browser.navigate",
        "missing_facts": ("destination_url",),
        "texts": {
            "es": "Llévame a la página de la empresa.",
            "en": "Take me to the company's webpage.",
            "spanglish": "Llévame al company website.",
        },
    },
    {
        "case": "calendar.event.create",
        "family": "calendar",
        "operation": "calendar.event.create",
        "missing_facts": ("event_time", "event_title"),
        "texts": {
            "es": "Agenda mi cita de seguimiento.",
            "en": "Schedule my follow-up appointment.",
            "spanglish": "Schedule mi follow-up appointment.",
        },
    },
    {
        "case": "capture.active.window",
        "family": "capture",
        "operation": "capture.active.window",
        "missing_facts": ("target_window",),
        "texts": {
            "es": "Captura la ventana que tengo que compartir.",
            "en": "Capture the window I need to share.",
            "spanglish": "Capture la window que necesito share.",
        },
    },
    {
        "case": "clipboard.write.text",
        "family": "clipboard",
        "operation": "clipboard.write.text",
        "missing_facts": ("literal_text",),
        "texts": {
            "es": "Pon ese texto en el portapapeles.",
            "en": "Put that text on the clipboard.",
            "spanglish": "Pon ese text en el clipboard.",
        },
    },
    {
        "case": "email.latest.reply",
        "family": "email",
        "operation": "email.latest.reply",
        "missing_facts": ("reply_body",),
        "texts": {
            "es": "Responde al último correo con lo que acordamos.",
            "en": "Reply to the latest email with what we agreed.",
            "spanglish": "Reply al latest email con lo que acordamos.",
        },
    },
    {
        "case": "filesystem.move",
        "family": "filesystem",
        "operation": "filesystem.move",
        "missing_facts": ("source_file", "destination_path"),
        "texts": {
            "es": "Mueve el archivo que te mostré a la carpeta correcta.",
            "en": "Move the file I showed you to the right folder.",
            "spanglish": "Move el file que te mostré al right folder.",
        },
    },
    {
        "case": "game.install.named",
        "family": "game",
        "operation": "game.install.named",
        "missing_facts": ("game_title",),
        "texts": {
            "es": "Instala el juego que quiero probar.",
            "en": "Install the game I want to try.",
            "spanglish": "Instala el game que quiero try.",
        },
    },
    {
        "case": "input.text.type",
        "family": "input",
        "operation": "input.text.type",
        "missing_facts": ("text_to_type",),
        "texts": {
            "es": "Escribe el mensaje pendiente en la ventana activa.",
            "en": "Type the pending message in the active window.",
            "spanglish": "Type el pending message en la active window.",
        },
    },
    {
        "case": "media.play.query",
        "family": "media",
        "operation": "media.play.query",
        "missing_facts": ("media_query",),
        "texts": {
            "es": "Pon la canción que te mencioné.",
            "en": "Play the song I mentioned.",
            "spanglish": "Play la song que te mencioné.",
        },
    },
    {
        "case": "memory.save",
        "family": "memory",
        "operation": "memory.save",
        "missing_facts": ("memory_content",),
        "texts": {
            "es": "Guarda el dato importante que acabo de contar.",
            "en": "Save the important detail I just told you.",
            "spanglish": "Save el important detail que te acabo de contar.",
        },
    },
    {
        "case": "message.send",
        "family": "message",
        "operation": "message.send",
        "missing_facts": ("recipient", "message_body"),
        "texts": {
            "es": "Manda el aviso a la persona del equipo.",
            "en": "Send the update to the person on the team.",
            "spanglish": "Send el update a la person del team.",
        },
    },
    {
        "case": "network.ping",
        "family": "network",
        "operation": "network.ping",
        "missing_facts": ("host",),
        "texts": {
            "es": "Comprueba si el servidor responde.",
            "en": "Check whether the server responds.",
            "spanglish": "Checkea si el server responde.",
        },
    },
    {
        "case": "note.create",
        "family": "note",
        "operation": "note.create",
        "missing_facts": ("note_title", "note_content"),
        "texts": {
            "es": "Crea una nota con lo que acordamos.",
            "en": "Create a note with what we agreed.",
            "spanglish": "Create una note con lo que agreed.",
        },
    },
    {
        "case": "notification.schedule",
        "family": "notification",
        "operation": "notification.schedule",
        "missing_facts": ("schedule_time",),
        "texts": {
            "es": "Programa la alarma para después.",
            "en": "Set the alarm for later.",
            "spanglish": "Setea la alarm para later.",
        },
    },
    {
        "case": "ocr.read",
        "family": "ocr",
        "operation": "ocr.read",
        "missing_facts": ("capture_identity",),
        "texts": {
            "es": "Lee el texto de la imagen que te envié.",
            "en": "Read the text in the image I sent you.",
            "spanglish": "Read el text de la image que te envié.",
        },
    },
    {
        "case": "office.word.append",
        "family": "office",
        "operation": "office.word.append",
        "missing_facts": ("text_to_append",),
        "texts": {
            "es": "Añade el párrafo final al Word que está abierto.",
            "en": "Append the final paragraph to the open Word document.",
            "spanglish": "Append el final paragraph al Word document open.",
        },
    },
    {
        "case": "package.install.prepare",
        "family": "package",
        "operation": "package.install.prepare",
        "missing_facts": ("package_identifier",),
        "texts": {
            "es": "Prepara la instalación del programa que necesito.",
            "en": "Prepare the program I need for installation.",
            "spanglish": "Prepare el program que necesito para installation.",
        },
    },
    {
        "case": "peripheral.print",
        "family": "peripheral",
        "operation": "peripheral.print",
        "missing_facts": ("target_document",),
        "texts": {
            "es": "Imprime el archivo que ya revisamos.",
            "en": "Print the file we already reviewed.",
            "spanglish": "Print el file que ya reviewed.",
        },
    },
    {
        "case": "reminder.create",
        "family": "reminder",
        "operation": "reminder.create",
        "missing_facts": ("reminder_content", "reminder_time"),
        "texts": {
            "es": "Recuérdame esto más tarde.",
            "en": "Remind me about this later.",
            "spanglish": "Remind me esto later.",
        },
    },
    {
        "case": "routine.phrase.create",
        "family": "routine",
        "operation": "routine.phrase.create",
        "missing_facts": ("routine_phrase", "routine_steps"),
        "texts": {
            "es": "Crea mi rutina de mañana.",
            "en": "Create my morning routine.",
            "spanglish": "Create mi morning routine.",
        },
    },
    {
        "case": "streaming.play.named",
        "family": "streaming",
        "operation": "streaming.play.named",
        "missing_facts": ("video_title",),
        "texts": {
            "es": "Pon el video que me recomendaste.",
            "en": "Play the video you recommended.",
            "spanglish": "Play el video que me recommended.",
        },
    },
    {
        "case": "system.settings.set",
        "family": "system",
        "operation": "system.settings.set",
        "missing_facts": ("setting", "desired_value"),
        "texts": {
            "es": "Ajusta la configuración de pantalla como necesito.",
            "en": "Set the display setting the way I need it.",
            "spanglish": "Setea el display setting como lo necesito.",
        },
    },
    {
        "case": "task.create",
        "family": "task",
        "operation": "task.create",
        "missing_facts": ("task_title",),
        "texts": {
            "es": "Anota la tarea que tenemos pendiente.",
            "en": "Add the task we still have pending.",
            "spanglish": "Add la task que tenemos pending.",
        },
    },
    {
        "case": "vision.describe",
        "family": "vision",
        "operation": "vision.describe",
        "missing_facts": ("capture_identity",),
        "texts": {
            "es": "Descríbeme la captura que quiero revisar.",
            "en": "Describe the capture I want to review.",
            "spanglish": "Describe la capture que quiero review.",
        },
    },
    {
        "case": "web.search",
        "family": "web",
        "operation": "web.search",
        "missing_facts": ("search_query",),
        "texts": {
            "es": "Busca lo que necesito para la reunión.",
            "en": "Search for what I need for the meeting.",
            "spanglish": "Search lo que necesito para la meeting.",
        },
    },
    {
        "case": "wifi.connect.named",
        "family": "wifi",
        "operation": "wifi.connect.named",
        "missing_facts": ("profile_name",),
        "texts": {
            "es": "Conecta el Wi-Fi que usaba antes.",
            "en": "Connect the Wi-Fi network I used before.",
            "spanglish": "Connect el Wi-Fi que usaba before.",
        },
    },
    {
        "case": "window.minimize",
        "family": "window",
        "operation": "window.minimize",
        "missing_facts": ("target_window",),
        "texts": {
            "es": "Minimiza la ventana que no necesito ver.",
            "en": "Minimize the window I do not need to see.",
            "spanglish": "Minimize la window que no necesito see.",
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
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return {
        str(capability["name"])
        for capability in catalogue["catalogue"]["capabilities"]
    }


def _normalised_texts(path: Path) -> set[str]:
    return {
        normalise(str(json.loads(line)["text"]))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    }


def build_rows() -> list[dict[str, Any]]:
    if not all(path.is_file() for path in (CATALOGUE, R196, R264)):
        raise RuntimeError("R270 requires R219, R196 provenance, and sealed R264")
    catalogue_operations = current_catalogue_operations()
    rows: list[dict[str, Any]] = []
    for case in CASES:
        texts = case["texts"]
        if (
            not isinstance(texts, dict)
            or set(texts) != {"es", "en", "spanglish"}
            or not isinstance(case["operation"], str)
            or case["operation"] not in catalogue_operations
            or not isinstance(case["missing_facts"], tuple)
            or not case["missing_facts"]
        ):
            raise RuntimeError(f"R270 case contract failed for {case['case']}")
        for language, text in sorted(texts.items()):
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError(f"R270 text contract failed for {case['case']}")
            rows.append(
                {
                    "schema": SCHEMA,
                    "case_id": f"clarification-r270-{case['case']}-{language}",
                    "family": case["family"],
                    "language": language,
                    "text": text,
                    "intended_operations": [case["operation"]],
                    "missing_facts": list(case["missing_facts"]),
                    "expected_turn_kind": "clarify",
                    "expected_effect_operations": [],
                    "blind_holdout": True,
                    "execution_authority": False,
                    "oracle_origin": "manual_contract_missing_fact_specification_independent_of_recogniser_and_prior_cut_b_language",
                }
            )
    normalised = [normalise(str(row["text"])) for row in rows]
    expected_families = {operation.split(".", 1)[0] for operation in catalogue_operations}
    if (
        len(rows) != 93
        or len(set(normalised)) != len(rows)
        or {str(row["family"]) for row in rows} != expected_families
        or {str(row["expected_turn_kind"]) for row in rows} != {"clarify"}
        or any(row["expected_effect_operations"] for row in rows)
    ):
        raise RuntimeError("R270 requires 31-family clarification-only coverage")
    reused = set(normalised) & (_normalised_texts(R196) | _normalised_texts(R264))
    if reused:
        raise RuntimeError("R270 text overlaps R196 or sealed R264")
    return rows


def corpus_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )


def build() -> dict[str, object]:
    rows = build_rows()
    return {
        "schema": "baxy.independent-clarification-cut-b.r270-preregistration.v1",
        "authority": "sealed_before_recogniser_or_model_measurement",
        "population": {
            "rows": len(rows),
            "semantic_cases": len(CASES),
            "families": 31,
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "expected_turn_kind": "clarify",
            "expected_effect_operations": 0,
        },
        "independence": {
            "generator_imports_recogniser": False,
            "generator_imports_alias_catalogue": False,
            "generator_imports_prior_cut_b_builder": False,
            "generator_uses_r196_or_r264_language": False,
            "generator_uses_current_catalogue_descriptions": False,
            "manual_contract_missing_fact_specification": True,
        },
        "measurement_contract": {
            "first_measurement": "A separately sealed, one-pass read-only recogniser scorer must report any deterministic effect resolution before a model-path candidate is designed.",
            "recogniser_effect_reach_limit": 0.5,
            "later_model_success": "The model must ask a question that obtains at least one listed missing fact while producing zero effects; intent, retrieval, decision, veto, visible-text and latency evidence remain separate requirements.",
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
            ],
            "cannot_refute": "This preregistration alone cannot establish model-path success, OOS behaviour, real provider effects, or latency.",
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
            "catalogue_sha256": sha256(CATALOGUE),
            "r196_sha256": sha256(R196),
            "r264_corpus_sha256": sha256(R264),
            "corpus_sha256": hashlib.sha256(corpus_bytes(rows)).hexdigest(),
            "program_sha256": sha256(Path(__file__)),
        },
        "next_step": "Commit this preregistration unchanged, then preregister one read-only recogniser-effect-reach measurement before designing a model-path candidate.",
    }


def main() -> int:
    if CORPUS.exists() or PREREGISTRATION.exists():
        raise RuntimeError("R270 output already exists; refusing to reseal the population")
    rows = build_rows()
    CORPUS.write_bytes(corpus_bytes(rows))
    PREREGISTRATION.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
