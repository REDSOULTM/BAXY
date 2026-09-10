"""Publish the complete paired prompt diagnostic with auditable local pins."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/FACTS_PROMPT737"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-facts-prompt737-private"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    result = read(OUT / "RESULT.json")
    adjudication = read(OUT / "ADJUDICATION.json")
    summary = adjudication["summary"]
    native, baxy = summary["native_high"], summary["baxy_prompt_high"]
    assert result["calls_completed"] == 114 and len(adjudication["reviews"]) == 57
    assert all(result[key] for key in ["manifest_unchanged", "source_unchanged", "driver_unchanged"])
    assert not result["violations"]
    p = summary["paired_quality"]
    lines = ["# K2: qué cambia al añadir el prompt de BAXY", "",
        "La comparación terminó: 57 pares, 114 peticiones. El prompt completo de redacción de BAXY mejora el resultado agregado de este conjunto, pero también produce pérdidas concretas. Cada fallo necesita atribución a la capa donde aparece.", "",
        "| Medida | Pregunta y hechos directos | Prompt de BAXY |",
        "|---|---:|---:|"]
    for label, key in [("Respuestas fieles", "P"), ("Fallos de respuesta con datos suficientes", "F"),
                       ("Observación insuficiente para el alcance", "I"), ("Entrega fallida o vacía", "E")]:
        lines.append(f"| {label} | {native['verdict_counts'].get(key, 0)}/57 | {baxy['verdict_counts'].get(key, 0)}/57 |")
    for label, key in [("Mediana de respuesta final completa (s)", "complete_final_median_seconds"),
                       ("Mediana hasta primer texto visible (s)", "first_content_median_seconds"),
                       ("Mediana de generación (tokens/s)", "decode_tokens_per_second_median")]:
        lines.append(f"| {label} | {native[key]:.3f} | {baxy[key]:.3f} |")
    lines += [f"| Respuestas fieles completas antes de 4 s | {native['correct_within4s']}/57 | {baxy['correct_within4s']}/57 |", "",
        f"En pares: {p['both_correct']} aciertos compartidos, {p['baxy_only_correct']} aciertos sólo con el prompt de BAXY, {p['native_only_correct']} sólo con la petición directa y {p['neither_correct']} pares sin respuesta acreditable en ninguno. Las insuficiencias del dato se conservan aparte, no como un fallo semántico puro del modelo.", "",
        "El caso H0037 ejemplifica una pérdida: la respuesta directa conserva batería al 96%, sin carga y con corriente conectada; con el prompt de BAXY se niega esa conexión y aparece texto en otro idioma. H0600 entrega la hora directamente, mientras el otro brazo termina sin content. H0625 muestra un error propio de redacción: aun con la capacidad observada, el brazo BAXY afirma 12 GB. En sentido contrario, el prompt reduce varias explicaciones inventadas sobre memoria, GPU y salud del equipo.", "",
        "En windows-focus-mixed, el brazo BAXY produjo 1.176 tokens y completó en 22,328 s; el primer texto visible llegó a los 22,015 s. El coste principal de esa llamada estaba antes de la respuesta visible. H0350 agotó 120 s de observación sin respuesta final en ese brazo. El presupuesto del producto sigue intacto.", "",
        f"El servidor K2 alcanzó **{result['gpu_peak_mib']:.2f} MiB de VRAM ({result['gpu_peak_mib']/1024:.3f} GiB)** y **{result['ram_peak_mib']:.2f} MiB de RAM residente**. Son cifras del servidor, no de BAXY completo. No hubo corte por los guardas de recursos. Duración de campaña: {result['seconds']:.2f} s.", "",
        "La puntuación es conservadora sobre la respuesta completa. Los casos fronterizos están identificados en ADJUDICATION: permitir la truncación 14,46% en lugar del redondeo 14,47%, aceptar la clasificación AMD integrada a partir del nombre comercial o interpretar el imperativo de H0433 como una errata añade hasta tres aciertos al brazo BAXY. Interpretar favorablemente la coordenada negativa y la hipótesis de batería llena añade hasta dos al directo; penalizar la interpretación de la pregunta como etiqueta en H0037 resta uno al directo. Estas sensibilidades no sustituyen las adjudicaciones principales ni cambian los tests del producto. Las filas de observación insuficiente también pueden tener errores adicionales de redacción, detallados por caso.", "",
        "El error 500 H0104 pertenece al parser final del servidor: su log conserva un resto con respuesta correcta, pero la API no entregó content. H0600 es distinto: 84 eventos SSE contienen razonamiento y ningún fragmento visible, con stop normal. La causa previa al parser de esa salida vacía no queda identificada. Véase PARSER_ATTRIBUTION.md; no se usa razonamiento como respuesta.", "",
        "La comparación utiliza K2 Q4 con su plantilla y razonamiento alto; ambas variantes comparten backend, sampler y hechos. La receta se apoya en [la documentación oficial de IFM](https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices). El contexto local de 8.192 tokens y el backend llama.cpp siguen siendo diferencias frente a su referencia BF16/SGLang. Una sola pasada por caso no mide variabilidad entre semillas. El método y los límites de streaming, contexto y timeout están en METHOD.md.", "",
        "Las pruebas nativas 699 y la integración 736 responden preguntas distintas: 699 mide capacidades sin BAXY; 736 localiza pérdidas en el producto. Esta comparación 737 aísla únicamente el prompt de redacción. No es una nueva comparación completa K2–Qwen ni una validación de todas las capas.", "",
        "**Siguiente trabajo:** reparar las transformaciones de BAXY ya demostradas que vetan operaciones o prosa correctas, y reproducir el fallo PEG con el parser exacto antes de modificar el backend. Conservar esta comparación como control; cambiar una pieza y comprobar la primera pérdida antes de otra tanda integrada. No promover K2 ni atribuirle fallos de datos, veto o transporte.", "",
        "C03 continúa activo: encuesta con 26 cubiertos, 716 abiertos y 0 no aplicables; Full5 rojo por los límites originales de packaging y sidecar; validación final de producto/UI/voz y resto del alcance pendientes. Esta comparación no adopta fuente, no cambia manifiesto, no añade cobertura y no ejecuta Full por un diagnóstico sin cambios de producto.", "",
        "Evidencia pública: PREREG.json, PREFLIGHT.json, RESULT.json, TRANSPORT.json, ADJUDICATION.json y PINS.json. Preguntas, respuestas y payloads completos permanecen en el directorio privado local C03-facts-prompt737-private, en RESPUESTAS.md y sus trazas originales."]
    (OUT / "REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    private_text = (PRIVATE / "RESPUESTAS.md").read_text(encoding="utf-8")
    private_text += "\n# Adjudicación por caso\n\n"
    for review in adjudication["reviews"]:
        private_text += f"- {review['case_id']}: directo {review['native_high']}; BAXY {review['baxy_prompt_high']}. {review['reason']}\n"
    (PRIVATE / "RESPUESTAS_Y_ADJUDICACION.md").write_text(private_text, encoding="utf-8")
    public_names = ["PREREG.json", "PREFLIGHT.json", "PROCESS.json", "RESULT.json", "TRANSPORT.json", "ADJUDICATION.json", "METHOD.md", "PARSER_ATTRIBUTION.md", "REPORT.md", "INTEGRITY.json"]
    private_names = ["cases.json", "planned-requests.json", "rendered-prompts.jsonl", "props.json", "stream.jsonl", "results.jsonl", "server.log", "RESPUESTAS.md", "RESPUESTAS_Y_ADJUDICACION.md"]
    script_names = ["c03-facts-prompt737.py", "c03-review-facts737.py", "c03-adjudicate-facts737.py", "c03-report-facts737.py", "c03-checkpoint737.py"]
    pins = {"public": {str((OUT/name).relative_to(ROOT)).replace("\\", "/"): sha(OUT/name) for name in public_names},
        "private": {name: sha(PRIVATE/name) for name in private_names},
        "scripts": {"scratchpad/"+name: sha(ROOT/"scratchpad"/name) for name in script_names},
        "source_unchanged_sha256": sha(ROOT/"src/baxy_mind/llm.py"),
        "private_root": "%LOCALAPPDATA%/BAXY/C03-facts-prompt737-private", "byte_preservation": "New public737 and script paths use -text; historical evidence unchanged."}
    (OUT / "PINS.json").write_text(json.dumps(pins, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"report": str(OUT/"REPORT.md"), "pins": sum(len(pins[key]) for key in ["public", "private", "scripts"])}))


if __name__ == "__main__":
    main()
