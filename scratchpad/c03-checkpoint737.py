"""Keep current continuation explicit without altering historical records."""
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "FACTS_PROMPT737"
TITLE = "## Diagnóstico737 — estado vigente\n\n"


def main():
    running = not (OUT / "RESULT.json").exists()
    body = ("737 sigue en sesión85518, driver5116/servidor32236, endpoint local52076. "
            "No reiniciar ni editar el driver o llm.py durante la corrida. " if running else
            "737 terminó114/114, sesión85518 terminal; no volver a sondearla ni reiniciar. ")
    if (OUT / "ADJUDICATION.json").exists():
        scores = json.loads((OUT / "ADJUDICATION.json").read_text(encoding="utf-8"))["summary"]
        native, baxy = scores["native_high"], scores["baxy_prompt_high"]
        body += (f"Adjudicación57pares: directo{native['verdict_counts'].get('P', 0)} fieles, "
                 f"prompt BAXY{baxy['verdict_counts'].get('P', 0)}. "
                 f"Mediana final completa{native['complete_final_median_seconds']:.3f}/{baxy['complete_final_median_seconds']:.3f}s. "
                 "BAXY:1errorPEG,1límiteoffline120s,1stop sin content. "
                 "Datos insuficientes y sensibilidad separados enREPORT/ADJUDICATION. "
                 "Seguir reparando primera transformación demostrada, no otro barrido de presets. ")
    body += ("Compara57 pares con los mismos hechos/pregunta: petición directa frente a los mensajes exactos del writer BAXY capturados en736. "
             "Sólo cambia ese componente de prompt; K2 Q4 high/T1/p.95, backend y contexto8192 iguales, salida32768 y streaming. "
             "Preflight114/114 con plantilla high nativa, máximo1232 tokens de entrada. "
             "Es diagnóstico de prompt completo, no cláusula individual ni aceptación de producto. "
             "El límite offline120s es blando por lectura SSE/socket; no se presenta como deadline estricto. "
             "Errores sin usage dejan contexto desconocido aunque el campo original diga false. "
             "La referencia4s separa latencia de calidad; no cambia plazos de producción.\n\n"
             "H0104/BAXY produjo una salida cruda con respuesta correcta y el parser PEG final la rechazó con500; "
             "no atribuir ese fallo de entrega a semántica ni a un veto del producto. "
             "La causa sintáctica específica sigue en investigación. BAXY manual cerrado. "
             "No se adopta fuente ni promueve modelo ni añade cobertura. Encuesta26/716/0; Full5rojo original, noFull6. "
             "705+712+730 y cambios ajenos preservados. C03 completo sigue activo; ninguna decisión pendiente.\n\n")
    text = TITLE + body
    for filename in ["CHECKPOINT.md", "HANDOFF.md"]:
        path = BASE / filename
        old = path.read_text(encoding="utf-8-sig")
        if old.startswith(TITLE):
            index = old.find("\n## ", len(TITLE))
            old = old[index+1:] if index >= 0 else ""
        path.write_text(text+old, encoding="utf-8")
    (OUT / "HANDOFF.md").write_text(text.rstrip()+"\n", encoding="utf-8")
    path = BASE / "RELEVO_ACTIVO.json"
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
                 workStatus="facts_prompt737_running" if running else "facts_prompt737_complete_no_adoption",
                 checkpoint=body.split("\n\n")[0],
                 continuation="Follow FACTS_PROMPT737/HANDOFF.md. Keep inference and quality adjudication distinct; no new integrated campaign before first-loss attribution.",
                 currentDiagnostic={"path": str(OUT.relative_to(ROOT)).replace("\\", "/"),
                                    "sessionId": 85518, "running": running},
                 previousGoalTurnClassification="progress",
                 previousGoalTurnClassificationReason="Frozen57 paired facts-to-prose controls, verified114 native high templates and observed model/server/prompt separately.")
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
