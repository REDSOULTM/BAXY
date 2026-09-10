"""Preserve the validated worktree candidate without claiming source adoption."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/WINDOW_FOCUS738"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-window-focus738-private"
TEMP = Path(os.environ["TEMP"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    logs = {
        "BEFORE.log": "c03-window-focus738-before.log",
        "OWNERS.log": "c03-window-focus738-owners-final.log",
        "PROGRAM_TESTS.log": "c03-window-focus738-program-tests.log",
        "FAST1.log": "c03-window-focus738-fast.log",
        "FAST2.log": "c03-window-focus738-fast2.log",
    }
    assert "772 passed in 2.75s" in (TEMP / logs["OWNERS.log"]).read_text(encoding="utf-8-sig")
    assert "17 passed, 1 skipped in 1.90s" in (TEMP / logs["PROGRAM_TESTS.log"]).read_text(encoding="utf-8-sig")
    assert "source_quality_gate_passed: mode=Fast" in (TEMP / logs["FAST2.log"]).read_text(encoding="utf-8-sig")
    assert (TEMP / "c03-window-focus738-fast2-exit.txt").read_text(encoding="utf-8-sig").strip() == "0"
    for destination, source in logs.items():
        shutil.copyfile(TEMP / source, OUT / destination)
    snapshots = {
        "window_prose_facts.py.txt": "src/baxy_mind/window_prose_facts.py",
        "test_c03_window_focus_apposition.py.txt": "tests/test_c03_window_focus_apposition.py",
    }
    for destination, source in snapshots.items():
        shutil.copyfile(ROOT / source, OUT / destination)
    result = {
        "utc": datetime.now(timezone.utc).isoformat(), "status": "validated_worktree_candidate_not_adopted",
        "source_sha256": sha(ROOT / "src/baxy_mind/window_prose_facts.py"),
        "test_sha256": sha(ROOT / "tests/test_c03_window_focus_apposition.py"),
        "baseline_new_tests": {"passed": 40, "failed": 179, "total": 219},
        "final_window_owner_tests": {"passed": 772, "failed": 0, "skipped": 0, "seconds": 2.75,
            "command": "pytest tests/test_c03_window_facts.py tests/test_c03_window_focus_coverage.py tests/test_c03_window_focus_subject_order.py tests/test_c03_window_identity_answers.py tests/test_c03_window_prose_projection.py tests/test_c03_window_state_facts.py tests/test_c03_window_focus_apposition.py -q"},
        "program_tests": {"passed": 17, "failed": 0, "skipped": 1, "seconds": 1.90,
            "skip": "environment: blind campaign inputs absent", "audio_acceptance": False},
        "fast1": {"session": 39645, "exit_code": 0, "revision": "before quoted-title apposition fix", "release_seconds": 21.70},
        "fast2": {"session": 84139, "exit_code": 0, "release_seconds": 1.74, "warnings": 0, "errors": 0},
        "validation_context": "Existing unadopted705+712+730 worktree retained. Current STT declarations reflect this worktree, not a standalone clean-head promotion.",
        "llm_dependency_sha256": sha(ROOT / "src/baxy_mind/llm.py"),
        "snapshots": snapshots, "adopted": False, "model_promoted": False, "survey_coverage_added": 0,
        "full": "Full5 remains red at original packaging45s and sidecar3s. No Full6 and no final-goal acceptance.",
        "next_action": "Repair original Full5 blockers before adopting the pending source set; inherit725/727 without treating phase-prototype passes as original3s proof.",
    }
    write(OUT / "RESULT.json", result)
    report = """# Corrección del rechazo de foco — candidato 738

BAXY rechazaba una respuesta correcta de K2 por el orden de la cópula y por
presentar el nombre observado entre paréntesis. El candidato reconoce ambas
formas sin reescribir la respuesta ni pedir otra inferencia. El nombre
descriptivo debe estar en los datos de la misma ventana: un alias inventado o
la identidad de otra aplicación no acreditan el foco.

