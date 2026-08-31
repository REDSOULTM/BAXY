"""Re-inspect code_tests-477 from BAXY git blobs (Schema Agent, not worktree)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_goal095_queues import PROGRAMACION, hash_git_blob
from scripts.goal095_code_ledger import dump_json, load_json, validate_ledger, queue_paths
from scripts.goal095_inspect_code_batch import py_outline

KEEP = REPO / "artifacts" / "goal095" / "sources" / "baxy_schema_agent.keep.sha256.jsonl"
LEDGER = (
    REPO
    / "artifacts"
    / "goal095"
    / "ledger"
    / "code_tests-477-baxy_schema_agent-baxy_schema_agent.json"
)
EXTRACT = REPO / "artifacts" / "goal095" / "extract"
HEAD = "e6f9c1e5130d17d8de2c1b9447c327e53f468948"
HW = "Windows · BAXY git blob Schema Agent (Tools-Reduce)"


def main() -> int:
    baxy = PROGRAMACION / "BAXY"
    by_path = {}
    for line in KEEP.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        by_path[row["path"]] = row
    ledger = load_json(LEDGER)
    tmp = EXTRACT / "_schema_agent_blobs"
    tmp.mkdir(parents=True, exist_ok=True)
    outlines: dict[str, dict] = {}
    for row in ledger["files"]:
        meta = by_path[row["path"]]
        data, digest = hash_git_blob(baxy, meta["git_blob"])
        if digest != row["sha256"]:
            raise SystemExit(f"hash mismatch {row['path']}")
        dest = tmp / row["path"].replace("/", "__")
        dest.write_bytes(data)
        outlines[row["path"]] = py_outline(dest)
        n = outlines[row["path"]]["lines"]
        row["ranges"] = [f"1-{n}"]
        row["parse_note"] = f"git blob {meta['git_blob'][:12]} @ {meta['git_commit'][:12]}"
    cards = []
    tests = [row["path"] for row in ledger["files"] if "/tests/" in row["path"]]
    schemas = [row["path"] for row in ledger["files"] if "tool_schemas.py" in row["path"]]
    scripts = [row["path"] for row in ledger["files"] if row["path"].startswith("scripts/")]
    tool = outlines[schemas[0]]
    cards.append(
        {
            "card_id": "schema-agent-tool-schemas",
            "disposition": "reject_candidate",
            "component": "tool_schemas.py de Schema Agent (catalogo OpenAI/JSON en el prompt)",
            "contract": (
                f"Modulo {tool['lines']} lineas. Head: "
                + " ".join(tool["head"][:12])[:500]
                + f" defs={len(tool['defs'])}"
            ),
            "dependencies": "gemma4_agent tools_pkg; tests de schema en el mismo lote",
            "historical_test": "test_schema_handler_contract.py y test_experience_schema_drift.py en este lote",
            "limitations": "No esta en el worktree de BAXY HEAD; vive en git Tools-Reduce/vram4_lean/v0.9.2. Goal 01 rechazo catalogo cocido en pesos/prompt.",
            "current_owner": "src/Baxy.Kernel/Operations/ProductCatalog.cs",
            "source_files": schemas,
            "failure_mechanism": "El universo de tools vive en un modulo Python que el LLM ve. BAXY exige catalogo tipado autorizado por kernel.",
            "readme_vs_real": "El blob git coincide con el hash 09.5.1. No hay copia en HEAD actual de BAXY.",
            "invariant_risk": "Trasplantar tool_schemas como tools OpenAI rompe invariante 1.",
            "duplicate_layers": "Schema Agent vs FunctionGemma slim schemas vs ProductCatalog .NET vs Carter v4 @tool.",
            "provisional": True,
            "provenance": {
                "path": schemas[0],
                "ranges": [f"1-{tool['lines']}"],
                "date": "2026-06-26",
                "hardware": HW,
                "model": "n/a (schemas)",
                "commit": HEAD,
            },
        }
    )
    cards.append(
        {
            "card_id": "schema-agent-schema-tests",
            "disposition": "adapt_candidate",
            "component": "Tests de contrato de schema (no inventar tools, drift, cache de nombres)",
            "contract": "Seis tests: no invented msg, experience schema drift, handler contract, names cache, whatsapp slots, window_active examples.",
            "dependencies": "tool_schemas.py historico",
            "historical_test": "Los seis ficheros SON los tests. No reejecutados (arbol git, no worktree).",
            "limitations": "Aterrizan sobre el catalogo Python, no ProductCatalog.",
            "current_owner": "tests/Baxy.Kernel.Tests y tests de catalogo",
            "source_files": tests,
            "failure_mechanism": "Contratos de schema en pytest Python; BAXY los tiene en .NET. Adaptar la idea (no inventar nombres) no el harness.",
            "readme_vs_real": "Los tests existen en el blob git. HEAD de BAXY ya no tiene gemma4_agent/.",
            "invariant_risk": "Adaptar aserciones de 'no inventar' al kernel no rompe invariantes.",
            "duplicate_layers": "tests Schema Agent vs Kernel.Tests vs FunctionGemma holdout.",
            "provisional": True,
            "provenance": {
                "path": tests[0],
                "ranges": [f"1-{outlines[tests[0]]['lines']}"],
                "date": "2026-06",
                "hardware": HW,
                "model": "n/a (pytest)",
                "commit": HEAD,
            },
        }
    )
    cards.append(
        {
            "card_id": "schema-agent-schema-scripts",
            "disposition": "evidence_only",
            "component": "Scripts de medicion y verify de schema hint",
            "contract": " _measure_tool_schemas.py y _verify_schema_hint_gate.py: medidor y gate de hints.",
            "dependencies": "tool_schemas.py",
            "historical_test": "Scripts, no pytest.",
            "limitations": "No se ejecutaron. Son receta de medicion de un catalogo abandonado.",
            "current_owner": "scripts/ de BAXY Definitivo (gates actuales)",
            "source_files": scripts,
            "failure_mechanism": "Gate de hint de schema sobre un catalogo que ya no es el ProductCatalog.",
            "readme_vs_real": "Blobs git coinciden. No hay equivalente 1:1 en scripts/ actuales.",
            "invariant_risk": "No ejecutar contra el catalogo vivo sin reescritura.",
            "duplicate_layers": "measure scripts vs test_source_quality.ps1",
            "provisional": True,
            "provenance": {
                "path": scripts[0],
                "ranges": [f"1-{outlines[scripts[0]]['lines']}"],
                "date": "2026-06",
                "hardware": HW,
                "model": "n/a",
                "commit": HEAD,
            },
        }
    )
    ledger["cards"] = cards
    ledger["hash_check"] = "9/9 git blob=cola 09.5.1; 0 en worktree HEAD BAXY"
    ledger["source_head"] = HEAD
    batches_path, _, _ = queue_paths(REPO)
    batches = load_json(batches_path)
    batch = next(item for item in batches if item["batch_id"] == ledger["batch_id"])
    errors = validate_ledger(ledger, batch)
    if errors:
        raise SystemExit("validate: " + "; ".join(errors))
    dump_json(LEDGER, ledger)
    print("ok cards", len(cards), "files", len(ledger["files"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
