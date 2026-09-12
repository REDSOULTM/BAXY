"""Actualiza RELEVO_ACTIVO.json conservando sourceThreadId, la pausa histórica y lo que no cambió.

Se reescriben sólo los campos que esta sesión midió; la identidad del relevo, la pausa del repositorio y
la corrección de papeles de las máquinas se conservan tal cual.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/comprobaciones/C03/RELEVO_ACTIVO.json"

UPDATES = {
    "threadId": "kiro-opus5-redpc-20260912T0527Z",
    "checkpoint": ("137/742covered,605open,0NA; 1029 medida y adjudicada (+3); 1030 sin credito por "
                   "frase fija; 1031 invalidada por el escritorio, sin cambio de registro; 1032 con las "
                   "dos reparaciones (+4). apps_open 21/54."),
    "continuation": (
        "Siguiente reparación, ya diagnosticada y medida: el hecho «ya estaba en ejecución» debe viajar "
        "como hecho con nombre propio para que el PRIMER borrador lo diga —las tres respuestas veraces y "
        "distintas de APPS1029 salieron del primer borrador, sin instrucción correctiva— y hay que cubrir "
        "la dirección espejo que H0575 destapó: dijo «ya tengo la calculadora abierta» con "
        "alreadyRunning=false. Quedan esperando esa vuelta los 7 literales de Steam (H0015, H0055, H0134, "
        "H0136, H0391, H0418, H0653) y H0575. Después, la reparación léxica de los 19 abiertos de apps que "
        "no llegan al reconocedor, casi todos erratas de «steam» y «calculadora». C03 no está completado."),
    "surveyVerificationCounts": {"covered": 137, "open": 605, "not_applicable": 0},
    "surveyRegistrySha256": "e9622300757b30a26fca21d84fbbde8afc85b5cec73aea1be03c9f600ef10ee3",
    "surveyCategories": {"closed": 0, "total": 35},
    "surveyCoverageLast24h": 109,
    "latestProductRun": {
        "batch": 1032,
        "state": "adjudicated",
        "executed": 23, "passed": 13, "failed": 10, "coverageAdded": 4,
        "exitCode": 0, "violations": 0,
        "gpuPeakMib": 3494.9296875, "ramPeakMib": 2652.30,
        "adjudication": "artifacts/comprobaciones/C03/REPAIR1032/ROOT_ADJUDICATION.json",
        "sealedBeforeExecution": True,
    },
    "batchesThisSession": [
        {"batch": 1029, "kind": "wide", "credits": 3,
         "adjudication": "artifacts/comprobaciones/C03/APPS1029/ROOT_ADJUDICATION.json"},
        {"batch": 1030, "kind": "directed_repair", "credits": 0,
         "why": "reparación correcta, frase fija: invariante 5",
         "adjudication": "artifacts/comprobaciones/C03/REPAIR1030/ROOT_ADJUDICATION.json"},
        {"batch": 1031, "kind": "directed_repair", "credits": 0,
         "why": "invalidada: ShellHost.exe retenía el primer plano; sin cambio de estado en el registro",
         "adjudication": "artifacts/comprobaciones/C03/REPAIR1031/ROOT_ADJUDICATION.json"},
        {"batch": 1032, "kind": "directed_repair", "credits": 4,
         "why": "verificación sin exigir foco, demostrada en el producto",
         "adjudication": "artifacts/comprobaciones/C03/REPAIR1032/ROOT_ADJUDICATION.json"},
    ],
    "sourceChangesThisSession": [
        {"file": "src/baxy_mind/llm.py",
         "change": "unstated_already_running: rechaza atribuirse una apertura que el recibo dice que no "
                   "ocurrió, y el relanzamiento afirmado sobre un proceso reutilizado",
         "verified_without_gpu": "scratchpad/c03-already-running-check.py, 28 borradores reales, 0 "
                                 "discrepancias"},
        {"file": "src/Baxy.Providers.Windows/Applications/{WindowsApplicationOpenVerifier,"
                 "WindowsInstalledApplicationOpenProvider,WindowsCalculatorOpenProvider}.cs",
         "change": "app.open pide el primer plano y ya no lo exige: la observación es una ventana visible "
                   "del proceso vinculado por el recibo",
         "build": "build_exit 0, warmup_exit 0, shutdown_exit 0, Core efectivo == publicado"},
    ],
    "instrumentsAdded": [
        "scratchpad/c03-open-mass-by-reach.py — masa abierta cruzada con alcance del reconocedor",
        "scratchpad/c03-app-gpu-cost.py — coste de GPU dedicada por app, con el contador de la guarda",
        "scratchpad/c03-window-state.py — quién tiene el primer plano y qué es visible",
        "scratchpad/c03-dismiss-flyout.py — devuelve el foco antes de medir",
        "scratchpad/c03-already-running-check.py — el chequeo contra los borradores reales, sin GPU",
        "scratchpad/c03-batch-dump.py — transcripción y recibos de cualquier tanda",
        "scratchpad/c03-candidate-manifest.py — manifiesto de candidato para cualquier tanda",
        "scratchpad/c03-build-receipt.py — compila por el arranque vigente y deja recibo propio",
    ],
    "environmentNotes": {
        "aot_publish_requires_vswhere_on_path": "%ProgramFiles(x86)%/Microsoft Visual Studio/Installer; "
                                               "sin eso el enlazado nativo falla con MSB3073",
        "core_private_directory": "debe ser hijo DIRECTO de %LOCALAPPDATA%/BAXY; una ruta anidada produce "
                                  "blocked_environment: runtime_not_ready",
        "system_flyout_holds_foreground": "ShellHost.exe «Configuración rápida» invalidó REPAIR1031; el "
                                          "runner de 1032 se niega a arrancar en ese estado",
        "app_gpu_not_attributed_to_tree": "picos 3492–3495 MiB con Paint lanzado dentro de la tanda: las "
                                          "apps que activa el servicio AppX no cuentan en el árbol",
    },
    "openRepairs": {
        "already_running_first_draft": "el hecho debe viajar como hecho para que el primer borrador lo "
                                       "diga; la instrucción correctiva homogeniza (7 literales de Steam)",
        "already_running_mirror": "H0575 dijo «ya tengo la calculadora abierta» con alreadyRunning=false",
        "apps_lexical_gap": "19 abiertos de apps no llegan al reconocedor: erratas de «steam» y "
                            "«calculadora», idiomas no pedidos, explorador, Photoshop",
        "prohibition_with_query_boundary": "«No abras X; sólo decime si está instalada» publica jerga de "
                                           "contrato en 1030, 1031 y 1032",
        "system1028_cause_B": "mitad temporal de petición compuesta perdida y después inventada",
        "system1028_cause_C": "scope summary elegido para una pregunta que nombra la GPU",
        "missing_referent": "ampliar _deictic_open_request con controles de tratamiento formal",
        "agenda1024": "parche recibido y revisado, sin integrar",
    },
    "previousGoalTurnClassification": "progress",
    "previousGoalTurnClassificationReason": (
        "130 -> 137 cubiertos con cuatro tandas reales selladas y adjudicadas, dos reparaciones de fuente "
        "adoptadas por evidencia (una .NET compilada por el arranque vigente), una tanda declarada "
        "invalidada por el escritorio sin tocar el registro, y el instrumento que ordena el trabajo por "
        "abiertos que ya llegan al reconocedor."),
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
    print(json.dumps({"threadId": data["threadId"], "covered": data["surveyVerificationCounts"],
                      "sourceThreadId": data["sourceThreadId"],
                      "pausedThreadId": data["pausedThreadId"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
