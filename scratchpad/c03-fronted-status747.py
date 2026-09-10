"""Probe one-sided status veto on fronted topics without editing tested source."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import inspect
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind import effect_intent as ei


def fronted_status_request(text: str) -> bool:
    text = ei._strip_request_envelope(ei._fold(text)).strip(" ¿?¡!.")
    split = re.fullmatch(r"(?P<topic>[^,;]+)[,;]\s*(?P<body>.+)", text)
    if split is None:
        return False
    topic, body = split.group("topic"), split.group("body")
    relation = r"(?:de|del|sobre|respecto a|en cuanto a|con respecto a|about|regarding|as for)"
    determiner = r"(?:el|la|mi|este|esta|the|my|this)"
    # The measured scope vocabulary already has one owner. The optional C
    # qualifies the existing system-disk request; it does not add drive selection.
    if not re.fullmatch(
        rf"(?:{relation}\s+)?(?:{determiner}\s+)?"
        rf"(?:{ei._MACHINE_STATUS_EVIDENCE})(?:\s+c:?)?", topic,
    ):
        return False
    return (
        ei._is_direct_request(body)
        and ei._head_is(ei._request_head(body), rf"(?:{ei._MACHINE_STATUS_HEAD}|tell)")
        and ei._has(body, ei._MACHINE_STATUS_OBSERVATION)
        and ei._system_status_domain(text)
        and ei._machine_status_scopes_are_one_reading(text)
        and ei._machine_status_is_the_whole_clause(text)
        and not ei._is_negative_effect_clause(body)
        and not ei._is_meta_or_tool_denial(text)
        and not ei._other_device_effect_scope(text)
        and not ei.explicit_non_action_frame(text)
    )


def main():
    out = ROOT / "artifacts/comprobaciones/C03/FRONTED_STATUS747"
    out.mkdir(exist_ok=False)
    source = ROOT / "src/baxy_mind/effect_intent.py"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    scopes = [
        ("disco C", "disk C", "cuánto espacio está ocupado", "how much space is occupied"),
        ("RAM", "RAM", "cuánta memoria queda libre", "how much memory is free"),
        ("CPU", "CPU", "qué modelo tengo", "which model I have"),
        ("GPU", "GPU", "qué modelo está instalado", "which model is installed"),
        ("batería", "battery", "cuánta carga queda", "how much charge remains"),
    ]
    cases = []
    for index, (es, en, query_es, query_en) in enumerate(scopes):
        forms = [
            f"Del {es}, dime {query_es}.",
            f"Sobre mi {es}, dime {query_es}.",
            f"Respecto a {es}, comprueba {query_es}.",
            f"En cuanto a {es}, muéstrame {query_es}.",
            f"Baxy, por favor: sobre {es}, dime {query_es}.",
            f"About my {en}, tell me {query_en}.",
            f"Regarding the {en}, show me {query_en}.",
            f"As for this {en}, check {query_en}.",
            f"Sobre mi {es}, tell me {query_en}.",
            f"About the {en}, dime {query_es}.",
        ]
        for variant, text in enumerate(forms):
            cases.append({"id": f"P{index + 1}-{variant + 1}", "text": text, "expected": True})
    negative = [
        "Del disco C, borra el archivo carta.txt.",
        "Sobre mi RAM, ayer había más libre.",
        "About my CPU, tell me what model I had last year.",
        "Regarding the battery, show me how much charge it will have tomorrow.",
        "Sobre la batería de mi auto, dime cuánta carga queda.",
        "About my phone CPU, tell me which model I have.",
        "De mi memoria del colegio, dime qué recuerdo queda.",
        "Sobre el disco de música, dime cuánto dura.",
        "Sobre mi GPU, dime cuál me recomiendas comprar.",
        "Del disco C, no me digas cuánto espacio está ocupado.",
        "Respecto a RAM, no compruebes cuánta queda libre.",
        "About my CPU, do not check the current load.",
        "Repite: «Del disco C, dime cuánto espacio está ocupado».",
        "Translate 'About my CPU, tell me which model I have'.",
        '«Del disco C, dime cuánto espacio está ocupado».',
        "Del disco C, «dime cuánto espacio está ocupado».",
        "Sobre la red neuronal, dime cómo está la conexión.",
        "About my CPU, explain how processors work.",
        "Sobre RAM, si fuera otro equipo dime cuánta tendría.",
        "Sobre GPU, escribe una nota que diga cuánto se está usando.",
    ]
    cases.extend({"id": f"N{i + 1}", "text": text, "expected": False} for i, text in enumerate(negative))
    def write(name, value):
        (out / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
    write("PREREG.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "source_sha256": source_sha,
        "cases": cases, "candidate": inspect.getsource(fronted_status_request),
        "hypothesis": "Retain a native system.status proposal when a complete scope topic precedes an explicit current observation request. Reuse existing scope and exclusion gates; do not normalize the whole turn or extend deterministic authority.",
        "criterion": "All70 domain controls correct, no new false domain. This only tests the first veto; deterministic resolution, arguments, product, survey and resources remain unverified.",
        "full7_concurrent": "Only pure calls to existing unchanged functions; no inference, tests, provider effects or source writes.",
    })
    rows = []
    for case in cases:
        before = ei.operation_domain_is_grounded(case["text"], "system.status")
        proposal = fronted_status_request(case["text"])
        rows.append({**case, "before": before, "after": bool(before or proposal),
                     "fronted_request": proposal,
                     "original_clauses": ei._request_clauses(ei._fold(case["text"]))})
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    counts = {
        "cases": len(rows), "before_correct": sum(x["before"] == x["expected"] for x in rows),
        "after_correct": sum(x["after"] == x["expected"] for x in rows),
        "gains": sum(x["before"] != x["expected"] and x["after"] == x["expected"] for x in rows),
        "losses": sum(x["before"] == x["expected"] and x["after"] != x["expected"] for x in rows),
        "false_vetoes": sum(x["expected"] and not x["after"] for x in rows),
        "false_domains": sum(not x["expected"] and x["after"] for x in rows),
    }
    write("RESULT.json", {"counts": counts, "rows": rows, "source_unchanged": True,
                          "adopted": False, "coverage_added": 0, "model_inference": False})
    print(json.dumps({"counts": counts, "failures": [x for x in rows if x["after"] != x["expected"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
