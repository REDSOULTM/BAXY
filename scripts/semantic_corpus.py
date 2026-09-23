"""Fase 3.5 corpus by layers: what was said to BAXY, in Spanish or English, with the expected reading.

Layers (META_SEMANTICA_TOTAL_2026-09-22.md):

A  real use: ``observed_user`` rows of the historical corpus said to a BAXY (not to the coding agents), the 742
   survey literals, and the user turns of BAXY Definitivo's private conversation logs.
B  inherited curation: the other origins (documents, acceptance examples, tests) that are not synthetic.
C  synthetic router corpora: FunctionGemma router/train_v3, the Gemma 4 router corpus, Carter's benches.

Two filters come first, both reproducible and published with their counts:

language   every text is re-labelled with ``wordfreq`` (not the old label): each word votes for the language
           where it is clearly most frequent among es, en and the neighbours that confuse them (pt, it, fr, de,
           ca, nl, ro); non-Latin script, no words or a majority of other languages is out. Spanish, English and
           their mix stay.
addressee  only what was said to BAXY: agent sessions (``codex/*`` sources), the ``engineering_instruction`` and
           ``product_requirement`` classes, harness markup and code are out.

Every row kept carries the oracle of ``historical_message_mapping.jsonl`` projected on the current catalog
(``FAMILY_OF``): ``expect`` is ``conversation``, ``effect`` (with the old families) or ``limit``; trace-only rows
are not an acceptance commitment and are out. Everything written here is private: it goes to
``%LOCALAPPDATA%\\BAXY\\semantic-corpus-v1`` and never into git; the repository gets the counts.

usage:
  semantic_corpus.py build
  semantic_corpus.py sample [--size 1000]
  semantic_corpus.py score DECISIONS.jsonl [--survey-reference LIT.jsonl] [--json OUT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
DATA = REPO / "tests" / "data"
OUT = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "BAXY" / "semantic-corpus-v1"
REGISTRY = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "BAXY" / "C03-survey-requirements336-private" / "requirements.jsonl"
REAL_LOGS = (pathlib.Path(r"D:\BAXY-traspaso-2026-09-21\private-logs\conversation.v1.jsonl"),)

TARGET = ("es", "en")
NEIGHBOURS = ("pt", "it", "fr", "de", "ca", "nl", "ro")
SYNTHETIC_SOURCES = (
    "functiongemma/router/",
    "functiongemma/finetune_llm/",
    "probando_gemma4/gemma4_agent/data/router_corpus",
    "carter_os_ai/carter_v5/audit/",
    "carter_os_ai/legacy/",
)
MARKUP = re.compile(
    r"<task-notification>|<codex_internal_context|<heartbeat>|<command-message>|# Context from my IDE|"
    r"```|<[a-z_-]+>|\btool-use-id\b"
)
CODE = re.compile(
    r"(?:\bdef \w+\(|\bimport \w|\breturn \w|=>|\w+\(\)|\{[^}]*\}|\bpytest\b|\bgit (?:commit|push|pull)\b|"
    r"\.(?:py|cs|ts|tsx|json|md|ps1)\b|\bsrc/|\bnpm\b)"
)
# Documentation fragments are notes about BAXY, not things said to it: metrics with units, bold markers,
# code identifiers («system.shutdown/restart», «restore_backup»), verdict words.
TECHNICAL = re.compile(
    r"\*\*|\b\d+(?:[.,]\d+)?\s?(?:ms|mib|gib|mb|gb|kb|s)\b|\b[a-z]+_[a-z_]+\b|\b[a-z]+\.[a-z]+(?:\.[a-z]+)*\b|"
    r"\b(?:PASS|FAIL|WER|p50|p95|VRAM|KV|mmproj|handle|flag|router|routing|parsers?|dataset|fine-?tun\w*|bench\w*)\b"
)
_WRAPPING_QUOTES = "«»\"“”„'‘’`"
AGENT_WORDS = re.compile(
    r"\b(?:codex|claude|opus|sonnet|gpt|fable|el agente|al agente|refactor\w*|commit\w*|implementa\w*|"
    r"el repo\b|la rama|goal\b|prompt\b|el c[oó]digo|tests?\b|debug\w*)",
    re.IGNORECASE,
)


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def language_of(text: str) -> str:
    """es, en, mixed, other, unknown (Latin words no dictionary knows) or noise, voted word by word."""

    import wordfreq

    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "noise"
    latin = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
    if latin / len(letters) < 0.7:
        return "other"
    words = re.findall(r"[^\W\d_]+", text.casefold())
    votes: Counter[str] = Counter()
    for word in words[:80]:
        es = wordfreq.zipf_frequency(word, "es")
        en = wordfreq.zipf_frequency(word, "en")
        neighbour = max(wordfreq.zipf_frequency(word, lang) for lang in NEIGHBOURS)
        if max(es, en, neighbour) <= 0:
            continue  # names, typos: no vote
        if max(es, en) >= neighbour - 0.3:
            # A word shared by several languages («no», «app», «ok») is compatible with the target.
            votes["es" if es >= en + 0.5 else "en" if en >= es + 0.5 else "shared"] += 1
        else:
            votes["other"] += 1
    es, en = votes["es"], votes["en"]
    other = sum(count for lang, count in votes.items() if lang not in {"es", "en", "shared"})
    if es + en + votes["shared"] == 0:
        return "other" if other else "unknown"
    if other > es + en + votes["shared"]:
        return "other"
    if es and en and min(es, en) / max(es, en) >= 0.25:
        return "mixed"
    if es >= en:
        return "es" if es or not en else "en"
    return "en"


# Speech-act opening of a turn said to an assistant (DECISIONES §12). Written for the corpus, independent
# of the product's readers on purpose: BAXY is not measured with its own grammar.
_SPEECH_VOCATIVE = r"(?:(?:baxy|carter|oye|oiga|che|hey|hola|bueno|ok|okay|dale|porfa|por\s+favor|please|y|ahora|entonces)[\s,.!]+)*"
_SPEECH_QUESTION = (
    r"(?:[¿?]|que|quien|quienes|como|cual|cuales|cuando|donde|adonde|por\s*que|cuanto|cuanta|cuantos|cuantas|"
    r"hay|tengo|tenes|tienes|sabes|sabias|puedes|podes|podrias|puede|what|who|how|which|when|where|why|"
    r"is|are|do|does|did|can|could|would|will|should|have|has)\b"
)
_SPEECH_REQUEST = (
    r"(?:quiero|quisiera|necesito|me\s+gustaria|ayudame|ayudarme|dame|decime|dime|contame|cuentame|mostrame|"
    r"muestrame|i\s+want|i\s+need|i'd\s+like|let's|lets|gracias|thanks|thank\s+you|perdon|sorry|buenas|buenos|"
    r"hola|hello|hi|chao|chau|adios|bye)\b"
)
_SPEECH_IMPERATIVE = (
    r"(?:abr[ie]\w*|abre\w*|cerr?a\w*|cierr?a\w*|pon\w*|pone\w*|busc\w*|reproduc\w*|toca\w*|sub[ei]\w*|baj[ae]\w*|"
    r"apag\w*|prend\w*|enciend\w*|silenci\w*|mut\w*|activ\w*|desactiv\w*|manda\w*|envi\w*|escrib\w*|crea\w*|"
    r"guard\w*|borr\w*|elimin\w*|instal\w*|desinstal\w*|descarg\w*|copi\w*|peg\w*|mov\w*|renombr\w*|lanz\w*|"
    r"inici\w*|ejecut\w*|jug\w*|jueg\w*|mir\w*|ve|anda|entra\w*|naveg\w*|muestr\w*|lee\w*|le[ei]\w*|resum\w*|"
    r"traduc\w*|calcul\w*|recuerd\w*|record\w*|avis\w*|agend\w*|program\w*|configur\w*|conect\w*|desconect\w*|"
    r"minimiz\w*|maximiz\w*|restaur\w*|cambi\w*|haz|hace\w*|hacelo|saca\w*|toma\w*|captur\w*|investig\w*|"
    r"averigu\w*|fija\w*|revis\w*|chequea\w*|explic\w*|llam\w*|contest\w*|respond\w*|par[ae]|pausa\w*|"
    r"segu\w*|sigue\w*|salt\w*|repet\w*|repit\w*|actualiz\w*|reinici\w*|suspend\w*|bloque\w*|"
    r"open|close|play|pause|stop|search|find|show|tell|turn|set|send|write|create|delete|remove|install|"
    r"uninstall|download|copy|paste|move|rename|launch|start|run|take|read|summarize|translate|remind|mute|"
    r"unmute|minimize|maximize|restore|lock|restart|shut|go|look|check|call|reply|skip|type|click|save|put|"
    r"make|give|help|list|switch|change|increase|decrease|lower|raise)"
)
_SPEECH_TECHNICAL = re.compile(
    r"[`*→=<>#|]|\b\d+\s*[x×/]\s*\d+|\b\d+(?:[.,]\d+)?\s*(?:mb|gb|ms|tok|tokens)\b|"
    r"\b(?:bug|issue|regex|cache|runtime|runtimes|backend|prefill|offload|vram|llm|stt|tts|json|sqlite|uia|"
    r"roi|pattern|payload|handoff|fallback|pipeline|benchmark|dataset|finetune|gemma\d*|qwen|whisper|onnx|"
    r"cuda|directml|false_pass|r\d{1,2})\b",
    re.IGNORECASE,
)


def speech_act_of(text: str) -> str | None:
    """None when the text has the form of a turn said to an assistant; otherwise why not.

    A turn opens (after a vocative or a filler) with a question, a request or an imperative verb, and
    carries no technical notation. A document's acceptance criterion or note («OCR PaddleOCR crop
    600×200», «Offload parcial CPU+GPU», «monitoreo de GPU») is not a turn, whatever family it names.
    """

    folded = unicodedata.normalize("NFKD", str(text).casefold())
    folded = " ".join("".join(ch for ch in folded if not unicodedata.combining(ch)).split())
    if _SPEECH_TECHNICAL.search(folded):
        return "technical_notation"
    opening = re.match(
        rf"^[¡!\s\"'“«-]*{_SPEECH_VOCATIVE}(?:{_SPEECH_QUESTION}|{_SPEECH_REQUEST}|{_SPEECH_IMPERATIVE}\b)",
        folded,
    )
    return None if opening is not None else "not_a_turn"


def addressee_of(row: dict[str, Any]) -> str | None:
    """None when the text was said to BAXY; otherwise why it was not."""

    text = str(row.get("text_literal") or "")
    source = str(row.get("source") or "")
    if source.startswith("codex/"):
        return "agent_session"
    if row.get("class") in {"engineering_instruction", "product_requirement"}:
        return "class_" + str(row["class"])
    if MARKUP.search(text):
        return "harness_markup"
    if CODE.search(text):
        return "code"
    if AGENT_WORDS.search(text) and len(text.split()) > 12:
        return "agent_talk"
    if row.get("origin") != "observed_user" and TECHNICAL.search(text):
        return "technical_note"
    if layer_of(row) == "B":
        # DECISIONES §12: a document's example is a turn only in the form of one; acceptance
        # criteria and notes are not. Layer C is phrases said to assistants and keeps its rows.
        reason = speech_act_of(clean(text))
        if reason is not None:
            return "document_" + reason
    return None


def clean(text: str) -> str:
    """The utterance as said: documents quote their examples («sube el volumen», "Baxy, pon música”.)."""
    text = " ".join(str(text).split())
    for _ in range(2):
        stripped = text.strip().strip(_WRAPPING_QUOTES).strip()
        stripped = re.sub(r"[" + re.escape(_WRAPPING_QUOTES) + r"]+([.!?]?)$", r"\1", stripped).strip()
        stripped = re.sub(r"^[" + re.escape(_WRAPPING_QUOTES) + r"]+", "", stripped).strip()
        if stripped == text:
            break
        text = stripped
    return text


def layer_of(row: dict[str, Any]) -> str:
    source = str(row.get("source") or "")
    if row.get("origin") == "observed_user":
        return "A"
    if any(source.startswith(prefix) for prefix in SYNTHETIC_SOURCES):
        return "C"
    return "B"


def expect_of(mapping: dict[str, Any]) -> tuple[str | None, list[str]]:
    outcome = mapping.get("outcome_type")
    families = list(mapping.get("operations") or [])
    if outcome == "conversation_no_tool":
        return "conversation", []
    if outcome in {"mission_must_implement", "risk_or_external_dependency_flow"} and families:
        return "effect", families
    if outcome == "safe_refusal":
        return "limit", []
    return None, families


# The oracle speaks the consolidated catalog of goal 03 (43 families); the product serves 204 operations.
# Each current operation satisfies the families below. Public and reviewable on purpose.
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("media.play.", ("media.play",)),
    ("streaming.play.named", ("media.play", "streaming.navigate")),
    ("streaming.navigate", ("streaming.navigate", "media.play")),
    ("media.", ("media.control",)),
    ("audio.microphone.mute", ("audio.mute",)),
    ("audio.mute", ("audio.mute",)),
    ("audio.status", ("audio.status", "audio.volume")),
    ("audio.", ("audio.volume",)),
    ("app.open", ("app.open",)),
    ("app.close", ("app.close",)),
    ("window.close.all", ("app.close", "window.manage")),
    ("system.process.terminate.named", ("app.close",)),
    ("window.", ("window.manage",)),
    ("input.", ("window.manage",)),
    ("web.download", ("filesystem.transfer", "web.search")),
    ("web.", ("web.search",)),
    ("weather.current", ("web.search",)),
    ("browser.", ("browser.navigate",)),
    ("task.", ("task.manage",)),
    ("reminder.create", ("reminder.create", "notification.manage")),
    ("reminder.", ("notification.manage", "reminder.create")),
    ("notification.", ("notification.manage",)),
    ("calendar.", ("calendar.manage",)),
    ("note.", ("note.manage",)),
    ("routine.", ("routine.manage",)),
    ("capture.screenshot", ("capture.screenshot",)),
    ("capture.active.window", ("vision.describe", "capture.screenshot")),
    ("vision.describe", ("vision.describe",)),
    ("ocr.read", ("ocr.read", "vision.describe")),
    ("system.power", ("system.power",)),
    ("system.settings.", ("system.settings",)),
    ("desktop.wallpaper.set", ("system.settings",)),
    ("system.recyclebin.empty", ("filesystem.trash",)),
    ("system.", ("system.status",)),
    ("display.status", ("system.status", "system.settings")),
    ("network.", ("system.status",)),
    ("software.", ("system.status",)),
    ("storage.", ("system.status",)),
    ("shell.command.run", ("system.status",)),
    ("app.installed", ("system.status", "app.open")),
    ("game.launch", ("game.launch",)),
    ("game.purchase.", ("game.purchase",)),
    ("game.install", ("game.install", "game.manage")),
    ("game.uninstall", ("game.install", "game.manage")),
    ("game.", ("game.manage",)),
    ("office.document.", ("office.document",)),
    ("document.", ("office.document",)),
    ("memory.save", ("memory.save",)),
    ("memory.sensitive.save", ("memory.save",)),
    ("memory.forget", ("memory.forget",)),
    ("memory.session.clear", ("memory.forget",)),
    ("memory.", ("memory.recall",)),
    ("message.", ("message.send",)),
    ("email.", ("message.send",)),
    ("client.channel.locate", ("message.send",)),
    ("filesystem.write.text", ("filesystem.write",)),
    ("filesystem.create.directory", ("filesystem.write",)),
    ("filesystem.sandbox.append.named", ("filesystem.write",)),
    ("filesystem.search", ("filesystem.search",)),
    ("filesystem.known.search", ("filesystem.search",)),
    ("filesystem.known.duplicates", ("filesystem.search",)),
    ("filesystem.trash.", ("filesystem.trash",)),
    ("filesystem.known.trash.named", ("filesystem.trash",)),
    ("filesystem.path.ensure.absent", ("filesystem.trash",)),
    ("filesystem.copy", ("filesystem.transfer",)),
    ("filesystem.move", ("filesystem.transfer",)),
    ("filesystem.sandbox.move.named", ("filesystem.transfer",)),
    ("file.compress", ("filesystem.transfer",)),
    ("file.open", ("filesystem.read",)),
    ("filesystem.", ("filesystem.read",)),
    ("clipboard.", ("clipboard.manage",)),
    ("wifi.", ("wifi.manage",)),
    ("bluetooth.", ("bluetooth.manage",)),
    ("peripheral.", ("peripheral.manage",)),
    ("backup.", ("backup.manage",)),
    ("package.", ("package.install",)),
    ("calculator.", ("calculator",)),
)


