"""Torneo de encoders del router (protocolo: tournament_encoder_protocol.json).

Por candidato, en un proceso NUEVO cada vez (RAM limpia):
1. --dev  → congela (tau, margen) del candidato.
2. --eval-coverage y --eval-loo con esos umbrales.
Luego consolida el scorecard.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / "Scripts" / "python.exe"
PROTOCOL = json.loads(
    (HERE / "tournament_encoder_protocol.json").read_text(encoding="utf-8")
)


def run(args: list[str]) -> str:
    result = subprocess.run(
        [str(PY), str(HERE / "run_spike.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "HF_HUB_OFFLINE": "1"},
        cwd=str(HERE),
        timeout=3600,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout


def first_json(text: str) -> dict:
    match = re.search(r"\{.*\n\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"sin JSON en la salida: {text[-500:]}")
    return json.loads(match.group(0))


def main() -> None:
    scorecard = []
    for candidate in PROTOCOL["candidates"]:
        model, prefix = candidate["id"], candidate["prefix"]
        print(f"== {model}", flush=True)
        try:
            dev = first_json(run(["--dev", "--model", model, "--prefix", prefix]))
            tau, margin = dev["frozen_tau"], dev["frozen_margin"]
            run(
                [
                    "--eval-coverage",
                    "--eval-loo",
                    "--model",
                    model,
                    "--prefix",
                    prefix,
                    "--tau",
                    str(tau),
                    "--margin",
                    str(margin),
                ]
            )
            slug = model.replace("/", "__")
            coverage = json.loads(
                (HERE / "results" / f"report_coverage__{slug}.json").read_text(
                    encoding="utf-8"
                )
            )
            loo = json.loads(
                (HERE / "results" / f"report_loo__{slug}.json").read_text(
                    encoding="utf-8"
                )
            )
            dangerous = loo["failure_modes"].get("dangerous_wrong_or_false_route", 0)
            entry = {
                "model": model,
                "status": "measured",
                "frozen_tau": tau,
                "frozen_margin": margin,
                "coverage_accuracy": coverage["overall_accuracy"],
                "coverage_failures": [
                    {
                        "text": failure["text"],
                        "expected": failure["expected"],
                        "predicted": failure["predicted"],
                    }
                    for failure in coverage["failures"]
                ],
                "loo_accuracy": loo["overall_accuracy"],
                "loo_dangerous": dangerous,
                "loo_dangerous_rate": round(dangerous / loo["total_cases"], 4),
                "loo_safe_abstention": loo["failure_modes"].get(
                    "safe_over_abstention", 0
                ),
                "single_query_cpu_ms": loo["single_query_cpu_ms"],
                "process_ram_mib": loo["process_ram_mib"],
                "weights_size_mib": loo["weights_size_mib"],
            }
        except Exception as error:  # noqa: BLE001 — el torneo registra exclusiones
            entry = {
                "model": model,
                "status": "excluded",
                "reason": str(error)[:500],
            }
        print(json.dumps(entry, ensure_ascii=False, indent=2), flush=True)
        scorecard.append(entry)

    out = HERE / "results" / "tournament_encoder_scorecard.json"
    out.write_text(
        json.dumps(
            {"protocol": PROTOCOL["protocol_id"], "results": scorecard},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"scorecard -> {out}")


if __name__ == "__main__":
    main()
