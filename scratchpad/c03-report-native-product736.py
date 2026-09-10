"""Seal the completed/interrupt-preserving comparison and readable local evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import statistics
from collections import Counter

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03/NATIVE_PRODUCT736"
local = Path(os.environ["LOCALAPPDATA"]) / "BAXY"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


data = {}
pins = {}
for model in ["k2", "qwen"]:
    folder = base / model
    private = local / f"C03-native-product736-{model}-private"
    decision, result = read(folder / "ADJUDICATION.json"), read(folder / "EXIT.json")
    assert all(result[key] for key in ["sources_unchanged", "scripts_unchanged", "app_dll_unchanged", "manifest_unchanged"])
    requests = [json.loads(line) for line in (private / "adapter-http.jsonl").open(encoding="utf-8-sig")]
    sent = {row["id"]: row for row in requests if row["stage"] == "request"}
    ended = {row["id"]: row for row in requests if row["stage"] != "request"}
    expected_temperature = 1.0 if model == "k2" else .7
    assert all(row["wire"]["temperature"] == expected_temperature and row["wire"]["max_tokens"] == 4096 for row in sent.values())
    assert all("enable_thinking" not in row["wire"].get("chat_template_kwargs", {}) for row in sent.values())
    if model == "k2":
        assert all(row["wire"]["chat_template_kwargs"]["reasoning_effort"] == "high" for row in sent.values())
    first50 = decision["verdicts"][:50]
    data[model] = {
        "completed": decision["completed_terminals"], "correct": decision["correct_finals"],
        "failed": decision["failed_finals"], "not_evaluated": decision["not_evaluated"],
        "matched50_correct": sum(row["pass"] for row in first50),
        "matched50_final_latency_p50_seconds": statistics.median(row["trace_duration_ms"]/1000 for row in first50),
        "resources": read(folder / "RESOURCES.json"), "observed_product_memory": read(folder / "PRODUCT_RESOURCES.json"),
        "http": {"calls": len(sent), "end_stages": dict(Counter(row["stage"] for row in ended.values())),
                 "incomplete_at_guard_stop": sorted(set(sent)-set(ended))},
        "legacy_guard_calls": sum(1 for _ in (private / "legacy-guard.jsonl").open(encoding="utf-8-sig")),
    }
    review = read(private / "review.json")
    lines = [f"# Respuestas literales736 — {model}", "", f"{len(review)} finales; {73-len(review)} sin evaluar. Cada juicio usa los hechos de su propio turno.", ""]
    for row, verdict in zip(review, decision["verdicts"], strict=True):
        lines.extend([f"## {row['case_id']} — {'correcta' if verdict['pass'] else 'fallo'}", "",
            "Entrada: " + row["text"], "", "Respuesta: " + row["terminal"]["final"], "",
            "Criterio: " + row["criterion"], "", "Adjudicación: " + verdict["reason"], "",
            "Operaciones: " + json.dumps(row["core_calls"]), "",
            "Payloads y borradores completos:", "", "```json",
            json.dumps(row["compose"], ensure_ascii=False, indent=2), "```", ""])
    (private / "RESPUESTAS.md").write_text("\n".join(lines), encoding="utf-8")
    names = ["panel.json", "review.json", "capture/events.jsonl", "shell-trace.jsonl", "turn-audit.jsonl", "compose-audit.jsonl",
             "adapter-http.jsonl", "http-posts.jsonl", "decision-boundary.jsonl", "legacy-guard.jsonl", "runtime-init.jsonl",
             "memory-samples.json", "product-resource-samples.jsonl", "props.json", "RESPUESTAS.md"]
    pins[model] = {name: sha(private / name) for name in names}

k2prereg, qwenprereg = read(base / "k2/PREREG.json"), read(base / "qwen/PREREG.json")
for field in ["sources", "scripts", "app_dll_sha256"]:
    assert k2prereg[field] == qwenprereg[field]
assert data["k2"]["observed_product_memory"]["observed_executables"] == data["qwen"]["observed_product_memory"]["observed_executables"]
k2verdict = read(base / "k2/ADJUDICATION.json")["verdicts"]
qwenverdict = read(base / "qwen/ADJUDICATION.json")["verdicts"][:50]
assert [r["case_id"] for r in k2verdict] == [r["case_id"] for r in qwenverdict]
paired = Counter((a["pass"], b["pass"]) for a, b in zip(k2verdict, qwenverdict, strict=True))
summary = {"utc": datetime.now(timezone.utc).isoformat(), "models": data,
    "matched50": {"both_correct": paired[True, True], "k2_only": paired[True, False],
                  "qwen_only": paired[False, True], "both_failed": paired[False, False]},
    "parity": {"source": True, "adapter_driver": True, "app_dll": True, "app_exe": True, "published_core": True},
    "environment_change": "K2 stopped below768MiB globally free RAM. After stop, AMD PresentMon collector was stopped and Steam shutdown requested. Qwen started with4940.35MiB free versus K2 reported3762.8MiB. Do not interpret this as an isolated causal latency comparison.",
    "limits": "K2 completed50/73 and must retain23 unmeasured. Qwen completed73. Matched50 are a post-stop common subset, not a newly claimed preregistered50 campaign. Native699 and product736 use different panels. Memory observers began with App present and exclude startup. No UI/voice/reserve acceptance, native-model ranking, adoption or survey coverage.",
    "adopted": False, "model_promoted": False, "survey_coverage_added": 0}
write(base / "COMPARISON.json", summary)
report = f'''# K2 y Qwen: capacidad del modelo e integración con BAXY

La preocupación del dueño está confirmada en casos concretos: BAXY puede retirar una operación correcta o rechazar una respuesta verdadera por su formulación. Eso debe separarse del rendimiento nativo del modelo.

## Resultados y alcance

El ensayo nativo699 ya comparó seis perfiles con los mismos50 casos, sin reglas ni catálogo de BAXY:300 respuestas. Qwen práctico obtuvo40/50 y K2 high práctico38/50. La prueba731 mostró además que forzar `enable_thinking=False` a K2 bajaba ese control a19/50; esa imposición no se usa aquí.

La comparación736 conserva código, adaptadores, App y Core idénticos, con el perfil propio de cada modelo. K2 se interrumpió por RAM libre global tras50 finales; Qwen completó73. Las23 peticiones restantes de K2 siguen sin evaluar.

| Medida del producto | K2 high práctico | Qwen práctico |
|---|---:|---:|
| Finales completados / previstos |50/73|73/73|
| Respuestas correctas entre los50 comunes |11/50|35/50|
| Correctas en todo lo completado |11/50|48/73|
| Mediana hasta terminal, mismos50, incluidos fallos |30,39 s|1,06 s|
| Pico VRAM del árbol medido |3,37 GiB|3,10 GiB|
| Pico RAM residente, servidor y producto observados |2,27 GiB|2,34 GiB|
| Pico memoria privada comprometida, mismo alcance |6,50 GiB|6,14 GiB|

En los50 comunes hay11 aciertos compartidos,24 sólo de Qwen y15 fallos compartidos. Esto describe **estas integraciones**: no demuestra que K2 sólo pueda responder11 de50 preguntas sin BAXY. El panel nativo699 es distinto y no permite restar puntuaciones como medida de regresión.

La adjudicación es conservadora: Qwen falla cuando añade que la GPU es principal sin observación o que la batería ya terminó de cargarse. Sus resultados son sensibles a tres formulaciones anotadas en ADJUDICATION.json (47–50/73 según esas interpretaciones). No cambia la conclusión de que ninguna integración cumple C03.

## Dónde se pierde la respuesta

- **BAXY retira propuestas correctas.** En H0023, H0103 y disk-used-es, K2 recibe y elige la operación pertinente. El replay del veto de dominio convierte las tres en conversación sin operaciones. El timeout posterior no fue la primera pérdida.
- **BAXY rechaza prosa correcta.** En H0104 la ventana y su foco están observados y bien descritos. El validador no reconoce la formulación «Activa está…» y también restringe cómo se identifica el sujeto. Reordenar sólo la cópula no basta.
- **El modelo/servidor también puede entregar un defecto.** H0207 y H0384 ya llegan con `</ifm|think>` en el content HTTP; BAXY lo publica. No se ha aislado su origen entre generación, prompt y parser. En H0359 K2 propone una cifra de batería sin lectura; después el guardia se agota. Ese error previo tampoco se atribuye a BAXY.
- **Los presupuestos de BAXY pesan mucho.** Hay llamadas de prosa con unos4s efectivos y reparaciones con el remanente. K2 registra292 fallos de transporte y40 respuestas completas en333 llamadas; una quedó abierta al corte. Qwen registra193 respuestas y1 fallo en194. Esos son contadores de llamadas, no de casos ni de errores semánticos.

Los logs distinguen el input de BAXY de la petición efectiva. Todas las llamadas K2 usaron T1/max4096/high y las Qwen T0,7/max4096; no se envió `enable_thinking=False`. Los guardias antiguos no intervienen en todas las rutas: se observaron3 llamadas en K2 y14 en Qwen, incluidos caminos posteriores a la selección nativa.

## Recursos y diferencias del entorno

K2 se cortó cuando la RAM **global** disponible cayó a747,49MiB, bajo el umbral768MiB. No superó el límite de VRAM propio. Sus muestras no identifican qué proceso causó la caída. Después se cerró el capturador AMD PresentMon (unos788MiB) y se solicitó cerrar Steam; Qwen arrancó con más RAM libre. No se presenta la diferencia de tiempos como un experimento de entorno perfectamente idéntico.

La RAM residente y la memoria privada comprometida no son equivalentes: esta última no implica que toda esa cantidad esté ocupando RAM física. Los observadores adicionales comenzaron después de aparecer la App y excluyen compiladores. Estas ejecuciones no acreditan ventana visible, voz física ni todo el consumo conjunto de BAXY en uso normal.

## Decisión y continuación

No se promueve K2 ni se cambia el runtime registrado. Tampoco se descarta K2 por la puntuación global del producto. El siguiente diagnóstico debe aislar la redacción de hechos con payloads congelados y un perfil apropiado para ese rol, y medir las pérdidas de los filtros compartidos antes de otra campaña general. No repetir la misma tanda con la misma configuración ni ampliar plazos para contar passes.

La categoría K2 sigue incompleta (23 pendientes). C03 sigue activo: encuesta26 cubiertos/716 abiertos/0 no aplicables; Full5 conserva sus dos fallos originales. No se adopta fuente ni se acredita cobertura con este informe.

[Método y atribuciones detalladas](METODO_Y_HALLAZGOS.md) · [comparación y controles](COMPARISON.json) · [juicios K2](k2/ADJUDICATION.json) · [juicios Qwen](qwen/ADJUDICATION.json).

Las entradas, respuestas literales, payloads y borradores completos permanecen localmente en:

- [K2 — respuestas](<{(local / 'C03-native-product736-k2-private/RESPUESTAS.md').as_posix()}>)
- [Qwen — respuestas](<{(local / 'C03-native-product736-qwen-private/RESPUESTAS.md').as_posix()}>)
'''
(base / "REPORT.md").write_text(report, encoding="utf-8")
public_names = ["COMPARISON.json", "REPORT.md", "METODO_Y_HALLAZGOS.md"]
for model in ["k2", "qwen"]:
    public_names.extend(f"{model}/{name}" for name in ["PREREG.json", "PREFLIGHT.json", "PROCESS.json", "EXIT.json", "RESOURCES.json", "PRODUCT_RESOURCES.json", "REVIEW_CAPTURE.json", "ADJUDICATION.json"])
public_names.extend(["k2/FOCUS_ATTRIBUTION.json", "k2/DOMAIN_ATTRIBUTION.json"])
scripts = ["c03-native-product736.py", "c03-observe-product-resources736.py", "c03-review-native-product736.py",
           "c03-focus-attribution736.py", "c03-domain-attribution736.py", "c03-adjudicate-native-product736.py", "c03-report-native-product736.py"]
write(base / "PINS.json", {"public": {name: sha(base / name) for name in public_names}, "private": pins,
    "scripts": {"scratchpad/"+name: sha(root / "scratchpad" / name) for name in scripts},
    "note": "Private literal content remains local. Original model-input scripts/backend/source hashes are also pinned by each PREREG; no source adoption."})
print(json.dumps({"matched50": summary["matched50"], "report": str(base / "REPORT.md"), "pins": len(public_names)}))