También conserva títulos entre comillas y evita que un proceso llamado
«Is Active» borre el predicado de «Which window is active?». Las comprobaciones
mantienen la distinción entre foco y estado normal/maximizado/minimizado,
negación, preguntas, incertidumbre, otro sujeto y campos no booleanos.

| Validación | Resultado |
|---|---|
| Primer conjunto de 219 variantes, antes de editar | 40 pass, 179 fail |
| Todas las pruebas dueñas de ventanas, revisión final | 772 pass, 0 fail, 0 skips; 2,75 s |
| Declaraciones actuales del programa STT | 17 pass, 1 skip ambiental; 1,90 s |
| `scripts/test_source_quality.ps1`, revisión final | Fast verde; Release 1,74 s, 0 advertencias y 0 errores |

El salto de STT corresponde a entradas ausentes de una campaña ciega y no
acredita audio. Las pruebas originales no se relajaron. Fast1 también pasó,
pero corresponde a la revisión anterior al ajuste de títulos entre comillas;
Fast2 acredita la fuente final.

El replay recorrió 215 registros capturados, equivalentes a 205 combinaciones
distintas de fuente, pregunta, respuesta y hechos. Nueve combinaciones son de
ventanas. Cambió una respuesta veraz de H0104/K2: antes `missing_fact`, ahora
aceptada por el validador completo. Aparece en seis registros duplicados;
no son seis aciertos independientes. Los otros resultados se conservaron.

Siguen rechazadas otras dos respuestas fieles de737: windows-focus-mixed con
el prompt de BAXY y windows-focus-reference-es con petición directa. Están
identificadas en REPLAY.json y en las respuestas privadas. Esta corrección no
cierra toda la familia de ventanas ni sustituye una prueba integrada nueva.

La fuente y las pruebas quedan como candidato en el árbol de trabajo. Las
copias `.py.txt` conservan sus bytes para revisión y recuperación. No se
promueve el modelo ni se adopta el conjunto todavía: las validaciones usan el
WIP previo de705,712 y730, y Full5 continúa rojo en los límites originales de
packaging (45 s) y salida del sidecar (3 s). Las declaraciones actuales de STT
describen ese árbol; los sellos de campañas históricas permanecen intactos.

La siguiente prioridad es resolver esos dos bloqueos de Full antes de acumular
más fuentes pendientes de adopción. C03 permanece activo, con26 requisitos de
encuesta cubiertos y716 abiertos. No se añadió cobertura con este replay.

Las preguntas, respuestas literales, hechos y validaciones antes/después están
en `%LOCALAPPDATA%/BAXY/C03-window-focus738-private/RESPUESTAS.md` y `replay.json`.
Los archivos públicos RESULT, REPLAY, PROGRAM y PINS vinculan las comprobaciones
con las fuentes exactas. No se ejecutaron modelos, UI ni voz en este tramo.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    public = list(logs) + list(snapshots) + ["RESULT.json", "REPLAY.json", "PROGRAM.json", "REPORT.md", "HANDOFF.md"]
    scripts = ["scratchpad/c03-replay-window-focus738.py", "scratchpad/c03-checkpoint-window738.py", "scratchpad/c03-record-window738.py"]
    pins = {"public": {str((OUT/name).relative_to(ROOT)).replace("\\", "/"): sha(OUT/name) for name in public},
        "private": {name: sha(PRIVATE/name) for name in ["replay.json", "RESPUESTAS.md"]},
        "scripts": {name: sha(ROOT/name) for name in scripts},
        "worktree_candidate": {source: sha(ROOT/source) for source in snapshots.values()},
        "private_root": "%LOCALAPPDATA%/BAXY/C03-window-focus738-private"}
    write(OUT / "PINS.json", pins)
    print(json.dumps({"status": result["status"], "public_pins": len(public), "script_pins": len(scripts)}))


if __name__ == "__main__":
    main()
