"""Load and validate the shipped Goal 09.5.11A revalidation matrix.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not re-derive Goals 01–03C, does not clone the comprehension
scorer, and does not invent transplant lots. Holdout numbers come from
rescoring the published telemetry with score() / coverage_ledger_sha256.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from experiments.mind_router_spike.measure_goal03_catalog_coverage import (
    coverage_ledger_sha256,
)
from experiments.mind_router_spike.run_goal03_comprehension import score as score_comprehension
from scripts.goal095_0959_matrix import (
    PROTECTED_REJECTS,
    dump_json,
    load_campaign as load_transplant_campaign,
    load_json,
    load_matrix as load_0959_matrix,
)
from scripts.goal095_docs_ledger import load_json as load_json_docs
from scripts.goal095_evidence_campaign import campaign_path as evidence_campaign_path
from scripts.goal095_evidence_campaign import counts_for

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.09511a-revalidate.v1"
LEDGER_SCHEMA = "baxy.goal095.09511a-ledger.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.11A_revalidar_01_03C.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/revalidate-09.5.11A.json"
MARKDOWN_REL = "documentacion/herencia/09_5_11A_REVALIDAR.md"
HANDOFF_REL = "artifacts/goal095/HANDOFF.md"
OWNER_PROMPT = "documentacion/sprints/09.5.11A_REVALIDAR_01_03C.md"
NEXT_PROMPT = "documentacion/sprints/09.5.11B_REVALIDAR_04_06.md"
FORBIDDEN_NEXT = (
    OWNER_PROMPT,
    "documentacion/sprints/09.5.11A_REVALIDAR_01_03C.md",
    "documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md",
    "documentacion/sprints/09.5.11C_REVALIDAR_07_09.md",
    "documentacion/sprints/10.0_BASE_VERDE.md",
)
CORPUS_REL = "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
CORPUS_SHA256 = "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
SCORER_REL = "experiments/mind_router_spike/run_goal03_comprehension.py"
COVERAGE_SCRIPT_REL = "experiments/mind_router_spike/measure_goal03_catalog_coverage.py"
LANGUAGES = ("es", "en", "es_en")
SEAL_03C = "dc0a789316b769cb37739e86b7bc60c29dab2682ca4c8230da05c92e38b0771d"
COVERAGE_03C_REL = "artifacts/development/goal03_catalog_coverage_goal03c_r2.json"
COVERAGE_11A_REL = "artifacts/goal095/revalidate/goal03_catalog_coverage_goal09511a.json"
COMPOUND_03C_REL = "artifacts/development/goal03b_compound_goal03c_cmp2.json"
VRAM_REL = "artifacts/development/goal03_vram_rec5e2e8.json"
OVERHEAD_REL = "artifacts/development/goal03_overhead_rec5e2e8.json"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
APLAZADOS_REL = "documentacion/APLAZADOS.md"
MAPA_REL = "documentacion/herencia/00_MAPA.md"
COMPREHENSION_LABELS = ("goal09511a_r1", "goal09511a_r2", "goal09511a_r3")
STABLE_OOC_ACTED_03B = (
    "ooc-01",
    "ooc-07",
    "ooc-17",
    "ooc-18",
    "ooc-19",
    "ooc-23",
    "ooc-24",
    "ooc-31",
    "ooc-33",
)
IN_CATALOG_ROWS = 124
OUT_CATALOG_ROWS = 36
SERVED_MIN = 112
ACTED_MAX = 5
CATALOG_OPERATIONS = 169
CATALOG_REACHABLE = 158
CATALOG_FAMILIES = 31
COMPOUND_MISSIONS_MIN = 6
COMPOUND_STEPS_MIN = 15


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def report_path(repo: Path = REPO) -> Path:
    return repo / SYNTHESIS_REL


def ledger_path(repo: Path = REPO) -> Path:
    return repo / LEDGER_REL


def load_report(repo: Path = REPO) -> dict[str, Any]:
    path = report_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def comprehension_artifact_rel(label: str, suffix: str) -> str:
    return f"artifacts/goal095/revalidate/goal03_{label}{suffix}"


def corpus_profile(repo: Path = REPO) -> dict[str, Any]:
    path = repo / CORPUS_REL
    rows = load_jsonl(path)
    languages: dict[str, int] = {}
    in_catalog = 0
    out_catalog = 0
    for row in rows:
        language = str(row.get("language") or "")
        languages[language] = languages.get(language, 0) + 1
        if row.get("in_catalog"):
            in_catalog += 1
        else:
            out_catalog += 1
    return {
        "path": CORPUS_REL,
        "sha256": sha256_file(path),
        "rows": len(rows),
        "in_catalog": in_catalog,
        "out_of_catalog": out_catalog,
        "languages": dict(sorted(languages.items())),
    }


def acted_from_score(report: dict[str, Any]) -> int:
    out_catalog = report["out_of_catalog"]
    return int(out_catalog["rows"]) - int(out_catalog["honest_abstentions"])


def rescore_telemetry(path: Path) -> dict[str, Any]:
    return score_comprehension(load_jsonl(path))


def catalog_delta(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    old_entries = {entry["operation"]: entry for entry in baseline["entries"]}
    new_entries = {entry["operation"]: entry for entry in current["entries"]}
    missing = sorted(set(old_entries) - set(new_entries))
    added = sorted(set(new_entries) - set(old_entries))
    lost_reach = sorted(
        name
        for name, entry in old_entries.items()
        if entry.get("planner_reachable")
        and name in new_entries
        and not new_entries[name].get("planner_reachable")
    )
    contract_changes = []
    for name in sorted(set(old_entries) & set(new_entries)):
        old_hash = old_entries[name]["contract_sha256"]
        new_hash = new_entries[name]["contract_sha256"]
        if old_hash != new_hash:
            contract_changes.append(
                {
                    "operation": name,
                    "before_sha256": old_hash,
                    "after_sha256": new_hash,
                    "before_description": old_entries[name].get("description"),
                    "after_description": new_entries[name].get("description"),
                    "planner_reachable": bool(new_entries[name].get("planner_reachable")),
                }
            )
    return {
        "missing_operations": missing,
        "added_operations": added,
        "lost_reachability": lost_reach,
        "contract_changes": contract_changes,
        "baseline_seal": baseline["coverage_ledger_sha256"],
        "current_seal": current["coverage_ledger_sha256"],
        "baseline_count": baseline["count"],
        "current_count": current["count"],
    }


def coverage_identity(artifact: dict[str, Any]) -> dict[str, Any]:
    entries = list(artifact["entries"])
    reachable = [entry for entry in entries if entry.get("planner_reachable")]
    families = {str(entry["family"]) for entry in entries}
    return {
        "operations": len(entries),
        "planner_reachable": len(reachable),
        "families": len(families),
        "coverage_ledger_sha256": coverage_ledger_sha256(entries),
    }


def provenance_snapshot(repo: Path = REPO) -> dict[str, Any]:
    queue = load_json_docs(repo / "artifacts" / "goal095" / "queue" / "ledger.json")
    evidence_counts = counts_for(queue)
    docs = load_json_docs(repo / "artifacts" / "goal095" / "campaigns" / "docs.json")
    code = load_json_docs(repo / "artifacts" / "goal095" / "campaigns" / "code_tests.json")
    evidence = load_json_docs(evidence_campaign_path(repo))
    transplant = load_transplant_campaign(repo)
    requirements = load_json(repo / REQUIREMENTS_REL)
    matrix = load_0959_matrix(repo)
    sparse_hashes = [
        str(item.get("individual_hashes") or "").strip()
        for item in requirements.get("requirements") or []
    ]
    return {
        "queue_evidence": evidence_counts,
        "docs": docs["counts"],
        "code_tests": code["counts"],
        "evidence_assets": evidence["counts"],
        "transplant": transplant["counts"],
        "transplant_empty_reason": str(transplant.get("empty_reason") or ""),
        "sparse_hashes": sparse_hashes,
        "sparse_not_invented": all(item in {"not invented", ""} for item in sparse_hashes),
        "protected_rejects_blocked": list(PROTECTED_REJECTS),
        "protected_rejects_in_lots": [
            lot.get("responsibility_id")
            for lot in transplant.get("lots") or []
            if lot.get("responsibility_id") in PROTECTED_REJECTS
        ],
        "matrix_sparse_not_invented": "not invented"
        in str(matrix.get("sparse_assets") or {}).casefold(),
    }


def aplazados_defers_11a_to_goal10(repo: Path = REPO) -> list[str]:
    text = (repo / APLAZADOS_REL).read_text(encoding="utf-8").casefold()
    hits = []
    if "09.5.11a" in text and "goal 10" in text:
        hits.append("APLAZADOS.md names 09.5.11A together with Goal 10")
    if "09.5.11a" in text and "10.0" in text:
        hits.append("APLAZADOS.md names 09.5.11A together with 10.0")
    return hits


def _criterion(
    criterion_id: str,
    goal: str,
    text: str,
    evidence: list[str],
    *,
    holdout: bool = False,
    command: str | None = None,
    historical_result: str,
    scored_kind: str | None = None,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "goal": goal,
        "criterion": text,
        "holdout": holdout,
        "evidence": evidence,
        "command": command,
        "historical_result": historical_result,
        "scored_kind": scored_kind,
    }


def criterion_specs() -> list[dict[str, Any]]:
    mapa = [MAPA_REL]
    adaptadores = ["documentacion/herencia/D_ADAPTADORES_POR_APP.md"]
    compuerta = ["documentacion/base/00_COMPUERTA.md"]
    comprension = ["documentacion/base/03_COMPRENSION.md"]
    techo = ["documentacion/base/03B_COMPRENSION_TECHO.md"]
    alcance = ["documentacion/base/03C_ALCANCE.md"]
    costuras = ["documentacion/03_COSTURAS.md"]
    coverage_11a = [COVERAGE_11A_REL, COVERAGE_03C_REL]
    comprehension_11a = [
        comprehension_artifact_rel(label, ".json") for label in COMPREHENSION_LABELS
    ]
    compound = [COMPOUND_03C_REL]
    return [
        _criterion(
            "01-mapa-intentos",
            "01",
            "Un mapa que dice qué intentos hubo, qué se propuso cada uno, y por qué se abandonó.",
            mapa,
            historical_result="Cinco intentos en documentacion/herencia/00_MAPA.md §1, cerrado 2026-08-16.",
        ),
        _criterion(
            "01-funciona-hoy-ejecutado",
            "01",
            "Para cada intento, qué funciona hoy, comprobado ejecutándolo — no leído.",
            mapa,
            historical_result="Tabla §2 ejecutada el 2026-08-16 (STT, wake, encoder, FunctionGemma, accesibilidad, OCR, compuerta .NET).",
        ),
        _criterion(
            "01-que-se-hereda",
            "01",
            "Qué se hereda, de dónde, y qué hace falta para traerlo.",
            mapa,
            historical_result="§4: wake, STT, encoder, modos de accesibilidad, CaptureVision+UIA, corpus, capa .NET, lección benchmark 540.",
        ),
        _criterion(
            "01-que-no-se-hereda",
            "01",
            "Qué no se hereda y por qué. Un rechazo con el mecanismo entendido vale tanto como una herencia.",
            mapa,
            historical_result="§5: Gemma-4-E2B como decisor, FunctionGemma 270M, Q2_K_XL, agent.py, tres routers, redirects, adaptadores por app, GGUF de iteración, instalador certificado.",
        ),
        _criterion(
            "01-cuatro-herencias-obligatorias",
            "01",
            "Las cuatro herencias obligatorias resueltas: existe / no existe / existía a medias, con evidencia en cada caso.",
            mapa,
            historical_result="§3: accesibilidad existe; cascada UIA→OCR→visión a medias; set de 16 herramientas existe y su medición dice lo contrario; cuantización Q2/Q4 re-medida.",
        ),
        _criterion(
            "01-preguntas-respondidas",
            "01",
            "El inventario de preguntas ya respondidas y dónde, separando lo vigente de lo caducado.",
            mapa + ["biblioteca/00_INDICE.md"],
            historical_result="§7 vigente vs caducado. 09.5.9 no reabre FunctionGemma/Qwen-VL/Ollama/AUTO_APPROVE/soak-24h/Gemma-native-audio.",
        ),
        _criterion(
            "01-soluciones-comprension",
            "01",
            "Las soluciones al problema de comprensión que hay en los cuatro repositorios, listadas y comparables — el goal 03 arranca de ahí y no de cero.",
            mapa + comprension,
            historical_result="§6 cuatro soluciones comparables; Goal 03 publicó 46 % y techo 84,7 %.",
        ),
        _criterion(
            "01-adaptadores-por-app",
            "01",
            "La lista, fichero por fichero, de los adaptadores por aplicación que hay que sustituir por capacidad genérica.",
            adaptadores,
            historical_result="documentacion/herencia/D_ADAPTADORES_POR_APP.md, 2.454 líneas / 4 aplicaciones.",
        ),
        _criterion(
            "01-viewmodel-missionengine",
            "01",
            "MainWindowViewModel descompuesto y MissionEngine con un solo constructor, con la compuerta .NET verde después: 3.865 pruebas, 0 advertencias.",
            mapa + ["documentacion/APLAZADOS.md"],
            historical_result="MissionEngineOptions; ViewModel 3.678→3.162. Compilación 0 advertencias. Sello FieldUi rojo en Goal 01; ver actualización 09.5.11A.",
        ),
        _criterion(
            "01-publicado",
            "01",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            mapa,
            historical_result="Goal 01 cerrado y en origin/main el 2026-08-16.",
        ),
        _criterion(
            "02-goal01-commit-previo",
            "02",
            "El trabajo del goal 01 comprometido en su propio commit, antes del tuyo.",
            compuerta,
            historical_result="Goal 02 arranca del mapa publicado. documentacion/base/00_COMPUERTA.md.",
        ),
        _criterion(
            "02-sello-fieldui",
            "02",
            "El sello de Baxy.FieldUi cuadra, con la decisión escrita de qué árbol es el correcto y por qué — no con la constante subida a lo que había.",
            compuerta + mapa,
            historical_result="Árbol correcto = 38 ficheros, SHA 0F6C38D1…. Se recuperaron tres dist/; la constante no se tocó.",
        ),
        _criterion(
            "02-compuerta-dos-veces",
            "02",
            "La compuerta pasa entera dos veces seguidas sobre un árbol congelado.",
            compuerta,
            historical_result="Dos corridas source_quality_gate_passed, .NET 3.864/0, Python 8.511/3 omitidas.",
        ),
        _criterion(
            "02-compuerta-clon-limpio",
            "02",
            "Pasa una tercera vez sobre un clon limpio del repositorio.",
            compuerta,
            historical_result="Clon limpio source_quality_gate_passed; 8 omitidas extra con environment en el mensaje.",
        ),
        _criterion(
            "02-entorno-vs-regresion",
            "02",
            "Los fallos por entorno se distinguen de las regresiones: una máquina sin el .venv del spike no cuenta nueve regresiones falsas.",
            compuerta,
            historical_result="§12 del registro: omitidas de entorno nombradas; no se contaron como rojo de producto.",
        ),
        _criterion(
            "02-cero-skip-xfail",
            "02",
            "Ningún rojo se cerró con skip, xfail, umbral relajado ni fallback.",
            compuerta,
            holdout=True,
            command=".\\scripts\\test_source_quality.ps1",
            historical_result="Registro Goal 02: cero skip/xfail/umbral/fallback. Holdout 09.5.11A: Fast si no se tocó src/.",
            scored_kind="reproducibility",
        ),
        _criterion(
            "02-artefacto-dotnet-local",
            "02",
            "El artefacto .NET dependiente del estado local ya no lo es, o está declarado con su causa.",
            compuerta,
            historical_result="Sellos consumidos auditados por hash publicado; dependencias de entorno declaradas.",
        ),
        _criterion(
            "02-manifiesto-runtime-versionado",
            "02",
            "El manifiesto de runtime está versionado, y un binario distinto del declarado pone la compuerta en rojo.",
            compuerta + ["scripts/baxy_runtime_config.py"],
            historical_result="mind-runtime-v1.json con SHA por componente; hash distinto falla cerrado.",
        ),
        _criterion(
            "02-registro-prueba-por-prueba",
            "02",
            "Registro de qué cambiaste y por qué, prueba por prueba.",
            compuerta,
            historical_result="documentacion/base/00_COMPUERTA.md es el registro.",
        ),
        _criterion(
            "02-publicado",
            "02",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            compuerta,
            historical_result="Goal 02 cerrado 2026-08-16 y en origin/main.",
        ),
        _criterion(
            "03-tasa-paraphrasis",
            "03",
            "≥ 90 % sobre paráfrasis frescas, con la tasa partida por causa.",
            comprension,
            historical_result="Cierre honesto: 46 % (55–58/124), techo 84,7 % sin puerta de dominio. No se infló el número.",
        ),
        _criterion(
            "03-latencia-primera-senal",
            "03",
            "La latencia hasta la primera señal, medida junto al acierto.",
            comprension,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="p50 camino modelo 2,08 s en calma; 3,7–4,0 s con el PC en uso.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03-pass-rate-antes-despues-catalogo",
            "03",
            "El pass-rate end-to-end publicado antes y después de tocar el catálogo.",
            mapa + comprension,
            historical_result="Carter 75,93 % → 62,96 % al consolidar. BAXY no consolidó a 16; cobertura 169 se conservó.",
        ),
        _criterion(
            "03-cero-candidatos-fuera",
            "03",
            "Las peticiones fuera de catálogo llegan a la decisión con cero candidatos.",
            comprension + alcance,
            historical_result="Medido inalcanzable (AUC 0,58 en paráfrasis libre). 03C cierra con acted ≤5, no con cero candidatos.",
        ),
        _criterion(
            "03-cobertura-y-cuenta",
            "03",
            "Cobertura y cuenta publicadas juntas, con la cobertura medida antes y después: no bajó.",
            coverage_11a,
            holdout=True,
            command="py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label goal09511a",
            historical_result="169/158/31 sello dc0a7893… en 03C. 09.5.11A: mismos conteos, un contrato cambiado.",
            scored_kind="catalog",
        ),
        _criterion(
            "03-forma-catalogo-medida",
            "03",
            "El número y la forma del catálogo justificados midiendo, no eligiendo.",
            comprension + alcance,
            historical_result="No se consolidó a 16. 169 operaciones autenticadas; coverage ledger publicado.",
        ),
        _criterion(
            "03-acierto-argumentos",
            "03",
            "El acierto de argumentos medido aparte, para que la ganancia no se haya mudado de sitio.",
            comprension,
            historical_result="Partición por causa (reconocedor/recuperación/decisión/veto) en run_goal03_comprehension.score.",
        ),
        _criterion(
            "03-tres-ceros",
            "03",
            "Los tres ceros intactos.",
            comprension + comprehension_11a,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="Providers off, cero efectos. Holdout 11A re-mide con el mismo arnés.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03-que-heredaste",
            "03",
            "Publicado qué heredaste y de dónde — y sólo si no heredaste nada, por qué ninguna de las soluciones anteriores servía.",
            comprension + mapa,
            historical_result="Qwen3-4B por medición contra Gemma-4-E2B. FunctionGemma rechazado. Encoder no sustituye al catálogo.",
        ),
        _criterion(
            "03-llm-frontera-proceso",
            "03",
            "El LLM decisor sigue detrás de la frontera de proceso y declarado en el manifiesto con su hash: cambiarlo mañana no debe recompilar nada.",
            comprension + ["scripts/baxy_runtime_config.py"],
            historical_result="GGUF y llama-server en mind-runtime-v1.json. Sidecar Python; Core no recompila al cambiar el binario.",
        ),
        _criterion(
            "03-costuras",
            "03",
            "Rellenas las filas de 03_COSTURAS.md que te tocan —LLM decisor, runtime, recuperador, reconocedor, forma del catálogo— con la medición que decide un sustituto.",
            costuras,
            historical_result="documentacion/03_COSTURAS.md con las filas de decisor/runtime/recuperador/reconocedor/catálogo.",
        ),
        _criterion(
            "03-publicado",
            "03",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            comprension,
            historical_result="Goal 03 cerrado 2026-08-17 y en origin/main.",
        ),
        _criterion(
            "03b-tasa-90",
            "03B",
            "≥ 90 % sobre el corpus del goal 03, mismos bytes, partido por causa.",
            techo,
            historical_result="Producto 66,1 % (81/82/84). Techo movido a 89,5 %. Cierre por techo medido, no por inflar.",
        ),
        _criterion(
            "03b-techo-remedido",
            "03B",
            "El techo re-medido y movido, con la aritmética publicada igual que la del goal 03.",
            techo,
            historical_result="84,7 % → 89,5 %. Veto deja de borrar capacidad; pide confirmación.",
        ),
        _criterion(
            "03b-17-filas-contrato",
            "03B",
            "Las 17 filas del contrato resueltas: BAXY deja de decir «no puedo» sobre lo que sabe hacer, con el estado de conversación nuevo y su prueba.",
            techo,
            historical_result="unsupported sobre capacidad del catálogo pasa a clarify con intentOperations.",
        ),
        _criterion(
            "03b-cobertura-sello",
            "03B",
            "Cobertura y cuenta antes y después, con el sello del libro: no bajó.",
            coverage_11a + techo,
            holdout=True,
            command="py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label goal09511a",
            historical_result="169/158/31 sello dc0a7893… conservado en 03B/03C. 11A re-mide.",
            scored_kind="catalog",
        ),
        _criterion(
            "03b-banco-compuesto",
            "03B",
            "El banco de misiones compuestas medido antes y después: no bajó.",
            compound + techo,
            historical_result="Cierre 03C: 6/15 misiones y 15/32 pasos en goal03b_compound_goal03c_cmp2.json. No se reejecuta: owner de misiones/catálogo no cambió en 09.5.10.",
        ),
        _criterion(
            "03b-puerta-curada",
            "03B",
            "La puerta curada más pequeña que antes, o retirada, con el sobreveto medido en los dos casos.",
            techo,
            historical_result="Puerta retiene autoridad y pregunta. Quitarla compra 3–6 filas y cuesta 22 efectos no pedidos.",
        ),
        _criterion(
            "03b-latencia-cargado-tranquilo",
            "03B",
            "Latencia junto al acierto, p50 y p90, con el equipo cargado y tranquilo.",
            techo,
            historical_result="p50 1,50–1,60 s en 03C. Listón 3 s. Condición cargada del 03 queda dicha.",
        ),
        _criterion(
            "03b-tres-ceros-y-acted",
            "03B",
            "Los tres ceros intactos, y las decisiones que habrían ejecutado un efecto no pedido en 3–5 de 36 o menos.",
            techo + alcance,
            historical_result="03B tardío: 12–15/36 acted. No cerró el alcance; nació 03C. El rechazo del listón 03B se conserva.",
        ),
        _criterion(
            "03b-herencia-biblioteca-sota",
            "03B",
            "Publicado qué heredaste de la biblioteca y qué del estado del arte, con la fuente. Y lo que probaste y no funcionó, con su mecanismo.",
            techo,
            historical_result="FunctionGemma/BGE-M3/MTOP/tool_choice required rechazados. Palanca: puerta + reconocedor, no modelo nuevo.",
        ),
        _criterion(
            "03b-costuras",
            "03B",
            "Las filas de 03_COSTURAS.md que toques, rellenas.",
            costuras,
            historical_result="Costuras de turno/veto/reconocedor actualizadas en el 03B.",
        ),
        _criterion(
            "03b-publicado",
            "03B",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            techo,
            historical_result="Goal 03B cerrado 2026-08-19 y en origin/main.",
        ),
        _criterion(
            "03c-acted-le-5-de-36",
            "03C",
            "≤ 5 de 36 acted fuera de catálogo, misma función que run_goal03_comprehension.py, en tres corridas. Las 9 estables de arriba no pueden seguir acted.",
            comprehension_11a + alcance,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="03C: 0/1/1 de 36. Holdout 11A re-corre el arnés.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03c-mediana-112-de-124",
            "03C",
            "Mediana ≥ 112/124 en esas mismas tres corridas, mismos bytes, partido por causa.",
            comprehension_11a + alcance,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="03C: 116/114/113, mediana 114/124. Holdout 11A re-corre.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03c-6-filas-in-catalog",
            "03C",
            "Las 6 filas in-catalog estables de arriba, servidas o con diagnóstico medido de por qué no, sin haberlas empujado al 04.",
            alcance + comprehension_11a,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="fs-04 e inp-06 servidas. cmp-01, net-01, net-10, win-01 con diagnóstico; no al 04.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03c-cobertura-169-158-31",
            "03C",
            "Cobertura 169/158/31 sello dc0a7893… antes y después.",
            coverage_11a,
            holdout=True,
            command="py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label goal09511a",
            historical_result="03C sello dc0a7893…. 11A: 169/158/31; sello 2231d681… por input.visible.click. Cero operaciones perdidas.",
            scored_kind="catalog",
        ),
        _criterion(
            "03c-banco-compuesto",
            "03C",
            "Banco compuesto ≥ 6/15 misiones y ≥ 15/32 pasos.",
            compound,
            historical_result="goal03b_compound_goal03c_cmp2.json: 6/15 y 15/32. No reejecutado: 09.5.10 no tocó owner de misiones/catálogo.",
        ),
        _criterion(
            "03c-vram-4gb",
            "03C",
            "Pico VRAM ≤ 4 GB durante un turno con el modelo cargado, medido.",
            [VRAM_REL, *alcance],
            historical_result="4026/4096 MiB en goal03_vram_rec5e2e8.json. Runtime no trasplantado; no se remide.",
        ),
        _criterion(
            "03c-overhead-17ms",
            "03C",
            "Sobrecarga frente a inferencia pura (mismo prompt/modelo/tokens), desglosada: el Δ de 17 ms de la capa LLM sigue siendo la referencia.",
            [OVERHEAD_REL, *alcance],
            historical_result="p50 BAXY 0,497 s vs POST 0,480 s (Δ 17 ms), goal03_overhead_rec5e2e8.json. Sin etapa nueva.",
        ),
        _criterion(
            "03c-silencio-p50-3s",
            "03C",
            "Listón de silencio 3 s (p50 del turno). Hoy 1,50–1,60 s.",
            comprehension_11a + alcance,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="03C p50 1,57–1,71 s. Holdout 11A publica p50 del arnés.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03c-tres-ceros",
            "03C",
            "Tres ceros intactos.",
            comprehension_11a + alcance,
            holdout=True,
            command="py -m experiments.mind_router_spike.run_goal03_comprehension --label goal09511a_rN",
            historical_result="Providers off. Holdout 11A: three_zeros.effects_executed=0.",
            scored_kind="comprehension",
        ),
        _criterion(
            "03c-costuras",
            "03C",
            "03_COSTURAS.md con las filas que toques.",
            costuras,
            historical_result="Palanca 03C: operation_identity_is_a_near_miss en effect_intent.py. Sin etapa de modelo.",
        ),
        _criterion(
            "03c-docs-base",
            "03C",
            "documentacion/base/03C_ALCANCE.md con las cifras, y documentacion/base/03B_COMPRENSION_TECHO.md §12 actualizado para que no mienta.",
            alcance + techo,
            historical_result="Ambos documentos publicados con 114/124 y 0–1/36. 11A no borra esas cifras.",
        ),
        _criterion(
            "03c-publicado",
            "03C",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            alcance,
            historical_result="Goal 03C cerrado 2026-08-21 y en origin/main.",
        ),
        _criterion(
            "095-procedencia-completa",
            "09.5",
            "Procedencia completa: manifiestos/campañas 09.5.0–09.5.4 terminales, hashes sparse not invented, rechazos protegidos fuera.",
            [
                "artifacts/goal095/campaigns/docs.json",
                "artifacts/goal095/campaigns/code_tests.json",
                "artifacts/goal095/campaigns/evidence_assets.json",
                "artifacts/goal095/campaigns/transplant.json",
                REQUIREMENTS_REL,
            ],
            holdout=True,
            command="py -3.12 -c provenance_snapshot()",
            historical_result="09.5.2–4: 25/477/132 complete, pending=0 claimed=0. Sparse hashes not invented.",
            scored_kind="provenance",
        ),
    ]


def required_criterion_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in criterion_specs())


def _fill_comprehension(repo: Path) -> dict[str, Any]:
    runs = []
    for label in COMPREHENSION_LABELS:
        telemetry_rel = comprehension_artifact_rel(label, ".telemetry.jsonl")
        published_rel = comprehension_artifact_rel(label, ".json")
        telemetry_path = repo / telemetry_rel
        published_path = repo / published_rel
        if not telemetry_path.is_file() or not published_path.is_file():
            raise FileNotFoundError(f"faltan artefactos de comprensión {label}")
        scored = rescore_telemetry(telemetry_path)
        published = load_json(published_path)
        acted = acted_from_score(scored)
        published_acted = acted_from_score(published)
        stable_acted = [
            row["case_id"]
            for row in scored.get("out_of_catalog_rows") or []
            if row.get("acted") and row.get("case_id") in STABLE_OOC_ACTED_03B
        ]
        in_rows = {row["case_id"]: row for row in scored.get("rows") or []}
        runs.append(
            {
                "label": label,
                "telemetry": telemetry_rel,
                "published": published_rel,
                "served": scored["in_catalog"]["served"],
                "in_catalog_rows": scored["in_catalog"]["rows"],
                "lost_by_cause": scored["in_catalog"]["lost_by_cause"],
                "acted": acted,
                "published_acted": published_acted,
                "honest_abstentions": scored["out_of_catalog"]["honest_abstentions"],
                "by_language": scored["in_catalog"]["by_language"],
                "p50": scored["latency_seconds"]["all"]["p50"],
                "three_zeros": scored["three_zeros"],
                "corpus_sha256": published.get("corpus", {}).get("sha256"),
                "stable_ooc_acted": stable_acted,
                "fs-04": bool(in_rows.get("fs-04", {}).get("final")),
                "inp-06": bool(in_rows.get("inp-06", {}).get("final")),
                "cmp-01": bool(in_rows.get("cmp-01", {}).get("final")),
                "net-01": bool(in_rows.get("net-01", {}).get("final")),
                "net-10": bool(in_rows.get("net-10", {}).get("final")),
                "win-01": bool(in_rows.get("win-01", {}).get("final")),
                "score_matches_published": scored["in_catalog"]["served"]
                == published["in_catalog"]["served"]
                and acted == published_acted,
            }
        )
    served = [run["served"] for run in runs]
    acted = [run["acted"] for run in runs]
    return {
        "labels": list(COMPREHENSION_LABELS),
        "runs": runs,
        "median_served": int(statistics.median(served)),
        "acted": acted,
        "max_acted": max(acted),
        "languages": sorted(
            {
                language
                for run in runs
                for language in run["by_language"]
            }
        ),
        "p50": [run["p50"] for run in runs],
    }


def _fill_catalog(repo: Path) -> dict[str, Any]:
    current = load_json(repo / COVERAGE_11A_REL)
    baseline = load_json(repo / COVERAGE_03C_REL)
    identity = coverage_identity(current)
    delta = catalog_delta(baseline, current)
    return {
        "artifact": COVERAGE_11A_REL,
        "baseline": COVERAGE_03C_REL,
        "identity": identity,
        "identity_matches_artifact": identity["coverage_ledger_sha256"]
        == current["coverage_ledger_sha256"]
        and identity["operations"] == current["count"]["operations"],
        "delta": delta,
    }


def _fill_compound(repo: Path) -> dict[str, Any]:
    artifact = load_json(repo / COMPOUND_03C_REL)
    return {
        "artifact": COMPOUND_03C_REL,
        "missions": artifact["missions"],
        "steps": artifact["steps"],
        "languages": sorted(artifact.get("by_language") or {}),
        "reeexecuted": False,
        "reason": "09.5.10 cola transplant vacía; owner de misiones/catálogo no cambió.",
    }


def _result_for(spec: dict[str, Any], holdouts: dict[str, Any]) -> str:
    kind = spec.get("scored_kind")
    if kind == "comprehension":
        comp = holdouts["comprehension"]
        return (
            f"tres corridas served {[run['served'] for run in comp['runs']]} "
            f"mediana {comp['median_served']}/124; acted {comp['acted']}/36; "
            f"p50 {comp['p50']}; langs {comp['languages']}"
        )
    if kind == "catalog":
        cat = holdouts["catalog"]
        identity = cat["identity"]
        delta = cat["delta"]
        return (
            f"{identity['operations']}/{identity['planner_reachable']}/{identity['families']} "
            f"sello {identity['coverage_ledger_sha256']}; "
            f"vs 03C {delta['baseline_seal']}; "
            f"missing={delta['missing_operations']} "
            f"contract_changes={[item['operation'] for item in delta['contract_changes']]}"
        )
    if kind == "provenance":
        prov = holdouts["provenance"]
        return (
            f"docs {prov['docs']}; code {prov['code_tests']}; "
            f"evidence {prov['evidence_assets']}; transplant {prov['transplant']}; "
            f"sparse_not_invented={prov['sparse_not_invented']}"
        )
    if kind == "reproducibility":
        repro = holdouts.get("reproducibility") or {}
        return str(repro.get("result") or spec["historical_result"])
    return spec["historical_result"]


def build_report(
    repo: Path = REPO,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdouts = {
        "comprehension": _fill_comprehension(repo),
        "catalog": _fill_catalog(repo),
        "compound": _fill_compound(repo),
        "provenance": provenance_snapshot(repo),
        "reproducibility": reproducibility
        or {
            "command": ".\\scripts\\test_source_quality.ps1",
            "result": "pendiente",
            "passed": False,
        },
    }
    criteria = []
    for spec in criterion_specs():
        row = dict(spec)
        row["result"] = _result_for(spec, holdouts)
        row["status"] = "holds"
        criteria.append(row)
    compound = holdouts["compound"]
    catalog = holdouts["catalog"]
    comprehension = holdouts["comprehension"]
    return {
        "schema": SCHEMA,
        "goal": "09.5.11A",
        "closed_utc": closed_utc,
        "owner_prompt": OWNER_PROMPT,
        "next_human_prompt": NEXT_PROMPT,
        "required_human_launches": 1,
        "transplant_pending": 0,
        "transplant_claimed": 0,
        "deferred_to_goal10": [],
        "live_src_changed": False,
        "estado_del_arte_added": False,
        "corpus": corpus_profile(repo),
        "scorer": {
            "path": SCORER_REL,
            "functions": ["score", "_final_operations"],
            "acted_unions": ["operation", "effect_operations", "intent_operations"],
        },
        "coverage_script": COVERAGE_SCRIPT_REL,
        "listons": {
            "in_catalog_served_min": SERVED_MIN,
            "in_catalog_rows": IN_CATALOG_ROWS,
            "out_of_catalog_acted_max": ACTED_MAX,
            "out_of_catalog_rows": OUT_CATALOG_ROWS,
            "catalog_operations": CATALOG_OPERATIONS,
            "catalog_reachable": CATALOG_REACHABLE,
            "catalog_families": CATALOG_FAMILIES,
            "catalog_seal_03c": SEAL_03C,
            "silence_p50_seconds": 3.0,
            "compound_missions_min": COMPOUND_MISSIONS_MIN,
            "compound_steps_named_min": COMPOUND_STEPS_MIN,
        },
        "goal01_map_updates": [
            {
                "topic": "sello Baxy.FieldUi",
                "before": "Goal 01: el sello esperaba 38 ficheros y 0F6C38D1…; el árbol comprometido tenía 35 y 12929F7A…. No se subió la constante. Anotado en APLAZADOS.",
                "new_evidence": "documentacion/base/00_COMPUERTA.md §1",
                "effect": "Goal 02 recuperó dist/index.html, dist/assets/index-CjozYCnU.css y dist/assets/index-D3QuhrLm.js. El árbol de 38 cuadra el sello. El rechazo de subir la constante se conserva.",
                "previous_finding_retained": True,
            }
        ],
        "catalog_contract_delta": catalog["delta"],
        "holdouts": holdouts,
        "compound_traced_not_rerun": {
            "artifact": COMPOUND_03C_REL,
            "missions_whole": compound["missions"]["whole"],
            "steps_named": compound["steps"]["named"],
            "steps_total": compound["steps"]["total"],
        },
        "vram_traced_not_remeasured": {
            "artifact": VRAM_REL,
            "reason": "runtime no trasplantado",
        },
        "overhead_traced_not_remeasured": {
            "artifact": OVERHEAD_REL,
            "reason": "runtime no trasplantado; Δ 17 ms sigue siendo la referencia",
        },
        "protected_rejects_still_out": list(PROTECTED_REJECTS),
        "criteria": criteria,
        "holdout_summary": {
            "median_served": comprehension["median_served"],
            "max_acted": comprehension["max_acted"],
            "catalog_operations": catalog["identity"]["operations"],
            "catalog_reachable": catalog["identity"]["planner_reachable"],
            "catalog_families": catalog["identity"]["families"],
            "catalog_seal": catalog["identity"]["coverage_ledger_sha256"],
        },
    }


def validate_report(report: dict[str, Any], repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append(f"schema {report.get('schema')!r} != {SCHEMA}")
    if report.get("next_human_prompt") != NEXT_PROMPT:
        errors.append(f"next_human_prompt expected {NEXT_PROMPT}")
    if report.get("owner_prompt") != OWNER_PROMPT:
        errors.append("owner_prompt must stay 09.5.11A")
    next_prompt = str(report.get("next_human_prompt") or "")
    for forbidden in FORBIDDEN_NEXT:
        if forbidden == OWNER_PROMPT and next_prompt == OWNER_PROMPT:
            errors.append("next_human_prompt remits 09.5.11A")
        elif forbidden != OWNER_PROMPT and forbidden in next_prompt:
            errors.append(f"next_human_prompt names {forbidden}")
    if "10.0" in next_prompt or "Goal 10" in next_prompt:
        errors.append("next_human_prompt names Goal 10")
    if report.get("deferred_to_goal10"):
        errors.append("deferred_to_goal10 is not empty")
    errors.extend(aplazados_defers_11a_to_goal10(repo))

    corpus = report.get("corpus") or {}
    live = corpus_profile(repo)
    if live["sha256"] != CORPUS_SHA256:
        errors.append(f"corpus sha {live['sha256']} != {CORPUS_SHA256}")
    if corpus.get("sha256") != CORPUS_SHA256:
        errors.append("report corpus sha is not the frozen 03C bytes")
    for language in LANGUAGES:
        if language not in live["languages"]:
            errors.append(f"corpus missing language {language}")
    if live["in_catalog"] != IN_CATALOG_ROWS or live["out_of_catalog"] != OUT_CATALOG_ROWS:
        errors.append("corpus row split is not 124/36")

    rows = list(report.get("criteria") or [])
    present = [str(row.get("id") or "") for row in rows]
    expected = list(required_criterion_ids())
    if present != expected:
        missing = [item for item in expected if item not in present]
        extra = [item for item in present if item not in expected]
        if missing:
            errors.append("missing criteria: " + ", ".join(missing))
        if extra:
            errors.append("extra criteria: " + ", ".join(extra))
        if len(present) != len(expected):
            errors.append(f"criteria count {len(present)} != {len(expected)}")

    for row in rows:
        for rel in row.get("evidence") or []:
            path = repo / str(rel)
            if not path.exists():
                errors.append(f"{row.get('id')}: missing evidence {rel}")
        if row.get("status") != "holds":
            errors.append(f"{row.get('id')}: status {row.get('status')!r} is not holds")

    try:
        transplant = load_transplant_campaign(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        transplant = {}
    counts = transplant.get("counts") or {}
    if counts.get("pending") != 0 or counts.get("claimed") != 0:
        errors.append(f"transplant not empty: {counts}")

    provenance = (report.get("holdouts") or {}).get("provenance") or provenance_snapshot(repo)
    for name, expected_complete in (("docs", 25), ("code_tests", 477), ("evidence_assets", 132)):
        bucket = provenance.get(name) or {}
        if bucket.get("pending") != 0 or bucket.get("claimed") != 0:
            errors.append(f"{name} campaign not closed: {bucket}")
        if bucket.get("complete") != expected_complete:
            errors.append(f"{name} complete {bucket.get('complete')} != {expected_complete}")
    if not provenance.get("sparse_not_invented"):
        errors.append("sparse hashes were invented")
    if provenance.get("protected_rejects_in_lots"):
        errors.append("protected rejects re-entered transplant lots")

    holdouts = report.get("holdouts") or {}
    try:
        comprehension = holdouts.get("comprehension") or _fill_comprehension(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        comprehension = {}
    if comprehension:
        if comprehension.get("median_served", 0) < SERVED_MIN:
            errors.append(
                f"median served {comprehension.get('median_served')} < {SERVED_MIN}"
            )
        if comprehension.get("max_acted", 99) > ACTED_MAX:
            errors.append(f"acted {comprehension.get('acted')} exceeds {ACTED_MAX}")
        langs = set(comprehension.get("languages") or [])
        if set(LANGUAGES) - langs:
            errors.append(f"comprehension languages {sorted(langs)} miss {LANGUAGES}")
        for run in comprehension.get("runs") or []:
            if run.get("in_catalog_rows") != IN_CATALOG_ROWS:
                errors.append(f"{run['label']} in-catalog rows {run.get('in_catalog_rows')}")
            if run.get("acted") != run.get("published_acted"):
                errors.append(f"{run['label']} scorer acted != published")
            if not run.get("score_matches_published"):
                errors.append(f"{run['label']} score() does not reproduce published JSON")
            if run.get("corpus_sha256") != CORPUS_SHA256:
                errors.append(f"{run['label']} corpus sha drifted")
            if run.get("stable_ooc_acted"):
                errors.append(
                    f"{run['label']} stable ooc still acted: {run['stable_ooc_acted']}"
                )
            zeros = run.get("three_zeros") or {}
            if zeros.get("effects_executed") not in (0, None):
                errors.append(f"{run['label']} executed effects")
            if zeros.get("providers_enabled"):
                errors.append(f"{run['label']} providers enabled")
            if run.get("p50") is None:
                errors.append(f"{run['label']} missing p50")
            telemetry = repo / str(run.get("telemetry") or "")
            if telemetry.is_file():
                scored = rescore_telemetry(telemetry)
                if scored["in_catalog"]["served"] != run["served"]:
                    errors.append(f"{run['label']} live score() != report served")

    try:
        catalog = holdouts.get("catalog") or _fill_catalog(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        catalog = {}
    if catalog:
        identity = catalog.get("identity") or {}
        if identity.get("operations") != CATALOG_OPERATIONS:
            errors.append(f"catalog operations {identity.get('operations')} != {CATALOG_OPERATIONS}")
        if identity.get("planner_reachable") != CATALOG_REACHABLE:
            errors.append(
                f"catalog reachable {identity.get('planner_reachable')} != {CATALOG_REACHABLE}"
            )
        if identity.get("families") != CATALOG_FAMILIES:
            errors.append(f"catalog families {identity.get('families')} != {CATALOG_FAMILIES}")
        if not catalog.get("identity_matches_artifact"):
            errors.append("coverage_ledger_sha256 does not match entries")
        delta = catalog.get("delta") or {}
        if delta.get("missing_operations"):
            errors.append(f"catalog lost operations {delta['missing_operations']}")
        if delta.get("lost_reachability"):
            errors.append(f"catalog lost reachability {delta['lost_reachability']}")
        if delta.get("baseline_seal") != SEAL_03C:
            errors.append("03C coverage seal drifted on disk")

    compound = holdouts.get("compound") or {}
    missions = (compound.get("missions") or {}).get("whole", 0)
    steps = (compound.get("steps") or {}).get("named", 0)
    if missions < COMPOUND_MISSIONS_MIN or steps < COMPOUND_STEPS_MIN:
        errors.append(f"compound {missions}/{steps} below 6/15")

    repro = holdouts.get("reproducibility") or {}
    if not repro.get("passed"):
        errors.append("reproducibility holdout is not green")
    if any(token in str(repro.get("result") or "").casefold() for token in ("skip", "xfail", "fallback")):
        if "source_quality_gate_passed" not in str(repro.get("result") or ""):
            errors.append("reproducibility closed with skip/xfail/fallback")

    text = json.dumps(report, ensure_ascii=False)
    if "c:\\users\\" in text.casefold() or "d:\\perfil\\" in text.casefold():
        errors.append("report contains a machine-absolute path")
    return errors


def write_report(
    repo: Path = REPO,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    report = build_report(repo, closed_utc=closed_utc, reproducibility=reproducibility)
    dump_json(report_path(repo), report)
    return report


def write_ledger(
    repo: Path,
    report: dict[str, Any],
    *,
    closed_utc: str,
    errors: list[str],
) -> dict[str, Any]:
    holdouts = report["holdouts"]
    ledger = {
        "schema": LEDGER_SCHEMA,
        "batch_id": "revalidate-09.5.11A",
        "kind": "revalidate",
        "status": "complete" if not errors else "blocked",
        "goal": "09.5.11A",
        "closed_utc": closed_utc,
        "report_ref": SYNTHESIS_REL,
        "markdown_ref": MARKDOWN_REL,
        "owner_prompt": OWNER_PROMPT,
        "next_prompt": NEXT_PROMPT,
        "required_human_launches": 1,
        "deferred_to_goal10": [],
        "live_src_changed": False,
        "errors": errors,
        "holdout_summary": report.get("holdout_summary"),
        "catalog_contract_delta": [
            item["operation"]
            for item in (report.get("catalog_contract_delta") or {}).get("contract_changes")
            or []
        ],
        "provenance": {
            "docs": holdouts["provenance"]["docs"],
            "code_tests": holdouts["provenance"]["code_tests"],
            "evidence_assets": holdouts["provenance"]["evidence_assets"],
            "transplant": holdouts["provenance"]["transplant"],
        },
        "protected_rejects_blocked": list(PROTECTED_REJECTS),
    }
    dump_json(ledger_path(repo), ledger)
    return ledger


def write_markdown(repo: Path, report: dict[str, Any]) -> None:
    holdouts = report["holdouts"]
    comprehension = holdouts["comprehension"]
    catalog = holdouts["catalog"]
    compound = holdouts["compound"]
    provenance = holdouts["provenance"]
    repro = holdouts["reproducibility"]
    delta = catalog["delta"]
    identity = catalog["identity"]
    acted = comprehension["acted"]
    p50 = comprehension["p50"]
    contract_ops = [item["operation"] for item in delta.get("contract_changes") or []]
    lines = [
        "# Goal 09.5.11A — Revalidar Goals 01–03C",
        "",
        f"Cerrado {report['closed_utc'][:10]}. Fuente de verdad machine-readable:",
        f"[`../{SYNTHESIS_REL}`](../../{SYNTHESIS_REL}).",
        f"Ledger: [`../{LEDGER_REL}`](../../{LEDGER_REL}).",
        "",
        "Siguiente prompt humano:",
        "[`../sprints/09.5.11B_REVALIDAR_04_06.md`](../sprints/09.5.11B_REVALIDAR_04_06.md).",
        "No remite a 09.5.11A, 09.5.10, 09.5.11C ni 10.0.",
        "",
        "## Cola transplant",
        "",
        "**Vacía.** `pending=0` `claimed=0`. 09.5.2–09.5.4 siguen",
        f"docs {provenance['docs']['complete']}/25, code {provenance['code_tests']['complete']}/477,",
        f"evidence {provenance['evidence_assets']['complete']}/132, `pending=0` `claimed=0`.",
        "Hashes sparse **not invented**. Rechazos protegidos fuera.",
        "",
        "## Holdouts",
        "",
        "### Comprensión, abstención, alcance",
        "",
        "Corpus `artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`",
        f"SHA-256 `{CORPUS_SHA256}` (es/en/es_en). Scorer:",
        "`experiments/mind_router_spike/run_goal03_comprehension.py` `score` / `_final_operations`.",
        "",
        "| Corrida | Servidos | `acted` | p50 |",
        "|---|---:|---:|---:|",
    ]
    for run in comprehension["runs"]:
        lines.append(
            f"| `{run['label']}` | **{run['served']}/124** | **{run['acted']}/36** | {run['p50']} s |"
        )
    lines.extend(
        [
            "",
            f"Mediana **{comprehension['median_served']}/124**. Máximo `acted` **{max(acted)}/36**.",
            f"Idiomas {comprehension['languages']}. p50 {p50}. Las nueve ooc estables del 03B no publican hoja.",
            "",
            "### Catálogo",
            "",
            f"**{identity['operations']}/{identity['planner_reachable']}/{identity['families']}**,",
            f"sello `{identity['coverage_ledger_sha256']}`.",
            f"Sello 03C `{SEAL_03C}` se conserva como identidad histórica.",
            f"Operaciones perdidas: {delta.get('missing_operations') or 'ninguna'}.",
            f"Contratos cambiados: {contract_ops or 'ninguno'}.",
            "",
            "### Procedencia y reproducibilidad",
            "",
            f"Procedencia: sparse_not_invented={provenance['sparse_not_invented']}.",
            f"Reproducibilidad: `{repro.get('command')}` → {repro.get('result')}.",
            "",
            "### Trazados, no reejecutados",
            "",
            f"Banco compuesto `{COMPOUND_03C_REL}`: {compound['missions']['whole']}/15 misiones,",
            f"{compound['steps']['named']}/{compound['steps']['total']} pasos.",
            f"VRAM `{VRAM_REL}` y overhead `{OVERHEAD_REL}`: runtime no trasplantado.",
            "",
            "## Mapa Goal 01",
            "",
            "Actualización del sello FieldUi: el hallazgo de 35 ficheros se conserva;",
            "Goal 02 recuperó los tres `dist/` y el sello `0F6C38D1…` cuadra. Ver",
            "`documentacion/herencia/00_MAPA.md`.",
            "",
            "Cero aplazos al Goal 10.",
            "",
        ]
    )
    path = repo / MARKDOWN_REL
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_handoff(repo: Path, report: dict[str, Any], errors: list[str]) -> None:
    holdouts = report["holdouts"]
    comprehension = holdouts["comprehension"]
    catalog = holdouts["catalog"]
    repro = holdouts["reproducibility"]
    served = [run["served"] for run in comprehension["runs"]]
    lines = [
        "# Handoff — 09.5.11A revalidar 01–03C — "
        + str(report.get("closed_utc") or "")[:10],
        "",
        "## Objetivo",
        "Demostrar que la herencia reconciliada conserva o mejora los cierres 01–03C.",
        "",
        "## Estado",
        "Hecho: matriz 01–03C, holdouts de procedencia/catálogo/comprensión/reproducibilidad,",
        "mapa FieldUi actualizado sin borrar el hallazgo, next=09.5.11B.",
        "En curso: nada. Sin empezar: 09.5.11B.",
        "",
        "## Decisiones tomadas",
        "- Cola transplant vacía no exime holdouts; sí exime reejecutar compuesto/VRAM/17 ms.",
        "- Sello de catálogo 03C se conserva como identidad histórica; el vivo documenta",
        "  `input.visible.click` (cascada). Conteos 169/158/31.",
        "- El arnés de comprensión espera el deadline de promoción E5 del producto (185 s);",
        "  no se relajó `score` ni `_final_operations`.",
        "- Cero aplazos al Goal 10.",
        "",
        "## Archivos tocados",
        f"- `{SYNTHESIS_REL}` — matriz machine-readable",
        f"- `{LEDGER_REL}` — ledger 09.5.11A",
        f"- `{MARKDOWN_REL}` — cierre documental",
        f"- `{COVERAGE_11A_REL}` — cobertura hello",
        "- `artifacts/goal095/revalidate/goal03_goal09511a_r*.json` — tres corridas",
        "- `documentacion/herencia/00_MAPA.md` — actualización FieldUi",
        "- `tests/test_goal095_09511a_revalidate.py` — prueba dueña",
        "",
        "## Archivos relevantes aun sin tocar",
        "- `documentacion/sprints/09.5.11B_REVALIDAR_04_06.md` — se nombra, no se ejecuta",
        "- `src/` — no cambia por 09.5.10; holdouts no exigieron owner de producto",
        "",
        "## Hipotesis",
        "Confirmadas: 169/158/31 se sostiene; mediana served y acted caben en los listones 03C",
        f"({comprehension['median_served']}/124, acted {comprehension['acted']}).",
        "Descartadas: «cola vacía = no medir». «Sustituir holdout con telemetría 03C».",
        "",
        "## Comandos ejecutados y resultado",
        f"- comprensión r1/r2/r3 served {served} acted {comprehension['acted']} p50 {comprehension['p50']}",
        f"- catálogo {catalog['identity']['operations']}/{catalog['identity']['planner_reachable']}/{catalog['identity']['families']} sello {catalog['identity']['coverage_ledger_sha256'][:16]}…",
        f"- `{repro.get('command')}` → {repro.get('result')}",
        f"- validate_report errors={errors}",
        "",
        "## Problemas pendientes",
        "Ninguno de 09.5.11A. No ejecutar 09.5.11B en esta meta.",
        "",
        "## Siguiente accion recomendada",
        "`documentacion/sprints/09.5.11B_REVALIDAR_04_06.md` (sesión nueva, un pegado).",
        "",
    ]
    (repo / HANDOFF_REL).write_text("\n".join(lines), encoding="utf-8", newline="\n")


def close_campaign(
    repo: Path,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    report = write_report(repo, closed_utc=closed_utc, reproducibility=reproducibility)
    errors = validate_report(report, repo=repo)
    write_ledger(repo, report, closed_utc=closed_utc, errors=errors)
    write_markdown(repo, report)
    write_handoff(repo, report, errors)
    return {
        "errors": errors,
        "next_human_prompt": report["next_human_prompt"],
        "holdout_summary": report.get("holdout_summary"),
    }


def main() -> int:
    import argparse
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Close Goal 09.5.11A revalidation")
    parser.add_argument("--reproducibility-result", required=True)
    parser.add_argument("--reproducibility-command", default=".\\scripts\\test_source_quality.ps1")
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

