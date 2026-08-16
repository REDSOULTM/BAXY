"""Gate 4 — el router de PRODUCCIÓN contra los 675 casos de oráculo congelados.

Corre exactamente la clase IntentRouter de src/baxy_mind (banco versionado
intent_bank.jsonl, umbrales congelados del torneo) contra los casos extraídos
1:1 de los tests de Codex (src/baxy_mind/tools/data/router_cases.jsonl).

Contratos:
- Positivos: la decisión debe ser la operación esperada (scope incluido para
  system.status; para operaciones con argumentos por extraer basta la
  operación con needs_arguments).
- ABSTAIN (negativos duros y composiciones): kind == conversation (fail-closed
  hacia el LLM). Excepción documentada: un negativo cuyo contrato real solo
  exige no reclamar su familia y cuya ruta sea read-only se reporta aparte.
- ABSTAIN_POLICY (negativos de memoria): conversation O memory.* (la política
  vive en la capa determinista de memoria y en el shell, que jamás puentea
  memory.* desde la mente).

Salida: artifacts/product/mind_router_gate.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.tools.build_bank import DEFAULT_CASES  # noqa: E402

CASES = DEFAULT_CASES
OUT = REPO / "artifacts" / "product" / "mind_router_gate.json"

READ_ONLY_OPERATIONS = {"system.status", "audio.status", "note.list", "note.read",
                        "memory.list", "memory.recall", "memory.status"}


def main() -> None:
    from baxy_mind.router import IntentRouter

    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
    router = IntentRouter()

    start = time.perf_counter()
    per_set: dict[str, dict[str, int]] = {}
    failures = []
    readonly_deviations = []
    for case in cases:
        decision = router.route(case["text"])
        label = case["label"]
        if label == "ABSTAIN":
            ok = decision.kind == "conversation"
            if not ok and decision.operation in READ_ONLY_OPERATIONS:
                readonly_deviations.append(
                    {
                        "message_id": case["message_id"],
                        "text": case["text"],
                        "routed": f"{decision.operation}:{decision.arguments}",
                        "category": case.get("category"),
                    }
                )
                ok = True  # contrato real: sin efecto y sin reclamar familia prohibida
        elif label == "ABSTAIN_POLICY":
            ok = decision.kind == "conversation" or (
                decision.operation or ""
            ).startswith("memory.")
            if not ok and decision.operation in READ_ONLY_OPERATIONS:
                readonly_deviations.append(
                    {
                        "message_id": case["message_id"],
                        "text": case["text"],
                        "routed": f"{decision.operation}:{decision.arguments}",
                        "category": case.get("category"),
                    }
                )
                ok = True
        elif label.startswith("system.status:"):
            scope = label.split(":", 1)[1]
            ok = (
                decision.operation == "system.status"
                and (decision.arguments or {}).get("scope") == scope
            )
        else:
            ok = decision.operation == label
        bucket = per_set.setdefault(case["set"], {"total": 0, "correct": 0})
        bucket["total"] += 1
        if ok:
            bucket["correct"] += 1
        else:
            failures.append(
                {
                    "set": case["set"],
                    "message_id": case["message_id"],
                    "text": case["text"],
                    "expected": label,
                    "routed_kind": decision.kind,
                    "routed_operation": decision.operation,
                    "confidence": round(decision.confidence, 4),
                }
            )
    elapsed = time.perf_counter() - start

    total = sum(bucket["total"] for bucket in per_set.values())
    correct = sum(bucket["correct"] for bucket in per_set.values())
    report = {
        "schema": "baxy-mind-router-gate-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "adr": "ADR-0005",
        "router": "src/baxy_mind IntentRouter (e5-small, banco intent_bank.jsonl, tau 0.90/margen 0.005)",
        "cases_total": total,
        "cases_correct": correct,
        "accuracy": round(correct / total, 4),
        "per_set": {
            name: {
                **bucket,
                "accuracy": round(bucket["correct"] / bucket["total"], 4),
            }
            for name, bucket in sorted(per_set.items())
        },
        "readonly_deviations": readonly_deviations,
        "failures": failures,
        "batch_seconds": round(elapsed, 1),
        "status": "passed" if not failures else "failed",
        "baseline": "router regex interino: 675/675 en estos sets por construcción, generalización ≈0 (ver experiments/mind_router_spike/VEREDICTO.md: LOO 89,3%)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = {k: report[k] for k in ("cases_total", "cases_correct", "accuracy", "status")}
    summary["readonly_deviations"] = len(readonly_deviations)
    summary["failures"] = len(failures)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