def families_of(operation: str) -> tuple[str, ...]:
    for prefix, families in _FAMILY_RULES:
        if operation == prefix or operation.startswith(prefix):
            return families
    return (operation,)


# Re-labels of the old oracle, applied in the open (DECISIONES_OPUS_2026-09-22 §9) and counted in every score:
# RL1  an information question the oracle calls conversation may also be answered with a public search
#      (sealed KNOWLEDGE1473 / d8eb88367: «dime qué es X» searches the entity).
# RL2  an order to the PC the oracle calls conversation («abre el panel de control», «click the OK button») is an
#      effect request: any effect or a single question counts; a conversation does not.
RL1_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:(?:dime|decime|explicame|explica|tell me)\s+)?(?:que|qué|quien|quién|como|cómo|cual|cuál|"
    r"what|who|how|which)\s+(?:es|son|fue|era|funciona|is|are|was|does)\b",
    re.IGNORECASE,
)
RL2_ORDER = re.compile(
    r"^[¿?¡!\s]*(?:abre|abri|abrí|cierra|cerra|cerrá|borra|borrá|elimina|copia|copiá|mueve|move|open|close|click|"
    r"clic|haz\s+clic|pulsa|presiona|press|type|escribe|escribí|minimiza|maximiza|sube|subí|baja|bajá|silencia|"
    r"mutea|apaga|apagá|enciende|prende|pon|poné|ponme|busca|buscá|search|play|reproduce|captura|toma|take|"
    r"delete|copy|guarda|save|crea|creá|create|instala|install|descarga|download|lanza|launch|conecta|connect)\b",
    re.IGNORECASE,
)


