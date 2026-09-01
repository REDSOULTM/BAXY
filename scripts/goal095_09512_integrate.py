"""Load and validate the shipped Goal 09.5.12 lineage close-out.

Reads the published 09.5 campaigns, queue, 09.5.9 matrix and 10.x/11.x
prompts. Does not re-audit historical trees, invent transplant lots, or
copy secrets/binaries/private corpus into Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.build_goal095_queues import FROZEN_0950, sha256_path
from scripts.goal095_0959_matrix import (
    PROTECTED_REJECTS,
    dump_json,
    load_campaign as load_transplant_campaign,
    load_json,
    load_matrix as load_0959_matrix,
)
from scripts.goal095_docs_ledger import load_json as load_json_docs
from scripts.goal095_evidence_campaign import campaign_path as evidence_campaign_path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.09512-integrate.v1"
LEDGER_SCHEMA = "baxy.goal095.09512-ledger.v1"
VERSION = "v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.12_integrar_y_replanificar.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/integrate-09.5.12.json"
MARKDOWN_REL = "documentacion/herencia/09_5_12_INTEGRAR.md"
HANDOFF_REL = "artifacts/goal095/HANDOFF.md"
OWNER_PROMPT = "documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md"
NEXT_PROMPT = "documentacion/sprints/10.0_BASE_VERDE.md"
ORDEN_REL = "documentacion/sprints/00_ORDEN_DESDE_09_5.md"
MAPA_REL = "documentacion/herencia/00_MAPA.md"
BIBLIOTECA_INDICE_REL = "biblioteca/00_INDICE.md"
BIBLIOTECA_INV_REL = "biblioteca/01_INVENTARIO.md"
QUEUE_SUMMARY_REL = "artifacts/goal095/queue/summary.json"
QUEUE_LEDGER_REL = "artifacts/goal095/queue/ledger.json"
DOCS_CAMPAIGN_REL = "artifacts/goal095/campaigns/docs.json"
CODE_CAMPAIGN_REL = "artifacts/goal095/campaigns/code_tests.json"
EVIDENCE_CAMPAIGN_REL = "artifacts/goal095/campaigns/evidence_assets.json"
TRANSPLANT_CAMPAIGN_REL = "artifacts/goal095/campaigns/transplant.json"
VALIDACION_REL = "documentacion/sprints/11_VALIDACION.md"
USO_DIARIO_REL = "documentacion/sprints/10_USO_DIARIO.md"
HERENCIA_TOTAL_REL = "documentacion/sprints/09.5_HERENCIA_TOTAL.md"
SPRINTS_INDICE_REL = "documentacion/sprints/00_INDICE.md"
GENERATED_BEGIN = "<!-- goal095-12-generated:begin -->"
GENERATED_END = "<!-- goal095-12-generated:end -->"
GOAL01_CLOSED = "2026-08-16"
FOUR_CLASSES = (
    "herencia previa",
    "delta nuevo",
    "piezas trasplantadas",
    "rechazos",
)
ALLOWED_FILE_TERMINALS = frozenset(
    {
        "leido",
        "parseado_completo",
        "duplicado_por_hash",
        "binario_inventariado",
        "excluido_razonado",
    }
)
FORBIDDEN_NEXT = (
    OWNER_PROMPT,
    "documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md",
    "documentacion/sprints/09.5.11C_REVALIDAR_07_09.md",
)
FORBIDDEN_BIBLIOTECA_SUFFIXES = (
    ".gguf",
    ".onnx",
    ".bin",
    ".pt",
    ".pth",
    ".safetensors",
    ".ckpt",
    ".wav",
    ".mp3",
    ".pkl",
    ".joblib",
    ".exe",
    ".dll",
)
FORBIDDEN_BIBLIOTECA_PARTS = (
    "/secrets/",
    "\\secrets\\",
    ".env",
    "id_rsa",
    "nontoken",
)
BARS_LITERAL = (
    "200 turnos",
    "1.947/808",
    "2.036",
    "Identidad",
    "Full",
    "500k",
    "FALLO_DE_AMBIENTE",
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ORDEN_LINK_RE = re.compile(r"^\d+\.\s+\[[^\]]+\]\(([^)]+)\)\s*$", re.MULTILINE)
HERITAGE_HEADING = "## Herencia 09.5"
CONTRATO_HEADING = "## Contrato de sesión"
OBJETIVO_HEADING = "## Objetivo único"
CRITERIOS_HEADING = "## Criterios de cierre"
EXECUTABLE_MARK = "## Prompts ejecutables restantes"
GROK46_CONTRACT_MARK = "<!-- grok46-goal-contract:begin -->"

EXECUTABLE_PROMPTS: tuple[str, ...] = (
    "10.0_BASE_VERDE.md",
    "10.1_CORPUS_Y_COLA.md",
    "10.2_PRESENCIA_Y_RECURSOS.md",
    "10.2.5_RECURSOS_EN_REPOSO.md",
    "10.7_CONVERSACION.md",
    "10.8_HECHOS_LOCALES.md",
    "10.9_WEB_Y_ACTUALIDAD.md",
    "10.10_APPS_VENTANAS_VISION.md",
    "10.11_AUDIO.md",
    "10.12_MEDIA_STREAMING_JUEGOS.md",
    "10.13_SISTEMA_CONECTIVIDAD.md",
    "10.14_PRODUCTIVIDAD_MEMORIA.md",
    "10.15_COMUNICACION_NAVEGACION.md",
    "10.16_MISIONES_COMPUESTAS.md",
    "10.17_IDENTIDAD_VIVA.md",
    "10.18_INTEGRACION.md",
    "11.1_COLA_DE_CIERRE.md",
    "11.2_CONTRATOS_RUNTIME.md",
    "11.3_REQUISITOS_A.md",
    "11.4_REQUISITOS_B.md",
    "11.5_REQUISITOS_C.md",
    "11.6_REQUISITOS_D.md",
    "11.7_REQUISITOS_E.md",
    "11.8_REQUISITOS_F.md",
    "11.9_NO_RUNTIME_A.md",
    "11.10_NO_RUNTIME_B.md",
    "11.11_ERRORES_MENTE_KERNEL.md",
    "11.12_ERRORES_PROVIDERS_ESTADO.md",
    "11.13_REGRESION_01_06.md",
    "11.14_REGRESION_07_10.md",
    "11.15_HIGIENE_IDENTIDAD.md",
    "11.16_FULL_Y_CIERRE.md",
)

RETIRED_PROMPTS: tuple[str, ...] = (
    "10.3_USO_REAL_A.md",
    "10.4_USO_REAL_B.md",
    "10.5_USO_REAL_C.md",
    "10.6_USO_REAL_D.md",
)

CLOSED_095_PROMPTS: tuple[str, ...] = (
    "09.5.0_FUENTES_Y_AMBIENTE.md",
    "09.5.1_MANIFIESTO_Y_COLAS.md",
    "09.5.2_LEER_DOCUMENTACION_LOTE.md",
    "09.5.3_AUDITAR_CODIGO_LOTE.md",
    "09.5.4_AUDITAR_EVIDENCIA_LOTE.md",
    "09.5.5_MODELOS_ROUTER_IDIOMAS.md",
    "09.5.6_VOZ_AUDIO_PRESENCIA.md",
    "09.5.7_TOOLS_SKILLS_MISIONES.md",
    "09.5.8_RUNTIME_UI_RECURSOS.md",
    "09.5.9_DECIDIR_HERENCIA.md",
    "09.5.10_TRASPLANTAR_LOTE.md",
    "09.5.11A_REVALIDAR_01_03C.md",
    "09.5.11B_REVALIDAR_04_06.md",
    "09.5.11C_REVALIDAR_07_09.md",
    "09.5.12_INTEGRAR_Y_REPLANIFICAR.md",
)

# citation: machine-searchable 09.5 piece. hueco: proven gap or empty string.
PROMPT_SPECS: tuple[dict[str, str], ...] = (
    {
        "file": "10.0_BASE_VERDE.md",
        "prev": "09.5.12_INTEGRAR_Y_REPLANIFICAR.md",
        "next": "10.1_CORPUS_Y_COLA.md",
        "citation": "09.5.11C Full verde; 09.5.9:llm_decisor, runtime_inferencia, journal",
        "hueco": "",
    },
    {
        "file": "10.1_CORPUS_Y_COLA.md",
        "prev": "10.0_BASE_VERDE.md",
        "next": "10.2_PRESENCIA_Y_RECURSOS.md",
        "citation": "09.5.9:catalogo_tipado; 09.5.4 residual_evidence no se reparsea",
        "hueco": "",
    },
    {
        "file": "10.2_PRESENCIA_Y_RECURSOS.md",
        "prev": "10.1_CORPUS_Y_COLA.md",
        "next": "10.2.5_RECURSOS_EN_REPOSO.md",
        "citation": "09.5.9:carga_descarga_modelos, arranque, process_lifecycle",
        "hueco": "unload-on-idle y arranque frío se miden aquí sobre el keep-warm vivo; no hay vram_manager/Ollama que transplantar",
    },
    {
        "file": "10.2.5_RECURSOS_EN_REPOSO.md",
        "prev": "10.2_PRESENCIA_Y_RECURSOS.md",
        "next": "10.7_CONVERSACION.md",
        "citation": "09.5.8:runtime_ui_recursos; 09.5.9:carga_descarga_modelos, arranque, process_lifecycle",
        "hueco": "el cierre 10.2 midió sólo Baxy.exe y no atribuyó el spin de ONNX/WebView2 al árbol vivo completo",
    },
    {
        "file": "10.7_CONVERSACION.md",
        "prev": "10.2.5_RECURSOS_EN_REPOSO.md",
        "next": "10.8_HECHOS_LOCALES.md",
        "citation": "09.5.9:llm_decisor, encoder_recuperador, puerta_abstencion, verificador_identidad",
        "hueco": "",
    },
    {
        "file": "10.8_HECHOS_LOCALES.md",
        "prev": "10.7_CONVERSACION.md",
        "next": "10.9_WEB_Y_ACTUALIDAD.md",
        "citation": "09.5.4 evidence_assets parseado_completo; 09.5.9:sistema",
        "hueco": "Goal 01 no inventarió corpus uno a uno; 09.5.4 ya terminalizó esos files y 10.8 no los reparsea",
    },
    {
        "file": "10.9_WEB_Y_ACTUALIDAD.md",
        "prev": "10.8_HECHOS_LOCALES.md",
        "next": "10.10_APPS_VENTANAS_VISION.md",
        "citation": "09.5.9:navegador, privacidad; invariante 6",
        "hueco": "",
    },
    {
        "file": "10.10_APPS_VENTANAS_VISION.md",
        "prev": "10.9_WEB_Y_ACTUALIDAD.md",
        "next": "10.11_AUDIO.md",
        "citation": "09.5.9:uia_ocr_vision, adapters_providers; qwen-vl rechazado",
        "hueco": "la cascada UIA→OCR→visión como política sigue siendo trabajo de producto; no se transplanta Qwen-VL",
    },
    {
        "file": "10.11_AUDIO.md",
        "prev": "10.10_APPS_VENTANAS_VISION.md",
        "next": "10.12_MEDIA_STREAMING_JUEGOS.md",
        "citation": "09.5.9:wake_word, stt, tts, vad, audio_ducking; 09.5.11C voice holdouts",
        "hueco": "",
    },
    {
        "file": "10.12_MEDIA_STREAMING_JUEGOS.md",
        "prev": "10.11_AUDIO.md",
        "next": "10.13_SISTEMA_CONECTIVIDAD.md",
        "citation": "09.5.9:steam_media; 09.5.11C steam físico = fixture",
        "hueco": "",
    },
    {
        "file": "10.13_SISTEMA_CONECTIVIDAD.md",
        "prev": "10.12_MEDIA_STREAMING_JUEGOS.md",
        "next": "10.14_PRODUCTIVIDAD_MEMORIA.md",
        "citation": "09.5.9:sistema, conectividad",
        "hueco": "",
    },
    {
        "file": "10.14_PRODUCTIVIDAD_MEMORIA.md",
        "prev": "10.13_SISTEMA_CONECTIVIDAD.md",
        "next": "10.15_COMUNICACION_NAVEGACION.md",
        "citation": "09.5.9:memoria_proactividad, archivos, journal",
        "hueco": "",
    },
    {
        "file": "10.15_COMUNICACION_NAVEGACION.md",
        "prev": "10.14_PRODUCTIVIDAD_MEMORIA.md",
        "next": "10.16_MISIONES_COMPUESTAS.md",
        "citation": "09.5.9:navegador, comunicacion",
        "hueco": "",
    },
    {
        "file": "10.16_MISIONES_COMPUESTAS.md",
        "prev": "10.15_COMUNICACION_NAVEGACION.md",
        "next": "10.17_IDENTIDAD_VIVA.md",
        "citation": "09.5.9:planes; 09.5.11C R6 6/6 orphan=0; microagentes no son segundo motor",
        "hueco": "",
    },
    {
        "file": "10.17_IDENTIDAD_VIVA.md",
        "prev": "10.16_MISIONES_COMPUESTAS.md",
        "next": "10.18_INTEGRACION.md",
        "citation": "09.5.9:field_ui_accesibilidad, confirmacion; 09.5.11B prosa 0/0",
        "hueco": "",
    },
    {
        "file": "10.18_INTEGRACION.md",
        "prev": "10.17_IDENTIDAD_VIVA.md",
        "next": "11.1_COLA_DE_CIERRE.md",
        "citation": "09.5.11A–C revalidación 01–09; transplant vacío",
        "hueco": "",
    },
    {
        "file": "11.1_COLA_DE_CIERRE.md",
        "prev": "10.18_INTEGRACION.md",
        "next": "11.2_CONTRATOS_RUNTIME.md",
        "citation": "09.5.9:catalogo_tipado; 09.5.12 no añade slices",
        "hueco": "",
    },
    {
        "file": "11.2_CONTRATOS_RUNTIME.md",
        "prev": "11.1_COLA_DE_CIERRE.md",
        "next": "11.3_REQUISITOS_A.md",
        "citation": "09.5.9:verificacion, catalogo_tipado",
        "hueco": "",
    },
    {
        "file": "11.3_REQUISITOS_A.md",
        "prev": "11.2_CONTRATOS_RUNTIME.md",
        "next": "11.4_REQUISITOS_B.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.4_REQUISITOS_B.md",
        "prev": "11.3_REQUISITOS_A.md",
        "next": "11.5_REQUISITOS_C.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.5_REQUISITOS_C.md",
        "prev": "11.4_REQUISITOS_B.md",
        "next": "11.6_REQUISITOS_D.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.6_REQUISITOS_D.md",
        "prev": "11.5_REQUISITOS_C.md",
        "next": "11.7_REQUISITOS_E.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.7_REQUISITOS_E.md",
        "prev": "11.6_REQUISITOS_D.md",
        "next": "11.8_REQUISITOS_F.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.8_REQUISITOS_F.md",
        "prev": "11.7_REQUISITOS_E.md",
        "next": "11.9_NO_RUNTIME_A.md",
        "citation": "09.5.12 overflow = checkpoints internos de 11.3–11.8; no slices nuevos",
        "hueco": "",
    },
    {
        "file": "11.9_NO_RUNTIME_A.md",
        "prev": "11.8_REQUISITOS_F.md",
        "next": "11.10_NO_RUNTIME_B.md",
        "citation": "09.5.12 K11 ≥2.036; overflow = checkpoints internos, no prompts nuevos",
        "hueco": "",
    },
    {
        "file": "11.10_NO_RUNTIME_B.md",
        "prev": "11.9_NO_RUNTIME_A.md",
        "next": "11.11_ERRORES_MENTE_KERNEL.md",
        "citation": "09.5.12 K11 ≥2.036; overflow = checkpoints internos, no prompts nuevos",
        "hueco": "",
    },
    {
        "file": "11.11_ERRORES_MENTE_KERNEL.md",
        "prev": "11.10_NO_RUNTIME_B.md",
        "next": "11.12_ERRORES_PROVIDERS_ESTADO.md",
        "citation": "09.5.9:confirmacion; auto_approve rechazado",
        "hueco": "",
    },
    {
        "file": "11.12_ERRORES_PROVIDERS_ESTADO.md",
        "prev": "11.11_ERRORES_MENTE_KERNEL.md",
        "next": "11.13_REGRESION_01_06.md",
        "citation": "09.5.9:adapters_providers, journal",
        "hueco": "",
    },
    {
        "file": "11.13_REGRESION_01_06.md",
        "prev": "11.12_ERRORES_PROVIDERS_ESTADO.md",
        "next": "11.14_REGRESION_07_10.md",
        "citation": "09.5.11A/B revalidación 01–06; no rederivar",
        "hueco": "",
    },
    {
        "file": "11.14_REGRESION_07_10.md",
        "prev": "11.13_REGRESION_01_06.md",
        "next": "11.15_HIGIENE_IDENTIDAD.md",
        "citation": "09.5.11C revalidación 07–09; no repetir 200 turnos",
        "hueco": "",
    },
    {
        "file": "11.15_HIGIENE_IDENTIDAD.md",
        "prev": "11.14_REGRESION_07_10.md",
        "next": "11.16_FULL_Y_CIERRE.md",
        "citation": "09.5.9:field_ui_accesibilidad; Identidad no se reescribe",
        "hueco": "",
    },
    {
        "file": "11.16_FULL_Y_CIERRE.md",
        "prev": "11.15_HIGIENE_IDENTIDAD.md",
        "next": "ninguno — BAXY listo para uso diario",
        "citation": "09.5.11C Full; 09.5.12 linaje cerrado",
        "hueco": "",
    },
)


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def report_path(repo: Path = REPO) -> Path:
    return repo / SYNTHESIS_REL


def load_report(repo: Path = REPO) -> dict[str, Any]:
    return load_json(report_path(repo))


def remaining_prompt_files() -> tuple[str, ...]:
    return EXECUTABLE_PROMPTS


def numbered_prompt_files(repo: Path) -> list[str]:
    sprints = repo / "documentacion" / "sprints"
    found: list[str] = []
    for path in sorted(sprints.glob("*.md")):
        if re.match(r"^(?:10|11)\.\d+", path.name):
            found.append(path.name)
    return found


def coverage_snapshot(repo: Path = REPO) -> dict[str, Any]:
    summary = load_json_docs(repo / QUEUE_SUMMARY_REL)
    queued = int(summary["queued"])
    duplicates = int(summary["duplicates"])
    prior = int(summary["prior_coverage"])
    manifest = int(summary["manifest_files"])
    missing = int(summary["missing"])
    overlaps = int(summary["overlaps"])
    covered = queued + duplicates + prior
    campaigns = {
        "docs": load_json_docs(repo / DOCS_CAMPAIGN_REL)["counts"],
        "code_tests": load_json_docs(repo / CODE_CAMPAIGN_REL)["counts"],
        "evidence_assets": load_json_docs(evidence_campaign_path(repo))["counts"],
        "transplant": load_transplant_campaign(repo)["counts"],
    }
    terminals = ledger_file_terminals(repo)
    hashes = reproduce_manifest_hashes(repo)
    coverage_pct = 0.0 if manifest == 0 else 100.0 * covered / manifest
    return {
        "queued": queued,
        "duplicates": duplicates,
        "prior_coverage": prior,
        "manifest_files": manifest,
        "missing": missing,
        "overlaps": overlaps,
        "covered": covered,
        "coverage_pct": coverage_pct,
        "campaigns": campaigns,
        "ledger_files": terminals["file_count"],
        "ledger_invalid_terminals": terminals["invalid"],
        "ledger_empty_terminals": terminals["empty"],
        "manifest_hashes": hashes,
        "transplant_empty_reason": str(
            load_transplant_campaign(repo).get("empty_reason") or ""
        ),
        "protected_rejects": list(PROTECTED_REJECTS),
    }


def ledger_file_terminals(repo: Path = REPO) -> dict[str, Any]:
    ledger_dir = repo / "artifacts" / "goal095" / "ledger"
    invalid: list[str] = []
    empty = 0
    file_count = 0
    seen_terminals: dict[str, int] = {}
    for path in sorted(ledger_dir.glob("*.json")):
        payload = load_json_docs(path)
        rows = payload.get("files")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            file_count += 1
            terminal = str(row.get("terminal") or "").strip()
            if not terminal:
                empty += 1
                invalid.append(f"{path.name}:empty")
                continue
            seen_terminals[terminal] = seen_terminals.get(terminal, 0) + 1
            if terminal not in ALLOWED_FILE_TERMINALS:
                invalid.append(f"{path.name}:{terminal}")
    return {
        "file_count": file_count,
        "invalid": invalid,
        "empty": empty,
        "by_terminal": seen_terminals,
    }


def reproduce_manifest_hashes(repo: Path = REPO) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for source_id, spec in FROZEN_0950.items():
        rel = spec.get("manifest_rel")
        if not rel:
            continue
        path = repo / rel
        actual = sha256_path(path) if path.is_file() else ""
        expected = str(spec["manifest_sha256"])
        out[source_id] = {
            "rel": _posix(str(rel)),
            "actual": actual,
            "expected": expected,
            "match": actual == expected and bool(actual),
        }
    return out


def campaign_queues_drained(snapshot: dict[str, Any]) -> bool:
    for counts in snapshot["campaigns"].values():
        if int(counts.get("pending") or 0) != 0:
            return False
        if int(counts.get("claimed") or 0) != 0:
            return False
    return True


def generate_lineage_appendix(repo: Path = REPO) -> str:
    snapshot = coverage_snapshot(repo)
    matrix = load_0959_matrix(repo)
    transplant = load_transplant_campaign(repo)
    decisions: dict[str, int] = {}
    rows: list[str] = []
    for item in matrix.get("responsibilities") or []:
        decision = str(item.get("decision") or "").strip()
        decisions[decision] = decisions.get(decision, 0) + 1
        ident = str(item.get("id") or "").strip()
        valor = str(item.get("valor_10_11") or "").strip()
        rows.append(f"| `{ident}` | `{decision}` | {valor} |")
    lots = list(transplant.get("lots") or [])
    lines = [
        "# Reconciliación 09.5 — linaje publicado",
        "",
        f"Generado por `scripts/goal095_09512_integrate.py` desde manifiestos y síntesis. "
        f"Goal 01 cerrado el **{GOAL01_CLOSED}**. No copia secretos, binarios ni corpus privados.",
        "",
        "## Las cuatro clases",
        "",
        "### Herencia previa",
        "",
        f"Fuentes ya contempladas el {GOAL01_CLOSED}: `Carter OS AI`, `Probando Gemma 4`, "
        "`FunctionGemma`, `BAXY`, biblioteca 1.350 documentos, mapa `00_MAPA.md` §1–§10. "
        "Schema Agent se audita en el historial Git de `BAXY`, no como carpeta hermana. "
        "`JRVS` y `Probando schemas` siguen fuera.",
        "",
        "### Delta nuevo",
        "",
        f"Manifiesto 09.5.1: {snapshot['manifest_files']} archivos hasheados; "
        f"cola {snapshot['queued']}; duplicados {snapshot['duplicates']}; "
        f"cobertura previa {snapshot['prior_coverage']}; faltantes {snapshot['missing']}; "
        f"solapes {snapshot['overlaps']}. Cobertura {snapshot['coverage_pct']:.0f} %.",
        "Llegó material intelectual adicional en los mismos árboles, la etapa Schema Agent "
        "dentro de `BAXY`, y la declaración de fuente dispersa (GGUF/datasets/checkpoints "
        "de Probando Gemma 4 omitidos a propósito; hashes individuales not invented).",
        "",
        "### Piezas trasplantadas",
        "",
        f"Cero lotes. `pending=0` `claimed=0` `complete={len(lots)}` `total={len(lots)}`. "
        "Decisión 09.5.9/10: `conservar_actual`. Un trasplante vacío es un hecho medido, "
        "no un hueco a rellenar.",
        "",
        str(snapshot["transplant_empty_reason"]).strip(),
        "",
        "### Rechazos",
        "",
        "Protegidos (no reentran): " + ", ".join(f"`{name}`" for name in PROTECTED_REJECTS) + ".",
        "",
        f"Decisiones 09.5.9 por terminal: {json.dumps(decisions, ensure_ascii=False)}.",
        "",
        "## Campañas",
        "",
        "| Campaña | pending | claimed | complete | total |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, counts in snapshot["campaigns"].items():
        lines.append(
            f"| `{name}` | {counts.get('pending', 0)} | {counts.get('claimed', 0)} | "
            f"{counts.get('complete', 0)} | {counts.get('total', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Hashes de manifiesto 09.5.0 (reproducibles)",
            "",
        ]
    )
    for source_id, rec in snapshot["manifest_hashes"].items():
        mark = "match" if rec["match"] else "MISMATCH"
        lines.append(f"- `{source_id}` `{rec['expected']}` ({mark})")
    lines.extend(
        [
            "",
            "## Tarjetas 09.5.9 → valor 10/11",
            "",
            "| Id | Decisión | valor_10_11 |",
            "|---|---|---|",
            *rows,
            "",
            "Las 9.268 tarjetas de auditoría 09.5.2–09.5.4 viven en "
            "`artifacts/goal095/ledger/` y "
            "`artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json`. "
            "No se copian árboles fuente, GGUF, datasets ni secretos a `biblioteca/`.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_mapa_section(repo: Path = REPO) -> str:
    appendix = generate_lineage_appendix(repo)
    return "\n".join(
        [
            '## 11. Reconciliación 09.5 <a id="11-reconciliacion-095"></a>',
            "",
            f"Actualización **09.5.12**, cerrada 2026-08-31. No borra las fechas ni las "
            f"conclusiones del Goal 01 (**{GOAL01_CLOSED}**): §1–§10 siguen siendo el mapa "
            "que los Goals 02–09 leyeron. Este apartado nombra las cuatro clases del linaje "
            "reconciliado: herencia previa, delta nuevo, piezas trasplantadas (cero lotes) "
            "y rechazos.",
            "",
            appendix,
            "",
            "Huecos del Goal 01 §10 que 09.5 cubrió sin reescribirlos: corpus y assets "
            "tienen terminal 09.5.4 (`parseado_completo` / `binario_inventariado` / "
            "`excluido_razonado`); `carter_v5` se leyó en la campaña `docs`/`code_tests`; "
            "el planner FunctionGemma sigue rechazado. Lo que sigue siendo medición de "
            "producto (unload-on-idle, arranque frío, cascada de visión como política, "
            "200 turnos) no se convierte en lote de trasplante.",
            "",
        ]
    )


def upsert_generated_section(path: Path, body: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = f"{GENERATED_BEGIN}\n{body.rstrip()}\n{GENERATED_END}\n"
    if GENERATED_BEGIN in text and GENERATED_END in text:
        pre, rest = text.split(GENERATED_BEGIN, 1)
        _, post = rest.split(GENERATED_END, 1)
        path.write_text(
            pre.rstrip() + "\n\n" + block + post.lstrip("\n"),
            encoding="utf-8",
            newline="\n",
        )
        return
    path.write_text(
        text.rstrip() + "\n\n" + block,
        encoding="utf-8",
        newline="\n",
    )


def heritage_block(spec: dict[str, str]) -> str:
    hueco = str(spec.get("hueco") or "").strip()
    hueco_line = (
        f"Hueco probado: {hueco}."
        if hueco
        else "Hueco probado: ninguno en este owner; hereda la pieza citada y no la reconstruye."
    )
    return "\n".join(
        [
            HERITAGE_HEADING,
            "",
            f"Cita: `{spec['citation']}`.",
            "Campaña `transplant` vacía (`conservar_actual`, cero lotes): no retires el "
            "mecanismo vivo ni construyas una segunda vía.",
            hueco_line,
            "Rechazos protegidos que no reentran: `functiongemma-270m-ft`, `qwen-vl`, "
            "`ollama-runtime`, `auto_approve`, `soak-24h-as-requirement`, `gemma-native-audio`.",
            "",
            CONTRATO_HEADING,
            "",
            f"Dependencia: `{spec['prev']}`. Siguiente: `{spec['next']}`.",
            "Presupuesto: ventana de trabajo <500k tokens; compacta y continúa en esta meta.",
            "Ambiente: `FALLO_DE_AMBIENTE` pausa esta meta; no skip ni pass ambiental.",
            "Barras que no se rebajan: 200 turnos, 1.947/808, 2.036 contratos, Identidad, Full.",
            "Idioma: sólo ES/EN/spanglish.",
            "",
        ]
    )


def upsert_prompt_heritage(text: str, spec: dict[str, str]) -> str:
    block = heritage_block(spec).rstrip() + "\n\n"
    if HERITAGE_HEADING in text and OBJETIVO_HEADING in text:
        pre, rest = text.split(HERITAGE_HEADING, 1)
        _, post = rest.split(OBJETIVO_HEADING, 1)
        return pre.rstrip() + "\n\n" + block + OBJETIVO_HEADING + post
    if OBJETIVO_HEADING not in text:
        return text.rstrip() + "\n\n" + block
    pre, post = text.split(OBJETIVO_HEADING, 1)
    return pre.rstrip() + "\n\n" + block + OBJETIVO_HEADING + post


def apply_prompt_heritage(repo: Path = REPO) -> list[str]:
    written: list[str] = []
    sprints = repo / "documentacion" / "sprints"
    for spec in PROMPT_SPECS:
        path = sprints / spec["file"]
        original = path.read_text(encoding="utf-8")
        updated = upsert_prompt_heritage(original, spec)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            written.append(spec["file"])
    return written


def parse_orden_executable(repo: Path = REPO) -> list[str]:
    text = (repo / ORDEN_REL).read_text(encoding="utf-8")
    if EXECUTABLE_MARK not in text:
        return []
    section = text.split(EXECUTABLE_MARK, 1)[1]
    nxt = section.find("\n## ")
    if nxt != -1:
        section = section[:nxt]
    files: list[str] = []
    for match in ORDEN_LINK_RE.finditer(section):
        href = match.group(1).split("#", 1)[0].strip()
        name = Path(href).name
        if name:
            files.append(name)
    return files


def local_link_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for match in LINK_RE.finditer(text):
        href = match.group(1).strip()
        if href.startswith("<"):
            href = href[1:]
        href = href.split()[0].strip("<>")
        target, _, _anchor = href.partition("#")
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"{path.name} broken link {target}")
    return errors


def validate_prompts(repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    sprints = repo / "documentacion" / "sprints"
    seen: list[str] = []
    numbered = numbered_prompt_files(repo)
    expected = sorted((*EXECUTABLE_PROMPTS, *RETIRED_PROMPTS))
    if numbered != sorted(expected):
        extra = sorted(set(numbered) - set(expected))
        missing = sorted(set(expected) - set(numbered))
        if extra:
            errors.append(f"extra numbered prompts the owner would launch: {extra}")
        if missing:
            errors.append(f"missing numbered prompts: {missing}")
    for spec in PROMPT_SPECS:
        rel = spec["file"]
        seen.append(rel)
        path = sprints / rel
        if not path.is_file():
            errors.append(f"missing prompt {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if rel.startswith("10.") and rel not in {
            "10.0_BASE_VERDE.md",
            "10.1_CORPUS_Y_COLA.md",
            "10.2_PRESENCIA_Y_RECURSOS.md",
            "10.2.5_RECURSOS_EN_REPOSO.md",
        } and GROK46_CONTRACT_MARK not in text:
            errors.append(f"{rel} missing embedded Grok 4.6 goal contract")
        if rel.startswith("11.") and GROK46_CONTRACT_MARK not in text:
            errors.append(f"{rel} missing embedded Grok 4.6 goal contract")
        if OBJETIVO_HEADING not in text:
            errors.append(f"{rel} missing {OBJETIVO_HEADING}")
        if CRITERIOS_HEADING not in text:
            errors.append(f"{rel} missing {CRITERIOS_HEADING}")
        if HERITAGE_HEADING not in text:
            errors.append(f"{rel} missing {HERITAGE_HEADING}")
        if CONTRATO_HEADING not in text:
            errors.append(f"{rel} missing {CONTRATO_HEADING}")
        if spec["citation"] not in text:
            errors.append(f"{rel} missing citation {spec['citation']}")
        hueco = str(spec.get("hueco") or "").strip()
        if hueco:
            if "Hueco probado:" not in text or hueco not in text:
                errors.append(f"{rel} missing hueco probado")
        elif "Hueco probado: ninguno" not in text and "hueco probado" not in text.casefold():
            errors.append(f"{rel} missing hueco-probado declaration")
        for bar in BARS_LITERAL:
            if bar not in text:
                errors.append(f"{rel} missing bar {bar}")
        if spec["next"] not in text:
            errors.append(f"{rel} missing next {spec['next']}")
        if spec["prev"] not in text:
            errors.append(f"{rel} missing dependency {spec['prev']}")
        lowered = text.casefold()
        if "menos de 200" in lowered or "199 turnos" in lowered:
            errors.append(f"{rel} lowers 200 turnos")
        if "1.946" in text or "807 misiones" in lowered:
            errors.append(f"{rel} lowers 1.947/808")
        if "2.035" in text:
            errors.append(f"{rel} lowers 2.036")
        errors.extend(local_link_errors(path, text))
    if seen != [item["file"] for item in PROMPT_SPECS]:
        errors.append("PROMPT_SPECS order drifted")
    if len(seen) != len(set(seen)):
        errors.append("duplicate prompt specs")
    for rel in RETIRED_PROMPTS:
        text = (sprints / rel).read_text(encoding="utf-8")
        if "NO LANZAR" not in text or "10_REPLANIFICACION_AUTONOMA.md" not in text:
            errors.append(f"{rel} is not an explicit retired tombstone")
    return errors


def validate_map_classes(repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    mapa = (repo / MAPA_REL).read_text(encoding="utf-8")
    indice = (repo / BIBLIOTECA_INDICE_REL).read_text(encoding="utf-8")
    inventario = (repo / BIBLIOTECA_INV_REL).read_text(encoding="utf-8")
    if GOAL01_CLOSED not in mapa:
        errors.append("00_MAPA.md lost Goal 01 date")
    if "1.350" not in indice and "1350" not in indice:
        errors.append("biblioteca/00_INDICE.md lost 1350 count")
    for label in FOUR_CLASSES:
        hits = 0
        for doc in (mapa, indice, inventario):
            if label in doc.casefold():
                hits += 1
        if hits == 0:
            errors.append(f"four-class label missing everywhere: {label}")
        if label not in mapa.casefold():
            errors.append(f"00_MAPA.md missing class {label}")
    if "cero lote" not in mapa.casefold() and "cero trasplante" not in mapa.casefold():
        errors.append("00_MAPA.md does not record empty transplant")
    return errors


def validate_biblioteca_clean(repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    root = repo / "biblioteca"
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = _posix(str(path.relative_to(root)))
        suffix = path.suffix.casefold()
        if suffix in FORBIDDEN_BIBLIOTECA_SUFFIXES:
            errors.append(f"biblioteca tracks forbidden suffix {rel}")
        folded = f"/{rel.casefold()}"
        for part in FORBIDDEN_BIBLIOTECA_PARTS:
            if part.casefold() in folded:
                errors.append(f"biblioteca tracks forbidden path {rel}")
    appendix = generate_lineage_appendix(repo)
    if ".gguf" in appendix and "GGUF" not in appendix:
        errors.append("appendix copied gguf blob path")
    return errors


def validate_orden(repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    files = parse_orden_executable(repo)
    expected = list(EXECUTABLE_PROMPTS)
    if files != expected:
        errors.append(
            "00_ORDEN executable list mismatch: "
            f"got {files!r} expected {expected!r}"
        )
    if len(files) != len(set(files)):
        errors.append("00_ORDEN has duplicate executable prompts")
    text = (repo / ORDEN_REL).read_text(encoding="utf-8")
    if "10.0_BASE_VERDE.md" not in text:
        errors.append("00_ORDEN does not name 10.0")
    if "siguiente" in text.casefold() and "10.0" not in text:
        errors.append("00_ORDEN next is not 10.0")
    if OWNER_PROMPT.split("/")[-1] in files:
        errors.append("00_ORDEN still lists 09.5.12 as remaining executable")
    errors.extend(local_link_errors(repo / ORDEN_REL, text))
    return errors


def validate_report(report: dict[str, Any], repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    if report.get("version") != VERSION:
        errors.append("version mismatch")
    if report.get("owner_prompt") != OWNER_PROMPT:
        errors.append("owner_prompt mismatch")
    nxt = str(report.get("next_human_prompt") or "")
    if nxt != NEXT_PROMPT:
        errors.append(f"next_human_prompt {nxt!r} != {NEXT_PROMPT!r}")
    if OWNER_PROMPT in nxt or "09.5.12" in nxt:
        errors.append("09.5.12 names itself as next")
    snapshot = coverage_snapshot(repo)
    if abs(float(snapshot["coverage_pct"]) - 100.0) > 1e-9:
        errors.append(f"coverage {snapshot['coverage_pct']} != 100")
    if snapshot["missing"] != 0 or snapshot["overlaps"] != 0:
        errors.append("manifest missing or overlaps")
    if snapshot["covered"] != snapshot["manifest_files"]:
        errors.append("covered != manifest_files")
    if not campaign_queues_drained(snapshot):
        errors.append("campaign queues not drained")
    if snapshot["ledger_invalid_terminals"] or snapshot["ledger_empty_terminals"]:
        errors.append("invalid or empty file terminals")
    if snapshot["ledger_files"] <= 0:
        errors.append("no ledger files walked")
    for rec in snapshot["manifest_hashes"].values():
        if not rec["match"]:
            errors.append(f"manifest hash mismatch {rec['rel']}")
    if not str(snapshot["transplant_empty_reason"]).strip():
        errors.append("empty transplant without reason")
    errors.extend(validate_prompts(repo))
    errors.extend(validate_map_classes(repo))
    errors.extend(validate_orden(repo))
    errors.extend(validate_biblioteca_clean(repo))
    a = generate_lineage_appendix(repo)
    b = generate_lineage_appendix(repo)
    if hashlib.sha256(a.encode("utf-8")).digest() != hashlib.sha256(b.encode("utf-8")).digest():
        errors.append("lineage appendix not reproducible")
    indice = (repo / BIBLIOTECA_INDICE_REL).read_text(encoding="utf-8")
    inventario = (repo / BIBLIOTECA_INV_REL).read_text(encoding="utf-8")
    mapa = (repo / MAPA_REL).read_text(encoding="utf-8")
    for label in FOUR_CLASSES:
        if label not in inventario.casefold() and GENERATED_BEGIN not in inventario:
            errors.append("01_INVENTARIO.md missing generated lineage")
            break
    if GENERATED_BEGIN not in indice or GENERATED_END not in indice:
        errors.append("biblioteca/00_INDICE.md missing generated markers")
    if GENERATED_BEGIN not in mapa or GENERATED_END not in mapa:
        errors.append("00_MAPA.md missing generated markers")
    if GENERATED_BEGIN not in inventario or GENERATED_END not in inventario:
        errors.append("01_INVENTARIO.md missing generated markers")
    validacion = (repo / VALIDACION_REL).read_text(encoding="utf-8")
    if "añade slices si hacen falta" in validacion:
        errors.append("11_VALIDACION.md still says 09.5.12 adds slices")
    if "no añade slices" not in validacion.casefold() and "checkpoints internos" not in validacion.casefold():
        errors.append("11_VALIDACION.md does not record internal checkpoints")
    return errors


def build_report(
    repo: Path,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    snapshot = coverage_snapshot(repo)
    matrix = load_0959_matrix(repo)
    decisions: dict[str, int] = {}
    for item in matrix.get("responsibilities") or []:
        decision = str(item.get("decision") or "").strip()
        decisions[decision] = decisions.get(decision, 0) + 1
    appendix = generate_lineage_appendix(repo)
    appendix_sha = hashlib.sha256(appendix.encode("utf-8")).hexdigest()
    prompt_errors = validate_prompts(repo)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "goal": "09.5.12",
        "closed_utc": closed_utc,
        "owner_prompt": OWNER_PROMPT,
        "next_human_prompt": NEXT_PROMPT,
        "coverage": {
            "percent": snapshot["coverage_pct"],
            "manifest_files": snapshot["manifest_files"],
            "queued": snapshot["queued"],
            "duplicates": snapshot["duplicates"],
            "prior_coverage": snapshot["prior_coverage"],
            "covered": snapshot["covered"],
            "missing": snapshot["missing"],
            "overlaps": snapshot["overlaps"],
            "ledger_files": snapshot["ledger_files"],
            "terminals": snapshot["ledger_invalid_terminals"] == []
            and snapshot["ledger_empty_terminals"] == 0,
        },
        "campaigns": snapshot["campaigns"],
        "transplant": {
            "lots": 0,
            "empty_reason": snapshot["transplant_empty_reason"],
            "protected_rejects": snapshot["protected_rejects"],
        },
        "decisions": decisions,
        "four_classes": list(FOUR_CLASSES),
        "manifest_hashes": snapshot["manifest_hashes"],
        "appendix_sha256": appendix_sha,
        "executable_prompts": list(EXECUTABLE_PROMPTS),
        "orden": parse_orden_executable(repo),
        "prompt_errors": prompt_errors,
        "reproducibility": reproducibility,
        "languages_in_scope": ["es", "en", "spanglish"],
        "bars": {
            "200_turnos": True,
            "n10_m10_min": "1.947/808",
            "k11_min": 2036,
            "identidad": True,
            "full": True,
            "ambiente": "FALLO_DE_AMBIENTE",
            "window": "500k",
        },
        "slices_added": 0,
        "enabled_next": NEXT_PROMPT,
    }


def render_markdown(report: dict[str, Any]) -> str:
    cov = report["coverage"]
    return "\n".join(
        [
            "# Goal 09.5.12 — Integrar herencia y replanificar 10–11",
            "",
            f"Cerrado {report['closed_utc'][:10]}. Fuente de verdad machine-readable:",
            f"[`../../{SYNTHESIS_REL}`](../../{SYNTHESIS_REL}).",
            f"Ledger: [`../../{LEDGER_REL}`](../../{LEDGER_REL}).",
            "",
            "Siguiente prompt humano:",
            "[`../sprints/10.0_BASE_VERDE.md`](../sprints/10.0_BASE_VERDE.md).",
            "No remite a 09.5.12 ni a 09.5.11C.",
            "",
            "## Cobertura",
            "",
            f"{cov['percent']:.0f} % del manifiesto ({cov['manifest_files']} "
            f"archivos; cubiertos {cov['covered']}). Faltantes {cov['missing']}, "
            f"solapes {cov['overlaps']}. Ledgers: {cov['ledger_files']} files con "
            "terminales permitidos.",
            "",
            "## Cuatro clases",
            "",
            "- Herencia previa: Goal 01 (" + GOAL01_CLOSED + ").",
            "- Delta nuevo: manifiesto 09.5.1 y fuentes dispersas declaradas.",
            "- Piezas trasplantadas: cero lotes (`conservar_actual`).",
            "- Rechazos: " + ", ".join(f"`{name}`" for name in PROTECTED_REJECTS) + ".",
            "",
            "## 10.x / 11.x",
            "",
            "Cero prompts o slices nuevos. Delta 09.5 va a checkpoints internos. "
            "Barras intactas: 200 turnos, 1.947/808, 2.036 contratos, ambiente, Identidad, Full. "
            "Ventana <500k. Sólo ES/EN/spanglish.",
            "",
            f"`00_ORDEN_DESDE_09_5.md` ejecutable restante: {len(report['executable_prompts'])} "
            "ficheros, 10.0 primero.",
            "",
            "## Reproducibilidad",
            "",
            f"`{report['reproducibility'].get('command')}` → "
            f"{report['reproducibility'].get('result')}",
            "",
        ]
    )


def render_handoff(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Handoff — 09.5.12 integrar y replanificar 10–11 — 2026-08-31",
            "",
            "## Objetivo",
            "Publicar el mapa del linaje reconciliado y hacer que cada 10.x/11.x herede antes de construir.",
            "",
            "## Estado",
            "Hecho: cobertura 100 %, colas vacías, transplant=0, prompts 10.0–10.18 y 11.1–11.16 citan herencia, "
            "00_ORDEN = ejecutable restante, 10.0 habilitado.",
            "En curso: nada. Sin empezar: 10.0 (no se ejecuta en esta meta).",
            "",
            "## Decisiones tomadas",
            "- Cero trasplantes es un hecho 09.5.9/10 (`conservar_actual`), no un hueco a rellenar.",
            "- 11_VALIDACION.md no añade slices; overflow = checkpoints internos de 11.3–11.8.",
            "- Barras 200 turnos, 1.947/808, 2.036, ambiente, Identidad y Full no se rebajan.",
            "- Biblioteca se regenera desde manifiestos; no se copian secretos/binarios/corpus.",
            "",
            "## Archivos tocados",
            f"- `{SYNTHESIS_REL}` — cierre machine-readable",
            f"- `{MARKDOWN_REL}` — síntesis humana",
            "- `biblioteca/00_INDICE.md`, `biblioteca/01_INVENTARIO.md`, `documentacion/herencia/00_MAPA.md`",
            "- `documentacion/sprints/10.0`–`10.18`, `11.1`–`11.16`, `00_ORDEN_DESDE_09_5.md`",
            "- `tests/test_goal095_09512_integrate.py`, `scripts/goal095_09512_integrate.py`",
            "",
            "## Archivos relevantes aun sin tocar",
            "- `documentacion/sprints/10.0_BASE_VERDE.md` — siguiente lanzamiento, no ejecutado aquí",
            "",
            "## Hipotesis",
            "Confirmadas: cola transplant vacía; 09.5.11A–C verdes; cobertura queued+dup+prior=manifiesto.",
            "Descartadas: «09.5.12 añade slices»; «hay que inventar trasplantes para llenar la clase».",
            "",
            "## Comandos ejecutados y resultado",
            f"- `{report['reproducibility'].get('command')}` → {report['reproducibility'].get('result')}",
            "",
            "## Problemas pendientes",
            "Ninguno de 09.5.12. No ejecutar 10.0 en esta meta.",
            "",
            "## Siguiente accion recomendada",
            "`documentacion/sprints/10.0_BASE_VERDE.md` (sesión nueva, un pegado).",
            "",
        ]
    )


def apply_generated_docs(repo: Path = REPO) -> None:
    appendix = generate_lineage_appendix(repo)
    upsert_generated_section(repo / BIBLIOTECA_INDICE_REL, appendix)
    upsert_generated_section(repo / BIBLIOTECA_INV_REL, appendix)
    upsert_generated_section(repo / MAPA_REL, generate_mapa_section(repo))


def close_campaign(
    repo: Path,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    apply_prompt_heritage(repo)
    apply_generated_docs(repo)
    report = build_report(repo, closed_utc=closed_utc, reproducibility=reproducibility)
    errors = validate_report(report, repo=repo)
    report["errors"] = errors
    dump_json(repo / SYNTHESIS_REL, report)
    dump_json(
        repo / LEDGER_REL,
        {
            "schema": LEDGER_SCHEMA,
            "goal": "09.5.12",
            "closed_utc": closed_utc,
            "next_human_prompt": NEXT_PROMPT,
            "owner_prompt": OWNER_PROMPT,
            "full_gate": reproducibility,
            "coverage_pct": report["coverage"]["percent"],
            "errors": errors,
        },
    )
    (repo / MARKDOWN_REL).write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    (repo / HANDOFF_REL).write_text(
        render_handoff(report), encoding="utf-8", newline="\n"
    )
    return {
        "errors": errors,
        "next_human_prompt": NEXT_PROMPT,
        "coverage_pct": report["coverage"]["percent"],
        "synthesis": SYNTHESIS_REL,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Close Goal 09.5.12 lineage integration")
    parser.add_argument("--reproducibility-result", required=True)
    parser.add_argument(
        "--reproducibility-command",
        default=".\\scripts\\test_source_quality.ps1 -Mode Full",
    )
    parser.add_argument("--reproducibility-passed", action="store_true")
    arguments = parser.parse_args()
    closed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = close_campaign(
        REPO,
        closed_utc=closed_utc,
        reproducibility={
            "command": arguments.reproducibility_command,
            "result": arguments.reproducibility_result,
            "passed": bool(arguments.reproducibility_passed),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
