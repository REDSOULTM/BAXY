"""Construye y CONGELA los sets de evaluación del torneo LLM (semilla 20260716).

- sampled_cases.jsonl: muestra estratificada de los 675 casos de oráculo
  (40 por set; el set entero si tiene menos).
- conversation_probes.jsonl: 24 mensajes del ledger (misiones de conversación,
  clase conversation_question / knowledge) + 6 probes autorados.

Se ejecuta UNA vez antes de medir; los archivos generados quedan versionados.
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.tools.atomic_output import replace_bytes_atomically  # noqa: E402
from baxy_mind.tools.frozen_files import (  # noqa: E402
    verify_frozen_file,
    verify_frozen_payload,
)

SEED = 20260716
PROTOCOL = HERE / "protocol.json"
CASES = verify_frozen_file(REPO, PROTOCOL, "router_cases")
HISTORICAL_MESSAGES = verify_frozen_file(
    REPO,
    PROTOCOL,
    "historical_messages",
)

# Curaduría explícita: 24 mensajes del ledger revisados a mano, SOLO
# español/inglés/spanglish (el campo `language` del corpus es heurístico y
# deja pasar francés/italiano/portugués; esos son trace-only y no son backlog
# 1.0). Mezcla congelada: conocimiento, identidad/capacidades, cierre social,
# typos reales y pedidos fuera de catálogo (prueban no_fabricated_effect).
CURATED_LEDGER_IDS = [
    "msg_a18bd90e571aed63ab59",  # es: qué es una resistencia eléctrica
    "msg_2094f9f6ae95c2756750",  # es: qué pasa si cierro Steam
    "msg_77a1094cbeeec52e668b",  # en: what's the foreground process
    "msg_708b0e106976c5a8c6de",  # en: Thanku what a great work!
    "msg_dee7660a1ecea7947563",  # en: open calcualtor (typo, fuera de catálogo)
    "msg_5ba84a96666df3a73a93",  # en: What is a winglet?
    "msg_e9623068609076b74e1d",  # es: jamás apagues la pc
    "msg_5d6a61aee58e704a3799",  # en: Can you please make it easier to understand?
    "msg_d39dc5fb2e6444ace2f1",  # es: Cómo puedo encontrar sentido a la vida
    "msg_d6b7f2a4b1d7541ca588",  # es: qué fue lo primero que te pregunté
    "msg_9979a0ca87ad9bc14751",  # es: hablame de Mortal Kombat
    "msg_7c0282642b0d7bc3c26a",  # es: ¿Podrías traducir ese código a Python?
    "msg_cf081d1789bb6783dc4d",  # es: 5 palabras que comiencen con H
    "msg_10d4b70e3d85abf28752",  # es/spanglish técnico con typos (robustez)
    "msg_52b1aa947165ff6a7dba",  # es: Gracias por tu ayuda. Nos hablamos pronto.
    "msg_1bc6403b79c4b7f6b40e",  # es: capital de francia
    "msg_0a30cb428e740b3b900f",  # es: entra a discord al chat de juanpi (fuera de catálogo)
    "msg_17cb1d3b1bb374c2890c",  # es: Cierra Opera ahora (fuera de catálogo)
    "msg_b4cf3d92c8c8d771fcce",  # en: is Steam open right now? (fuera de catálogo)
    "msg_7292a68484f75206474c",  # es: qué no puedes hacer
    "msg_b87f958691691d121e68",  # es: ¿Qué es ChatGPT?
    "msg_d1566351c3f1e2b112db",  # es: Háblame de ti, tú que se supone que haces.
    "msg_7b2d01588814c819f784",  # es: qué clima hace hoy en Buenos Aires (sin internet)
    "msg_74de8a899ad18ae55bf2",  # es: recordame tomar la pastilla a las 3 (fuera de catálogo)
]

AUTHORED_PROBES = [
    {"text": "hola baxy, qué puedes hacer?", "language": "es"},
    {"text": "who are you and what can you do on this pc?", "language": "en"},
    {"text": "explícame en simple qué es la memoria RAM", "language": "es"},
    {"text": "oye can you help me practicar mi english?", "language": "spanglish"},
    {"text": "puedes mandar correos o entrar a internet?", "language": "es"},
    {"text": "gracias, eso era todo por hoy", "language": "es"},
]


def main() -> None:
    rng = random.Random(SEED)

    cases = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
    ]
    by_set: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        by_set[case["set"]].append(case)
    sampled: list[dict] = []
    for name in sorted(by_set):
        group = sorted(by_set[name], key=lambda c: c["message_id"])
        take = group if len(group) <= 40 else rng.sample(group, 40)
        sampled.extend(sorted(take, key=lambda c: c["message_id"]))
    sampled_payload = "".join(
        json.dumps(case, ensure_ascii=False) + "\n"
        for case in sampled
    ).encode("utf-8")

    texts: dict[str, dict] = {}
    with HISTORICAL_MESSAGES.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["message_id"] in CURATED_LEDGER_IDS:
                texts[row["message_id"]] = row

    missing = [mid for mid in CURATED_LEDGER_IDS if mid not in texts]
    if missing:
        raise SystemExit(f"IDs curados ausentes del corpus: {missing}")

    probes = [
        {
            "message_id": mid,
            "text": (texts[mid].get("text_literal") or "").strip(),
            "language": texts[mid].get("language"),
        }
        for mid in CURATED_LEDGER_IDS
    ] + [
        {"message_id": f"authored_{index}", **probe}
        for index, probe in enumerate(AUTHORED_PROBES)
    ]
    probes_payload = "".join(
        json.dumps(probe, ensure_ascii=False) + "\n"
        for probe in probes
    ).encode("utf-8")

    sampled_path = verify_frozen_payload(
        REPO,
        PROTOCOL,
        "sampled_cases",
        sampled_payload,
    )
    probes_path = verify_frozen_payload(
        REPO,
        PROTOCOL,
        "conversation_probes",
        probes_payload,
    )
    replace_bytes_atomically(sampled_path, sampled_payload)
    replace_bytes_atomically(probes_path, probes_payload)

    print(f"sampled_cases: {len(sampled)} | conversation_probes: {len(probes)}")


if __name__ == "__main__":
    main()
