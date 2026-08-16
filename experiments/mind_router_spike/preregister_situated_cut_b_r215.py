"""Freeze a situated, indirect Cut-B population outside recogniser phrasing.

R213 was textually new yet its conventional task descriptions still let the
deterministic recogniser resolve 52/93 rows.  R215 changes the source method,
not R213: each request is a situated information need or indirect speech act.
Generation never imports the recogniser, aliases, or a prior Cut-B builder.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/situated_cut_b_r215.jsonl"
PREREGISTRATION = REPO / "artifacts/holdout/situated_cut_b_r215.preregistration.json"
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
PRIOR_SOURCES = (
    REPO / "artifacts/development/independent_cut_b_oracle_r146.jsonl",
    REPO / "artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json",
    REPO / "artifacts/holdout/generalization_product_current_tree_r28.jsonl",
    REPO / "artifacts/holdout/independent_cut_b_r213.jsonl",
    REPO / "artifacts/audit/independent_cut_b_r213_recogniser_reach_r214.json",
    *sorted((REPO / "artifacts/holdout").glob("veto_reach_v*.json*")),
)


CASES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "app": (
        ("app.installed",),
        {
            "es": "Antes de seguir con el informe, necesito saber si Paint ya viene en este equipo.",
            "en": "Before continuing my report, I need to know whether Paint already comes with this machine.",
            "spanglish": "Antes de seguir con my report, necesito saber if Paint already comes with esta machine.",
        },
    ),
    "audio": (
        ("audio.status",),
        {
            "es": "No escucho la reunión; ¿por qué aparato está saliendo lo que reproduce el PC?",
            "en": "I cannot hear the meeting; which device is carrying what the PC plays?",
            "spanglish": "No escucho la meeting; ¿qué device está carrying lo que el PC plays?",
        },
    ),
    "backup": (
        ("backup.list",),
        {
            "es": "Si se perdiera mi trabajo hoy, ¿qué versiones anteriores podría recuperar?",
            "en": "If my work disappeared today, which earlier versions could I recover?",
            "spanglish": "If mi work disappeared hoy, ¿qué earlier versions podría recover?",
        },
    ),
    "bluetooth": (
        ("bluetooth.device.list",),
        {
            "es": "Quiero emparejar algo después; ¿qué cosas cercanas alcanza a detectar Bluetooth?",
            "en": "I may pair something later; what nearby things can Bluetooth detect?",
            "spanglish": "Maybe pair algo later; ¿qué nearby things puede Bluetooth detect?",
        },
    ),
    "browser": (
        ("browser.tabs.list",),
        {
            "es": "Perdí el hilo de mi investigación: ¿en qué sitios web la dejé abierta?",
            "en": "I lost track of my research: which websites did I leave open?",
            "spanglish": "Perdí track de mi research: ¿qué websites dejé open?",
        },
    ),
    "calendar": (
        ("calendar.event.list",),
        {
            "es": "Antes de aceptar otra invitación, ¿qué compromisos tengo mañana?",
            "en": "Before accepting another invitation, what commitments do I have tomorrow?",
            "spanglish": "Before aceptar another invitation, ¿qué commitments tengo tomorrow?",
        },
    ),
    "capture": (
        ("capture.screenshot",),
        {
            "es": "Necesito dejar constancia de cómo se ve esto antes de cambiar nada.",
            "en": "I need a record of how this looks before changing anything.",
            "spanglish": "Necesito a record de cómo se ve esto before changing anything.",
        },
    ),
    "clipboard": (
        ("clipboard.read.text",),
        {
            "es": "Iba a insertar algo y olvidé qué había guardado temporalmente.",
            "en": "I was about to insert something and forgot what I kept temporarily.",
            "spanglish": "Iba a insert algo y forgot qué había kept temporarily.",
        },
    ),
    "email": (
        ("email.latest.read",),
        {
            "es": "Llegó algo mientras estaba fuera; cuéntame de qué trata lo último que entró.",
            "en": "Something arrived while I was away; tell me what the latest arrival says.",
            "spanglish": "Something llegó mientras estaba away; dime qué says the latest arrival.",
        },
    ),
    "filesystem": (
        ("filesystem.known.search",),
        {
            "es": "Tengo que adjuntar cuentas de marzo y no recuerdo dónde las dejé en Documentos.",
            "en": "I need to attach March accounts and cannot remember where I left them in Documents.",
            "spanglish": "Necesito attach March accounts y no remember dónde las dejé en Documents.",
        },
    ),
    "game": (
        ("game.catalog.list",),
        {
            "es": "Estoy eligiendo qué jugar; ¿cuáles títulos son realmente míos en Steam?",
            "en": "I am choosing what to play; which titles do I actually own in Steam?",
            "spanglish": "Estoy choosing qué play; ¿qué titles realmente own en Steam?",
        },
    ),
    "input": (
        ("input.keyboard.status",),
        {
            "es": "Las teclas escriben raro; necesito saber qué distribución está tomando el sistema.",
            "en": "The keys type strangely; I need to know which layout the system has taken.",
            "spanglish": "Las keys type raro; necesito know qué layout tomó el system.",
        },
    ),
    "media": (
        ("media.status",),
        {
            "es": "Alguien dejó algo reproduciéndose; ¿qué contenido está ocupando ahora la sesión multimedia?",
            "en": "Someone left something playing; what content is occupying the media session now?",
            "spanglish": "Someone dejó something playing; ¿qué content está occupying la media session now?",
        },
    ),
    "memory": (
        ("memory.status",),
        {
            "es": "Antes de confiarte algo, quiero asegurarme de que tu recuerdo privado está disponible aquí.",
            "en": "Before trusting you with something, I want to make sure your private recollection is available here.",
            "spanglish": "Before confiarte algo, quiero make sure your private recollection está available aquí.",
        },
    ),
    "message": (
        ("message.recipient.resolve",),
        {
            "es": "Hay varias Sofía Rojas y no quiero confundir a la persona guardada correcta.",
            "en": "There are several Sofia Rojas entries and I do not want to confuse the right saved person.",
            "spanglish": "Hay several Sofía Rojas entries y no want confundir la right saved person.",
        },
    ),
    "network": (
        ("network.status",),
        {
            "es": "La página no carga y necesito saber si este equipo todavía tiene salida hacia afuera.",
            "en": "The page will not load and I need to know whether this machine still reaches outside.",
            "spanglish": "La page no load y necesito know si esta machine still reaches outside.",
        },
    ),
    "note": (
        ("note.list",),
        {
            "es": "Quiero retomar una idea vieja: ¿qué apuntes míos siguen guardados localmente?",
            "en": "I want to resume an old idea: which of my jottings are still saved locally?",
            "spanglish": "Quiero resume an old idea: ¿qué jottings míos siguen saved locally?",
        },
    ),
    "notification": (
        ("notification.list.due",),
        {
            "es": "Temo haber pasado por alto avisos cuyo momento ya llegó.",
            "en": "I fear I missed notices whose time has already arrived.",
            "spanglish": "I fear que missed notices cuyo time already arrived.",
        },
    ),
    "ocr": (
        ("capture.screenshot", "ocr.read"),
        {
            "es": "No puedo copiar esas letras de la pantalla; necesito tenerlas escritas.",
            "en": "I cannot copy those letters from the display; I need them written down.",
            "spanglish": "No puedo copy esas letters del display; necesito have them written down.",
        },
    ),
    "office": (
        ("office.document.create",),
        {
            "es": "Me pidieron un informe de julio en Word y quiero partir con el archivo listo.",
            "en": "I was asked for a July report in Word and want the file ready to begin.",
            "spanglish": "Me pidieron a July report en Word y want el file ready to begin.",
        },
    ),
    "package": (
        ("package.install.prepare",),
        {
            "es": "Antes de dar permiso, quiero dejar encaminado 7zip.7zip para revisarlo.",
            "en": "Before giving permission, I want 7zip.7zip ready for me to review.",
            "spanglish": "Before dar permiso, quiero 7zip.7zip ready para review.",
        },
    ),
    "peripheral": (
        ("peripheral.list",),
        {
            "es": "Voy a usar un accesorio, pero primero necesito saber qué reconoce físicamente esta torre.",
            "en": "I will use an accessory, but first need to know what this tower physically recognizes.",
            "spanglish": "Voy a use an accessory, but first need know qué this tower physically recognizes.",
        },
    ),
    "reminder": (
        ("reminder.list",),
        {
            "es": "Estoy organizando la semana y no quiero olvidar lo que dejé para después.",
            "en": "I am organizing the week and do not want to forget what I left for later.",
            "spanglish": "Estoy organizing the week y no want olvidar what dejé for later.",
        },
    ),
    "routine": (
        ("routine.list",),
        {
            "es": "Quiero revisar las secuencias repetibles que alguna vez dejé preparadas.",
            "en": "I want to review the repeatable sequences I once set up.",
            "spanglish": "Quiero review las repeatable sequences que once set up.",
        },
    ),
    "streaming": (
        ("streaming.play.named",),
        {
            "es": "Para desconectarme un rato, me gustaría ver Arrival en Netflix.",
            "en": "To switch off for a while, I would like to watch Arrival on Netflix.",
            "spanglish": "Para switch off un rato, me gustaría watch Arrival on Netflix.",
        },
    ),
    "system": (
        ("system.status",),
        {
            "es": "El computador se siente pesado y necesito una visión general de cómo está.",
            "en": "The computer feels sluggish and I need an overall view of how it is doing.",
            "spanglish": "El computer feels sluggish y necesito an overall view de how it is doing.",
        },
    ),
    "task": (
        ("task.list",),
        {
            "es": "Antes de terminar el día, necesito saber qué obligaciones me siguen esperando.",
            "en": "Before ending the day, I need to know which obligations still await me.",
            "spanglish": "Before terminar el día, necesito know qué obligations still await me.",
        },
    ),
    "vision": (
        ("capture.screenshot", "vision.describe"),
        {
            "es": "No alcanzo a interpretar lo que aparece delante de mí; descríbeme la escena del monitor.",
            "en": "I cannot interpret what is in front of me; describe the scene on the monitor.",
            "spanglish": "No puedo interpret what is in front of me; describe la scene on the monitor.",
        },
    ),
    "web": (
        ("web.search",),
        {
            "es": "Estoy preparando un cultivo y necesito informarme sobre hidroponía.",
            "en": "I am preparing a crop and need to learn about hydroponics.",
            "spanglish": "Estoy preparing a crop y need to learn sobre hydroponics.",
        },
    ),
    "wifi": (
        ("wifi.status",),
        {
            "es": "Me cambié de habitación y quiero comprobar si sigo unido al inalámbrico.",
            "en": "I changed rooms and want to check whether I remain joined wirelessly.",
            "spanglish": "Me moved rooms y want to check si remain joined wireless.",
        },
    ),
    "window": (
        ("window.active",),
        {
            "es": "No sé dónde caerán mis próximas teclas; ¿qué programa tiene mi atención ahora?",
            "en": "I do not know where my next keystrokes will land; which program has my attention now?",
            "spanglish": "No sé where my next keystrokes land; ¿qué program has my attention now?",
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
    result: set[str] = set()
    for source in PRIOR_SOURCES:
        if source.suffix == ".jsonl":
            for line in source.read_text(encoding="utf-8").splitlines():
                if line:
                    result.update(_strings(json.loads(line)))
        else:
            result.update(_strings(json.loads(source.read_text(encoding="utf-8"))))
    return result


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for family, (operations, translations) in sorted(CASES.items()):
        if set(translations) != {"es", "en", "spanglish"}:
            raise ValueError(f"r215_language_coverage:{family}")
        for language, text in sorted(translations.items()):
            rows.append(
                {
                    "schema": "baxy.situated-cut-b.r215.v1",
                    "case_id": f"situated-r215-{family}-{language}",
                    "family": family,
                    "language": language,
                    "text": text,
                    "expected_operations": list(operations),
                    "blind_holdout": True,
                    "execution_authority": False,
                    "oracle_origin": "manual_situated_semantic_specification_independent_of_recogniser",
                }
            )
    normalised = [_normalise(row["text"]) for row in rows]
    if len(rows) != 93 or len(set(normalised)) != len(rows):
        raise ValueError("r215_unique_rows_contract")
    if set(normalised) & _prior_normalised_texts():
        raise ValueError("r215_textual_overlap")
    return rows


def build() -> dict[str, Any]:
    rows = build_rows()
    encoded = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )
    return {
        "schema": "baxy.situated-cut-b.r215-preregistration.v1",
        "authority": "sealed_before_recogniser_or_model_measurement",
        "population": {
            "rows": 93,
            "families": 31,
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
            "corpus_sha256": hashlib.sha256(encoded).hexdigest(),
            "prior_sources": {
                source.relative_to(REPO).as_posix(): _sha256(source)
                for source in PRIOR_SOURCES
            },
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
