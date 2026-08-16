"""Freeze a second manual situated Cut B, independent of recogniser grammar."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/situated_cut_b_r228.jsonl"
OUTPUT = REPO / "artifacts/holdout/situated_cut_b_r228.preregistration.json"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
PRIOR_SOURCES = (
    REPO / "artifacts/development/independent_cut_b_oracle_r146.jsonl",
    REPO / "artifacts/holdout/generalization_product_current_tree_r28.jsonl",
    REPO / "artifacts/holdout/independent_cut_b_r213.jsonl",
    REPO / "artifacts/holdout/situated_cut_b_r215.jsonl",
    *sorted((REPO / "artifacts/holdout").glob("veto_reach_v*.json*")),
)


CASES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "app": (
        ("app.installed",),
        {
            "es": "Para el dibujo de mi sobrina, ¿ya está disponible Paint sin buscarlo por internet?",
            "en": "For my niece's drawing, is Paint already available without looking online?",
            "spanglish": "Para el drawing de mi niece, ¿Paint ya está available sin buscar online?",
        },
    ),
    "audio": (
        ("audio.status",),
        {
            "es": "La clase suena pero no sé por dónde está saliendo; oriéntame sobre la salida actual.",
            "en": "The class is audible but I do not know where it is coming out; identify the current output.",
            "spanglish": "La class suena pero no sé dónde está coming out; identify la salida actual.",
        },
    ),
    "backup": (
        ("backup.list",),
        {
            "es": "Antes de probar este cambio arriesgado, ¿qué puntos de regreso tengo guardados?",
            "en": "Before trying this risky change, which saved return points do I have?",
            "spanglish": "Before probar este risky change, ¿qué saved return points tengo?",
        },
    ),
    "bluetooth": (
        ("bluetooth.device.list",),
        {
            "es": "Traje unos audífonos y quiero saber qué aparatos inalámbricos hay al alcance.",
            "en": "I brought headphones and want to know which wireless things are within reach.",
            "spanglish": "Traje headphones y quiero know qué wireless things están within reach.",
        },
    ),
    "browser": (
        ("browser.tabs.list",),
        {
            "es": "Dejé varias lecturas para después; recuérdame cuáles páginas siguen esperándome.",
            "en": "I left several readings for later; remind me which pages are still waiting for me.",
            "spanglish": "Dejé several readings para later; remind me qué pages siguen waiting.",
        },
    ),
    "calendar": (
        ("calendar.event.list",),
        {
            "es": "Quieren reunirse el viernes y necesito mirar primero qué ya prometí ese día.",
            "en": "They want to meet on Friday and I need to see what I already promised that day first.",
            "spanglish": "Quieren meet el Friday y necesito see qué already promised ese day.",
        },
    ),
    "capture": (
        ("capture.screenshot",),
        {
            "es": "Este error podría desaparecer; guárdame una prueba visual antes de tocar nada.",
            "en": "This error may disappear; keep visual evidence before I touch anything.",
            "spanglish": "Este error may disappear; keep visual evidence before tocar anything.",
        },
    ),
    "clipboard": (
        ("clipboard.read.text",),
        {
            "es": "Iba a pegar un dato importante y se me fue de la cabeza qué llevaba conmigo.",
            "en": "I was about to paste an important detail and forgot what I was carrying temporarily.",
            "spanglish": "Iba a paste an important detail y forgot qué llevaba temporarily.",
        },
    ),
    "email": (
        ("email.latest.read",),
        {
            "es": "Volví de almorzar y parece que entró algo urgente; revisa la novedad más reciente.",
            "en": "I came back from lunch and something urgent seems to have arrived; inspect the newest item.",
            "spanglish": "Volví from lunch y something urgent seems llegó; inspect la newest item.",
        },
    ),
    "filesystem": (
        ("filesystem.known.search",),
        {
            "es": "Necesito reenviar el presupuesto que guardé hace meses, pero perdí su pista.",
            "en": "I need to forward the budget I saved months ago, but I lost its trail.",
            "spanglish": "Necesito forward el budget que saved months ago, pero lost su trail.",
        },
    ),
    "game": (
        ("game.catalog.list",),
        {
            "es": "Antes de comprar de nuevo, quiero recordar qué biblioteca de juegos ya me pertenece.",
            "en": "Before buying again, I want to recall which game library already belongs to me.",
            "spanglish": "Before buying again, quiero recall qué game library already belongs to me.",
        },
    ),
    "input": (
        ("input.keyboard.status",),
        {
            "es": "Los signos salen cambiados al escribir la contraseña; dime cómo quedó configurado el teclado.",
            "en": "Symbols change while I type the password; tell me how the keyboard ended up configured.",
            "spanglish": "Los symbols change al type la password; tell me cómo quedó configured el keyboard.",
        },
    ),
    "media": (
        ("media.status",),
        {
            "es": "Escucho ruido desde otra pieza; ¿qué quedó reproduciéndose en esta sesión?",
            "en": "I hear noise from another room; what was left playing in this session?",
            "spanglish": "Escucho noise desde another room; what quedó playing en esta session?",
        },
    ),
    "memory": (
        ("memory.status",),
        {
            "es": "Quiero decidir si te cuento una preferencia personal; primero aclárame si tu recuerdo está activo.",
            "en": "I need to decide whether to tell you a personal preference; first clarify whether your memory is active.",
            "spanglish": "Quiero decide si tell you a personal preference; first clarify si your memory está active.",
        },
    ),
    "message": (
        ("message.recipient.resolve",),
        {
            "es": "Voy a escribirle a Daniela Pérez, pero en mis contactos aparecen dos iguales; ayúdame a distinguirla.",
            "en": "I will write Daniela Pérez, but two matching contacts appear; help me distinguish her.",
            "spanglish": "Voy a write Daniela Pérez, but two matching contacts aparecen; help me distinguirla.",
        },
    ),
    "network": (
        ("network.status",),
        {
            "es": "El chat de trabajo dejó de actualizarse; necesito saber si el equipo aún ve la red exterior.",
            "en": "The work chat stopped updating; I need to know whether the computer still sees the outside network.",
            "spanglish": "El work chat stopped updating; necesito know si el computer still sees la outside network.",
        },
    ),
    "note": (
        ("note.list",),
        {
            "es": "Estoy preparando una charla y quiero rescatar las notas que dejé en el equipo.",
            "en": "I am preparing a talk and want to recover the notes I left on this computer.",
            "spanglish": "Estoy preparing a talk y want to recover las notes que left en este computer.",
        },
    ),
    "notification": (
        ("notification.list.due",),
        {
            "es": "No quiero que se me pase nada vencido: ¿qué avisos ya requieren atención?",
            "en": "I do not want overdue things to slip past me: which notices already need attention?",
            "spanglish": "No want overdue things slip past me: ¿qué notices already need attention?",
        },
    ),
    "ocr": (
        ("capture.screenshot", "ocr.read"),
        {
            "es": "El código aparece sólo en esta pantalla y debo anotarlo sin equivocarme.",
            "en": "The code appears only on this screen and I must write it down accurately.",
            "spanglish": "El code appears sólo on this screen y debo write it down accurate.",
        },
    ),
    "office": (
        ("office.document.create",),
        {
            "es": "Mañana entrego una minuta y necesito partir con un documento Word en blanco.",
            "en": "I deliver minutes tomorrow and need to start with a blank Word document.",
            "spanglish": "Mañana deliver minutes y necesito start con a blank Word document.",
        },
    ),
    "package": (
        ("package.install.prepare",),
        {
            "es": "Me compartieron archivos comprimidos; deja preparado 7zip para que pueda autorizarlo después.",
            "en": "I was sent compressed files; prepare 7zip so I can authorize it later.",
            "spanglish": "Me shared compressed files; prepare 7zip so pueda authorize it later.",
        },
    ),
    "peripheral": (
        ("peripheral.list",),
        {
            "es": "Quiero conectar una cámara, pero antes necesito saber qué hardware está viendo el PC.",
            "en": "I want to connect a camera, but first need to know what hardware the PC can see.",
            "spanglish": "Quiero connect a camera, but first need know qué hardware el PC can see.",
        },
    ),
    "reminder": (
        ("reminder.list",),
        {
            "es": "Se me juntaron pendientes y quiero revisar qué dejé marcado para más adelante.",
            "en": "My pending items piled up and I want to review what I marked for later.",
            "spanglish": "Mis pending items piled up y want review qué marked para later.",
        },
    ),
    "routine": (
        ("routine.list",),
        {
            "es": "Estoy ordenando mi automatización y necesito ver las rutinas que aún conservo.",
            "en": "I am organizing my automation and need to see which routines I still keep.",
            "spanglish": "Estoy organizing my automation y need see qué routines still keep.",
        },
    ),
    "streaming": (
        ("streaming.play.named",),
        {
            "es": "Después de cenar quiero poner el episodio 'The Constant' en Netflix.",
            "en": "After dinner I want to put on the episode 'The Constant' on Netflix.",
            "spanglish": "After cenar quiero put on el episode 'The Constant' on Netflix.",
        },
    ),
    "system": (
        ("system.status",),
        {
            "es": "Todo está más lento que de costumbre; necesito una radiografía general del equipo.",
            "en": "Everything is slower than usual; I need a general health picture of the computer.",
            "spanglish": "Todo is slower than usual; necesito a general health picture del computer.",
        },
    ),
    "task": (
        ("task.list",),
        {
            "es": "Antes de salir, quiero saber qué cosas siguen en mi lista de trabajo.",
            "en": "Before I leave, I want to know which things remain on my work list.",
            "spanglish": "Before salir, want know qué things remain en mi work list.",
        },
    ),
    "vision": (
        ("capture.screenshot", "vision.describe"),
        {
            "es": "No alcanzo a reconocer lo que muestra la ventana abierta; necesito una descripción de la escena.",
            "en": "I cannot recognize what the open window shows; I need a description of the scene.",
            "spanglish": "No puedo recognize what la open window shows; necesito a description de la scene.",
        },
    ),
    "web": (
        ("web.search",),
        {
            "es": "Estoy comparando métodos de compostaje y quiero investigar cuál sirve para departamento.",
            "en": "I am comparing composting methods and want to research which works for an apartment.",
            "spanglish": "Estoy comparing composting methods y want research cuál works para an apartment.",
        },
    ),
    "wifi": (
        ("wifi.status",),
        {
            "es": "Desde que me moví al balcón, necesito comprobar si sigo conectado por Wi‑Fi.",
            "en": "Since I moved to the balcony, I need to check whether I remain connected by Wi-Fi.",
            "spanglish": "Since me moved al balcony, necesito check si remain connected by Wi-Fi.",
        },
    ),
    "window": (
        ("window.active",),
        {
            "es": "Antes de pulsar Enter, necesito saber qué aplicación está recibiendo mis teclas.",
            "en": "Before pressing Enter, I need to know which application is receiving my keystrokes.",
            "spanglish": "Before pulsar Enter, need know qué application is receiving mis keystrokes.",
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


def _prior_texts() -> set[str]:
    result: set[str] = set()
    for path in PRIOR_SOURCES:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        try:
            value = json.loads(raw)
            result |= _strings(value)
        except json.JSONDecodeError:
            for line in raw.splitlines():
                if line.strip():
                    result |= _strings(json.loads(line))
    return result


def build_rows() -> list[dict[str, object]]:
    rows = []
    for family, (operations, texts) in CASES.items():
        for language in ("es", "en", "spanglish"):
            rows.append(
                {
                    "schema": "baxy.situated-cut-b.r228.v1",
                    "case_id": f"situated-r228-{family}-{language}",
                    "family": family,
                    "language": language,
                    "text": texts[language],
                    "expected_operations": list(operations),
                    "blind_holdout": True,
                    "execution_authority": False,
                    "oracle_origin": "manual_situated_semantic_specification_independent_of_recogniser",
                }
            )
    texts = [_normalise(str(row["text"])) for row in rows]
    if len(rows) != 93 or len(set(texts)) != 93:
        raise ValueError("r228_requires_93_unique_manual_requests")
    if set(texts) & _prior_texts():
        raise ValueError("r228_text_overlaps_a_consumed_population")
    return rows


def build() -> dict[str, object]:
    rows = build_rows()
    return {
        "schema": "baxy.situated-cut-b.r228-preregistration.v1",
        "authority": "sealed_before_recogniser_or_model_measurement",
        "population": {
            "rows": 93,
            "families": 31,
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "recogniser_majority_limit": 0.5,
        },
        "acceptance": {
            "recogniser_reach_must_be_less_than": 0.5,
            "model_path_requires_separate_preregistration": True,
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
            ],
        },
        "constraints": {
            "generator_imports_recogniser": False,
            "generator_imports_alias_catalogue": False,
            "prior_cut_b_builder_imported": False,
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "corpus_sha256": hashlib.sha256(
                (
                    "\n".join(
                        json.dumps(row, ensure_ascii=False, sort_keys=True)
                        for row in rows
                    )
                    + "\n"
                ).encode("utf-8")
            ).hexdigest(),
            "catalog_sha256": _sha256(CATALOG),
            "prior_sources": {
                str(path.relative_to(REPO)): _sha256(path)
                for path in PRIOR_SOURCES
                if path.is_file()
            },
            "program_sha256": _sha256(Path(__file__)),
        },
    }


def main() -> int:
    if CORPUS.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite R228 holdout")
    rows = build_rows()
    CORPUS.write_bytes(
        (
            "\n".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows
            )
            + "\n"
        ).encode("utf-8")
    )
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