def relabel(entry: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if entry.get("expect") != "conversation":
        return entry, None
    text = str(entry.get("text") or "").strip()
    if RL1_QUESTION.search(text):
        return {**entry, "expect": "effect_or_conversation", "families": ["web.search"]}, "RL1"
    if RL2_ORDER.search(text):
        return {**entry, "expect": "any_effect_or_question", "families": []}, "RL2"
    return entry, None


def verdict(entry: dict[str, Any], decision: dict[str, Any]) -> tuple[bool, str]:
    """(understood, failure type) of one decision against the row's oracle."""

    if "error" in decision:
        return False, "error"
    kind = decision.get("kind")
    effects = list(decision.get("effects") or [])
    reply = str(decision.get("reply") or "")
    served = {family for operation in effects for family in families_of(operation)}
    expect = entry["expect"]
    if kind == "conversation" and reply:
        sys.path.insert(0, str(REPO / "src"))
        from baxy_mind.llm import visible_reply_claims_a_completed_effect

        if visible_reply_claims_a_completed_effect(reply):
            return False, "efecto_inventado"
    if expect == "any_honest":
        # The motor's rows (Fase 4/5): any honest turn counts; only an invented effect or an error does not.
        return True, "bien"
    if expect == "any_effect_or_question":
        return (kind in {"action", "plan", "clarify"}), ("bien" if kind in {"action", "plan", "clarify"} else "no_leido")
    if expect == "no_effect":
        return (kind in {"conversation", "clarify"}), ("bien" if kind in {"conversation", "clarify"} else "efecto_no_pedido")
    if expect == "effect_or_clarify" and kind == "clarify":
        return True, "bien"
    if expect == "effect_or_conversation" and kind == "conversation":
        return True, "bien"
    if expect == "conversation":
        if kind == "conversation":
            return True, "bien"
        if kind == "clarify":
            return False, "aclaracion_innecesaria"
        return False, "efecto_no_pedido"
    if expect == "limit":
        return (kind in {"conversation", "clarify"} and not effects), ("bien" if not effects else "limite_que_falto")
    wanted = set(entry["families"])
    if kind in {"action", "plan"}:
        if wanted <= served:
            return True, "bien"
        return False, "incompleto" if wanted & served else "leido_mal"
    if kind == "clarify":
        return False, "aclaracion"
    if decision.get("conversation_kind") == "unsupported":
        return False, "limite_falso"
    return False, "no_leido"


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (DATA / "historical_messages.jsonl").open(encoding="utf-8")]
    mapping = {row["message_id"]: row for row in map(json.loads, (DATA / "historical_message_mapping.jsonl").open(encoding="utf-8"))}
    kept, dropped = [], []
    seen: set[str] = set()
    counts: dict[str, Counter[str]] = defaultdict(Counter)

    def keep(entry: dict[str, Any]) -> None:
        key = " ".join(fold(entry["text"]).split())
        if key in seen:
            counts[entry["layer"]]["duplicate_text"] += 1
            return
        seen.add(key)
        counts[entry["layer"]]["kept"] += 1
        kept.append(entry)

    def drop(layer: str, reason: str, row_id: str, text: str, language: str) -> None:
        counts[layer][reason] += 1
        dropped.append({"id": row_id, "layer": layer, "reason": reason, "language": language, "text": text[:300]})

    # 742 survey literals first: they are layer A and their own oracle (the credited decision).
    if REGISTRY.is_file():
        for line in REGISTRY.open(encoding="utf-8"):
            row = json.loads(line)
            text = row["literal"]
            language = language_of(text)
            counts["A"]["seen_survey"] += 1
            # The survey is the owner's own: a garbled word («¡Habristín!») stays as written.
            if language not in {"es", "en", "mixed", "unknown"}:
                drop("A", "language_" + language, row["case_id"], text, language)
                continue
            keep({"id": row["case_id"], "layer": "A", "source": "survey742", "language": language, "text": text,
                  "expect": "survey", "families": [], "status": row.get("verification_status")})
    for path in REAL_LOGS:
        if not path.is_file():
            continue
        log = [json.loads(line) for line in path.open(encoding="utf-8")]
        for index, row in enumerate(log):
            if row.get("role") != "user":
                continue
            # A real turn is replayed with the dialogue it had: the last eight messages as they were,
            # and the pending request when BAXY had just asked.
            before = [item for item in log[max(0, index - 8):index] if item.get("role") in {"user", "assistant"}]
            history = [{"role": item["role"], "content": str(item.get("text") or "")} for item in before]
            pending = None
            if before and before[-1].get("role") == "assistant" and before[-1].get("route") == "clarification":
                pending = next((str(item.get("text")) for item in reversed(before) if item.get("role") == "user"), None)
            text = str(row.get("text") or "")
            language = language_of(text)
            counts["A"]["seen_real_log"] += 1
            if language not in {"es", "en", "mixed"}:
                drop("A", "language_" + language, f"log:{index}", text, language)
                continue
            keep({"id": f"log:{index}", "layer": "A", "source": "baxy_definitivo_log", "language": language,
                  "text": text, "expect": "manual", "families": [], "history": history, "pendingObjective": pending})
    for row in rows:
        if row.get("dedup_status") != "canonical_source":
            continue
        layer = layer_of(row)
        text = clean(row.get("text_literal") or "")
        counts[layer]["seen_canonical"] += 1
        language = language_of(text)
        if language not in {"es", "en", "mixed"}:
            drop(layer, "language_" + language, row["message_id"], text, language)
            continue
        reason = addressee_of(row)
        if reason is not None:
            drop(layer, "addressee_" + reason, row["message_id"], text, language)
            continue
        expect, families = expect_of(mapping.get(row["message_id"], {}))
        if expect is None:
            drop(layer, "oracle_" + str(mapping.get(row["message_id"], {}).get("outcome_type")), row["message_id"], text, language)
            continue
        keep({"id": row["message_id"], "layer": layer, "source": row.get("source"), "language": language,
              "text": text, "expect": expect, "families": families, "class": row.get("class")})
    with (OUT / "corpus.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for entry in kept:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    with (OUT / "dropped.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for entry in dropped:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    random.seed(20260922)
    sample = {reason: random.sample([d for d in dropped if d["reason"] == reason],
                                    min(15, sum(1 for d in dropped if d["reason"] == reason)))
              for reason in sorted({d["reason"] for d in dropped})}
    (OUT / "dropped_sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    languages = Counter((entry["layer"], entry["language"]) for entry in kept)
    summary = {
        "layers": {layer: dict(counter) for layer, counter in sorted(counts.items())},
        "kept_languages": {f"{layer}:{lang}": count for (layer, lang), count in sorted(languages.items())},
        "kept_expect": dict(Counter((entry["layer"], entry["expect"]) for entry in kept).most_common()),
    }
    summary["kept_expect"] = {f"{layer}:{expect}": count for (layer, expect), count in summary["kept_expect"].items()}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def score(decisions_path: pathlib.Path, survey_reference: pathlib.Path | None, json_out: str | None) -> None:
    """Per layer, per expected family and per failure type. Survey rows are judged against the decision the
    registry credited (the reference run on the credited HEAD) — an open row is not yet understood; real-log
    rows need a hand label in ``OUT/labels_real_log.json`` ({id: {"expect": ..., "families": [...]}})."""

    corpus = _load_jsonl(OUT / "corpus.jsonl")
    decisions = {row.get("case_id"): row for row in _load_jsonl(decisions_path)}
    reference = {row["case_id"]: row for row in _load_jsonl(survey_reference)} if survey_reference else {}
    labels_path = OUT / "labels_real_log.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.is_file() else {}
    table: dict[str, Counter[str]] = defaultdict(Counter)
    by_family: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    detail = []
    relabels: list[dict[str, Any]] = []
    for entry in corpus:
        layer = entry["layer"]
        decision = decisions.get(entry["id"])
        digest = hashlib.sha256(entry["text"].encode("utf-8")).hexdigest()
        if decision is not None and decision.get("text_sha256") not in (None, digest):
            decision = None  # decided on another text (the corpus was cleaned since)
        if decision is None:
            table[layer]["sin_decision"] += 1
            continue
        if entry["expect"] == "survey" and entry["id"] in labels:
            # A covered row whose reference run already decided against its credit (e.g. H0086 «bajá el
            # volumen a 20» read as an install since REOPEN1993) is judged by its hand label.
            ok, why = verdict({**entry, **labels[entry["id"]]}, decision)
            family = "survey"
        elif entry["expect"] == "survey":
            credited = reference.get(entry["id"])
            key = lambda row: (row.get("kind"), row.get("operation"), tuple(row.get("effects") or ()))  # noqa: E731
            if entry.get("status") != "covered":
                ok, why = False, "abierta_sin_etiqueta"
            elif credited is None:
                ok, why = False, "sin_referencia"
            else:
                ok, why = key(decision) == key(credited), "bien" if key(decision) == key(credited) else "cambio_de_decision"
            family = "survey"
        elif entry["expect"] == "manual":
            label = labels.get(entry["id"])
            if label is None:
                table[layer]["sin_etiqueta"] += 1
                continue
            if label.get("expect") == "skip":
                table[layer]["fuera_confirmacion_del_shell"] += 1
                continue
            ok, why = verdict({**entry, **label}, decision)
            family = (label.get("families") or [label.get("expect")])[0]
        else:
            family = (entry["families"] or [entry["expect"]])[0]
            if entry["families"] and all(f.startswith("memory.") for f in entry["families"]):
                # «recuerda que…» is taken by the shell's private memory route before the mind is asked
                # (NaturalMemoryRequestParser); a mind-only replay cannot judge it.
                table[layer]["fuera_ruta_memoria_del_shell"] += 1
                continue
            if layer != "A":
                relabelled, rule = relabel(entry)
                if rule:
                    table[layer]["reetiqueta:" + rule] += 1
                    relabels.append({"id": entry["id"], "rule": rule, "text": entry["text"][:200],
                                     "old": entry["expect"], "new": relabelled["expect"]})
                    entry = relabelled
            ok, why = verdict(entry, decision)
        table[layer]["total"] += 1
        table[layer]["bien" if ok else "mal"] += 1
        # Layer A is two populations: the survey (judged against what it credited) and real conversations.
        part = f"{layer}:{entry.get('source') if layer == 'A' else layer}"
        table[part]["total"] += 1
        table[part]["bien" if ok else "mal"] += 1
        table[layer]["fallo:" + why] += 0 if ok else 1
        by_family[(layer, family)]["total"] += 1
        by_family[(layer, family)]["bien"] += ok
        detail.append({"id": entry["id"], "layer": layer, "ok": ok, "why": why, "family": family,
                       "kind": decision.get("kind"), "effects": decision.get("effects")})
    if relabels:
        random.seed(20260923)
        (OUT / "relabel_sample.json").write_text(
            json.dumps(random.sample(relabels, min(50, len(relabels))), ensure_ascii=False, indent=1), encoding="utf-8"
        )
    for layer in sorted(table):
        row = table[layer]
        total = row["total"] or 1
        failures = ", ".join(f"{key[6:]} {count}" for key, count in row.most_common() if key.startswith("fallo:") and count)
        print(f"capa {layer}: {row['bien']}/{row['total']} = {100 * row['bien'] / total:.1f} %"
              + (f"  (sin decisión {row['sin_decision']})" if row["sin_decision"] else "")
              + (f"  (sin etiqueta {row['sin_etiqueta']})" if row["sin_etiqueta"] else "")
              + "".join(f"  ({key} {count})" for key, count in row.items() if key.startswith("reetiqueta:")))
        print(f"    fallos: {failures}")
        worst = sorted(((key[1], value) for key, value in by_family.items() if key[0] == layer),
                       key=lambda item: item[1]["bien"] / item[1]["total"])[:12]
        print("    peores familias: " + ", ".join(f"{name} {value['bien']}/{value['total']}" for name, value in worst))
    if json_out:
        pathlib.Path(json_out).write_text(json.dumps({
            "layers": {layer: dict(counter) for layer, counter in table.items()},
            "families": {f"{layer}:{family}": dict(counter) for (layer, family), counter in by_family.items()},
            "detail": detail,
        }, ensure_ascii=False, indent=1), encoding="utf-8")


def sample(size: int) -> None:
    """``corpus_run.jsonl``: layers A and B whole, layer C as a stratified sample (seeded, proportional to each
    expected family, at least three rows per stratum). The model path is ~2.4 s a turn; C whole would take hours."""

    corpus = _load_jsonl(OUT / "corpus.jsonl")
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    kept = [entry for entry in corpus if entry["layer"] != "C"]
    for entry in corpus:
        if entry["layer"] == "C":
            strata[(entry["expect"], (entry["families"] or ["-"])[0])].append(entry)
    total = sum(len(rows) for rows in strata.values())
    rng = random.Random(20260923)
    chosen = 0
    for key in sorted(strata):
        rows = strata[key]
        take = min(len(rows), max(3, round(size * len(rows) / total)))
        kept.extend(rng.sample(rows, take))
        chosen += take
    with (OUT / "corpus_run.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for entry in kept:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"corpus_run: {len(kept)} filas (C muestreada {chosen} de {total} en {len(strata)} estratos)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sm = sub.add_parser("sample")
    sm.add_argument("--size", type=int, default=1000)
    sc = sub.add_parser("score")
    sc.add_argument("decisions", type=pathlib.Path)
    sc.add_argument("--survey-reference", type=pathlib.Path)
    sc.add_argument("--json")
    args = parser.parse_args(argv)
    if args.command == "build":
        build()
    elif args.command == "sample":
        sample(args.size)
    elif args.command == "score":
        score(args.decisions, args.survey_reference, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
