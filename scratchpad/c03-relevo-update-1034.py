"""Actualiza RELEVO_ACTIVO.json tras REPAIR1033 y CLOCK1034, conservando identidad y pausa."""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/comprobaciones/C03/RELEVO_ACTIVO.json"

UPDATES = {
    "threadId": "kiro-opus5-redpc-20260912T0610Z",
    "checkpoint": ("154/742covered,588open,0NA; seis tandas propias: 1029 +3, 1030 0, 1031 invalidada, "
                   "1032 +4, 1033 +7, 1034 +10. apps_open 28/54, clock 13/23."),
    "continuation": (
        "Candidato grande y ya diagnosticado: la aclaración innecesaria. Cinco literales han fallado por "
        "preguntar cuando la decisión ya sabía la operación —turn-audit con intent_operations "
        "[system.time] y effect_operations vacío— en SYSTEM1028 (H0532), APPS1029 (H0497) y las cuatro "
        "variantes de CLOCK1034. Toca la capa de decisión, así que se mide primero cuántos abiertos "
        "dependen de ella y se sella con controles de las dos clases: donde preguntar es correcto "
        "(destino ausente, referente deíctico, confirmación de efecto) y donde no. Detalle en "
        "RUTAS_DE_TEXTO_VISIBLE.md. Después, por masa abierta ejecutable: agenda 29 abiertos con 18 que "
        "llegan al reconocedor, o música 39 con 19 —música exige decidir antes qué se hace con el efecto "
        "incierto de Spotify 962, que no se reproduce ni se cierra—. C03 no está completado."),
    "surveyVerificationCounts": {"covered": 154, "open": 588, "not_applicable": 0},
    "surveyRegistrySha256": "58986cb8b2b42a6d70f6648ea0e66b9a7b7e948b784963316683fb6b3f8671f7",
    "surveyCategories": {"closed": 0, "total": 35},
    "surveyCoverageLast24h": 128,
    "latestProductRun": {
        "batch": 1034, "state": "adjudicated", "executed": 22, "passed": 15, "failed": 7,
        "coverageAdded": 10, "exitCode": 0, "violations": 0,
        "gpuPeakMib": 3494.9296875, "ramPeakMib": 2580.30,
        "adjudication": "artifacts/comprobaciones/C03/CLOCK1034/ROOT_ADJUDICATION.json",
        "sealedBeforeExecution": True,
        "readOnly": True,
    },
    "batchesThisSession": [
        {"batch": 1029, "kind": "wide_apps", "credits": 3},
        {"batch": 1030, "kind": "directed_repair", "credits": 0,
         "why": "reparación correcta, frase fija: invariante 5"},
        {"batch": 1031, "kind": "directed_repair", "credits": 0,
         "why": "invalidada: ShellHost.exe retenía el primer plano; sin cambio de estado en el registro"},
        {"batch": 1032, "kind": "directed_repair", "credits": 4,
         "why": "verificación sin exigir foco, demostrada en el producto"},
        {"batch": 1033, "kind": "directed_repair", "credits": 7,
         "why": "dirección espejo, y criterio de frase fija estrechado con su coste declarado"},
        {"batch": 1034, "kind": "wide_clock", "credits": 10,
         "why": "diez lecturas de reloj comprobadas al minuto contra su propio recibo"},
    ],
    "sourceChangesThisSession": [
        {"file": "src/baxy_mind/llm.py",
         "change": "unstated_already_running + invented_prior_open_state: las dos direcciones del estado "
                   "de apertura, y el relanzamiento afirmado sobre un proceso reutilizado",
         "verified_without_gpu": "scratchpad/c03-open-state-check.py, 48 borradores reales, 0 "
                                 "discrepancias"},
        {"file": "src/Baxy.Providers.Windows/Applications/{WindowsApplicationOpenVerifier,"
                 "WindowsInstalledApplicationOpenProvider,WindowsCalculatorOpenProvider}.cs",
         "change": "app.open pide el primer plano y ya no lo exige",
         "build": "build_exit 0, warmup_exit 0, shutdown_exit 0, Core efectivo == publicado"},
        {"file": "src/baxy_mind/__main__.py",
         "change": "una respuesta conversacional de una sola palabra en mayúsculas no se publica: es "
                   "vocabulario del prompt, y la ruta de llm.chat no pasa por el filtro de defectos",
         "verified_without_gpu": "scratchpad/c03-bare-token-check.py, 125 terminales publicados de seis "
                                 "tandas: rechaza los dos «SIEMPRE», conserva las 123 respuestas reales"},
    ],
    "openRepairs": {
        "unnecessary_clarification": "cinco literales fallados por preguntar con la operación ya "
                                     "identificada; toca la capa de decisión y necesita controles de las "
                                     "dos clases",
        "already_running_first_draft": "el hecho llega por instrucción de reintento, que homogeniza; el "
                                       "primer borrador debería decirlo solo",
        "apps_lexical_gap": "19 abiertos de apps no llegan al reconocedor y la puerta está antes de la "
                            "gramática verbal (HUECO_LEXICO_APPS.md)",
        "prohibition_with_query_boundary": "«No abras X; sólo decime si está instalada» publica jerga de "
                                           "contrato en cuatro tandas seguidas",
        "system1028_cause_B": "mitad temporal de petición compuesta perdida y después inventada",
        "system1028_cause_C": "scope summary elegido para una pregunta que nombra la GPU",
        "missing_referent": "ampliar _deictic_open_request con controles de tratamiento formal",
        "agenda1024": "parche recibido y revisado, sin integrar",
    },
    "previousGoalTurnClassification": "progress",
    "previousGoalTurnClassificationReason": (
        "137 -> 154 cubiertos en esta iteración con dos tandas selladas y adjudicadas, una reparación de "
        "fuente más adoptada por evidencia, el criterio de frase fija estrechado antes de ejecutar con su "
        "coste declarado, y las tres rutas de texto visible identificadas con la conversacional ya "
        "cerrada contra la fuga de vocabulario del prompt."),
}


def main() -> int:
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    data.update(UPDATES)
    data["utcUpdated"] = datetime.now(timezone.utc).isoformat()
    for required in ("sourceThreadId", "pausedThreadId", "historicalPause", "machineRoleCorrection",
                     "destinationRuntime", "classificationImmutable"):
        if required not in data:
            raise SystemExit(f"refusing to write a relay record without {required}")
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"threadId": data["threadId"], "counts": data["surveyVerificationCounts"],
                      "sourceThreadId": data["sourceThreadId"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
