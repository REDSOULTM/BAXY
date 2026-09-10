"""Record source validation and full-goal continuation during window repair."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "WINDOW_FOCUS738"
TITLE = "## Fuente candidata738 — estado vigente\n\n"


def main():
    final = "--final" in sys.argv
    status = ("Fast2/84139 en curso; esperar esa sesión sin reiniciar." if not final else
              "Fast2/84139 terminó verde; no volver a sondear.")
    body = (
        "Se corrige el orden del predicado de foco y el enlace de un nombre observado entre paréntesis, "
        "incluido un título opaco entre comillas. El alias descriptivo debe estar en los datos de esa misma ventana. "
        "También se impide que un nombre como Is Active borre el predicado de una pregunta. "
        "No se cambian respuestas, modelos, plazos ni reglas de autorización.\n\n"
        "Pruebas: nuevos219 antes=179fallos/40pass; dueñas finales de ventanas772pass/0skip en2,75s. "
        "Declaraciones actuales del programa STT:17pass/1skip ambiental en1,90s, no aceptación de voz. "
        "Árbol Python407/hash87bf1a3b9602377869fa7d27fdfe3a65a6231f2d2ad5dfc71c450a783af9e47a; "
        "sellos históricos intactos. Fast1/39645 verde sobre la revisión anterior; " + status + "\n\n"
        "Replay de215registros,205textos/factos distintos,14registros de ventanas/9distintos. "
        "Cambia una respuesta correcta de K2/H0104 que aparece en6registros duplicados: pasa de missing_fact "
        "a aceptada por el validador completo. Los demás resultados del replay se conservan. "
        "Dos respuestas737 fieles siguen rechazadas: windows-focus-mixed/BAXY y windows-focus-reference-es/directo; "
        "no ampliar aceptación sin revisar las demás afirmaciones del texto. "
        "Esta fuente es candidata pendiente de regresión integrada, no cierre de la familia ni promoción de K2.\n\n"
        "Siguiente: resolver los dos fallos originales de Full5 antes de acumular más fuentes sin adoptar. "
        "Empezar por tests/test_sidecar_lifecycle.py y la evidencia725/727; sus pases del prototipo de fases "
        "retirado no acreditan el límite original3s. Conservar packaging45s y ambas pruebas intactas. "
        "736 también prueba3vetos incorrectos de propuestas;737 separa prompt/servidor/modelo. "
        "Fuentes705+712+730 sin adoptar; Full5 sigue rojo en packaging45s y sidecar3s originales, noFull6. "
        "Encuesta26cubiertos/716abiertos/0NA; ninguna decisión pendiente. BAXY manual cerrado. "
        "C03 completo sigue activo, incluidos UI, voz, recursos conjuntos, reserva, matriz y Full final.\n"
    )
    text = TITLE+body
    for filename in ["CHECKPOINT.md", "HANDOFF.md"]:
        path = BASE / filename
        old = path.read_text(encoding="utf-8-sig")
        if old.startswith(TITLE):
            boundary = old.find("\n## ", len(TITLE))
            old = old[boundary+1:] if boundary >= 0 else ""
        path.write_text(text+"\n"+old, encoding="utf-8")
    (OUT / "HANDOFF.md").write_text(text, encoding="utf-8")
    path = BASE / "RELEVO_ACTIVO.json"
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
        workStatus="window_focus738_candidate_validated" if final else "window_focus738_validation_running",
        checkpoint=body, continuation="Follow WINDOW_FOCUS738/HANDOFF.md; preserve full C03 scope and all unadopted sources.",
        publishedEvidenceCommit="d47a92c532f205a71a39eec83c606b9a8ac939d3",
        currentDiagnostic={"path": "artifacts/comprobaciones/C03/WINDOW_FOCUS738", "sessionId": 84139, "running": not final},
        previousGoalTurnClassification="progress",
        previousGoalTurnClassificationReason="737 completed114calls, paired adjudication and publication;738 now fixes an observed false rejection with existing and variant controls.")
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
