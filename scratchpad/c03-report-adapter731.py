"""Join frozen731 verdicts with the unchanged historical699 control and publish evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "K2_HORIZON_ADAPTER731"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-k2-adapter731-private"
REFERENCE = BASE / "K2_HORIZON_NATIVE699/run-37-q4-high-practical699"
REFERENCE_PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-k2-native699-37-q4-high-practical699-private"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def jsonl(path):
    with path.open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


adjudication = read(OUT / "ADJUDICATION.json")
assert adjudication["complete"] and not adjudication["historical_verdicts_joined"]
assert sha(OUT / "ADJUDICATION.json") == "445bf654239743b706db9f2a791671f979e6c26a6241111d83ce45f56419b198"
prereg = read(OUT / "PREREG.json")
reference_adjudication = read(REFERENCE / "ADJUDICATION.json")
reference_verdicts = {r["id"]: r for r in reference_adjudication["rows"]}
assert sha(REFERENCE_PRIVATE / "results.jsonl") == reference_adjudication["raw_results_sha256"]
reference_results = jsonl(REFERENCE_PRIVATE / "results.jsonl")
results = jsonl(PRIVATE / "results.jsonl")
requests = jsonl(PRIVATE / "requests.jsonl")
reference_requests = jsonl(REFERENCE_PRIVATE / "requests.jsonl")
panel_path = BASE / "K2_HORIZON_NATIVE699/PANEL.json"
assert sha(panel_path) == reference_adjudication["panel_sha256"]
panel = {r["id"]: r for r in read(panel_path)}
assert [r["case"] for r in results] == prereg["cases"] == [r["case"] for r in reference_results]
assert len(results) == 50 and set(adjudication["cases"]) == set(panel)
for before, after in zip(reference_requests, requests, strict=True):
    normalized = json.loads(json.dumps(after))
    assert normalized["payload"]["chat_template_kwargs"].pop("enable_thinking") is False
    assert normalized == before
old_prompts = {r["case"]: r["prompt"] for r in jsonl(REFERENCE_PRIVATE / "rendered-prompts.jsonl")}
rendered = jsonl(PRIVATE / "rendered-prompts.jsonl")
assert len(rendered) == 50
assert all(r["native"] == old_prompts[r["case"]] for r in rendered)
resources = read(OUT / "RESOURCES.json")
reference_resources = read(REFERENCE / "RESOURCES.json")
assert read(OUT / "EXIT.json")["exit_code"] == 0
assert resources["manifest_unchanged"] and resources["source_unchanged"] and not resources["violations"]
assert sha(ROOT / "src/baxy_mind/llm.py") == prereg["llm_source_sha256"]


def timings(rows):
    first = [r["first_content_seconds"] for r in rows if "first_content_seconds" in r]
    return {"final_median_seconds": statistics.median(r["seconds"] for r in rows),
            "final_maximum_seconds": max(r["seconds"] for r in rows),
            "first_visible_median_seconds": statistics.median(first),
            "first_visible_samples": len(first),
            "finish_reasons": dict(Counter(r.get("finish_reason") for r in rows))}


paired = []
for row in results:
    ident = row["case"]
    before = reference_verdicts[ident]["passed"]
    after = adjudication["cases"][ident]["correct"]
    paired.append({"id": ident, "before": before, "after": after,
                   "change": "unchanged" if before == after else "gain" if after else "loss",
                   "reason": adjudication["cases"][ident]["reason"],
                   "answer_sha256": hashlib.sha256(row["content"].encode()).hexdigest()})
summary = {
    "utc": datetime.now(timezone.utc).isoformat(), "case_count": 50,
    "before_correct": sum(r["before"] for r in paired), "after_correct": sum(r["after"] for r in paired),
    "sensitivity_after_correct": 20,
    "gains": [r["id"] for r in paired if r["change"] == "gain"],
    "losses": [r["id"] for r in paired if r["change"] == "loss"],
    "shared_failures": [r["id"] for r in paired if not r["before"] and not r["after"]],
    "timings_native_high": timings(reference_results), "timings_thinking_disabled": timings(results),
    "resources_native_high": reference_resources, "resources_thinking_disabled": resources,
    "actual_server_template_native_matches_historical": 50,
    "actual_server_template_only_adds_thinking_close": 50,
    "actual_post_native_bodies_unchanged": 50,
    "payload_pairs_equal_except_thinking_flag": 50,
    "by_input_language": {lang: {"cases": sum(r["language"] == lang for r in panel.values()),
                                   "before_correct": sum(v["before"] for v in paired if panel[v["id"]]["language"] == lang),
                                   "after_correct": sum(v["after"] for v in paired if panel[v["id"]]["language"] == lang)}
                          for lang in ("es", "en", "mix")},
    "rows": paired, "adopted": False, "coverage_added": 0,
    "limits": "Historical single-seed control and practical8k/4096output profile. One payload flag changes; no full BAXY integration or unquantized-backend parity. This does not rank K2 against Qwen or test other BAXY layers. Server process-tree memory samples250ms, excludingUI/TTS and shorter unsampled peaks. Native server terminated by the driver after all50 responses: backend_exit1 is deliberate Windows termination, not a spontaneous model crash.",
    "hashes": {"prereg": sha(OUT / "PREREG.json"), "adjudication": sha(OUT / "ADJUDICATION.json"),
               "results": sha(PRIVATE / "results.jsonl"), "requests": sha(PRIVATE / "requests.jsonl"),
               "rendered_prompts": sha(PRIVATE / "rendered-prompts.jsonl"),
               "reference_adjudication": sha(REFERENCE / "ADJUDICATION.json"),
               "reference_results": sha(REFERENCE_PRIVATE / "results.jsonl"), "panel": sha(panel_path)},
}
write(OUT / "SUMMARY.json", summary)
before, after = summary["timings_native_high"], summary["timings_thinking_disabled"]
report = f"""# Una opción de BAXY perjudica el perfil local de K2

El mismo K2 3.7B Q4 pasó de **{summary['before_correct']}/50 a {summary['after_correct']}/50** al añadir únicamente `enable_thinking=false`, la opción que envía el selector actual de BAXY. Un segundo lector aceptaría una reescritura fronteriza y elevaría el resultado a20/50; la discrepancia y los dos razonamientos se conservan. El resultado justifica corregir esa adaptación antes de juzgar K2 dentro del producto. No justifica descartar K2 ni declara que todas las reglas favorezcan a Qwen.

Se conservaron las50 tareas sintéticas699 completas, pesos, backend, orden, semilla, muestreoT1/p0.95, contexto8192, salida4096 y servidor con razonamiento alto. Cada petición cambió sólo esa clave. El servidor verificó50/50 prefijos: el nuevo flag añade el cierre del razonamiento; los prefijos originales coinciden exactamente con los50 guardados en699. El método real `_post` conserva intactas esas50 peticiones nativas; no tenían varios mensajes system. La fusión de múltiples systems no queda evaluada por esta igualdad.

La receta oficial K2 recomienda razonamiento alto y al menos32768tokens de margen de salida. El perfil8k/4096 es el práctico ya medido, no la receta de evaluación oficial completa. El servidor siguió en high/on con presupuesto-1 para aislar la opción de la petición; no se añadieron además los flags off/budget0, temperatura0 o256tokens de BAXY. [Ficha oficial](https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices).

| Medida | Perfil high699 | Mismo perfil +flag de BAXY |
|---|---:|---:|
| Respuestas que cumplen | {summary['before_correct']}/50 | {summary['after_correct']}/50 (20 si se acepta el fronterizo) |
| Primer texto, mediana | {before['first_visible_median_seconds']:.3f}s | {after['first_visible_median_seconds']:.3f}s |
| Final, mediana | {before['final_median_seconds']:.3f}s | {after['final_median_seconds']:.3f}s |
| Final más lento | {before['final_maximum_seconds']:.3f}s | {after['final_maximum_seconds']:.3f}s |
| VRAM pico del servidor | {reference_resources['gpu_peak_mib']:.2f}MiB | {resources['gpu_peak_mib']:.2f}MiB |
| RAM pico del servidor | {reference_resources['ram_peak_mib']:.2f}MiB | {resources['ram_peak_mib']:.2f}MiB |

Comparación porcaso: **{len(summary['gains'])}mejoras, {len(summary['losses'])}pérdidas y {len(summary['shared_failures'])}fallos compartidos**. Español:{summary['by_input_language']['es']['before_correct']}/30→{summary['by_input_language']['es']['after_correct']}/30; inglés:{summary['by_input_language']['en']['before_correct']}/15→{summary['by_input_language']['en']['after_correct']}/15; mezcla:{summary['by_input_language']['mix']['before_correct']}/5→{summary['by_input_language']['mix']['after_correct']}/5. Los tres finales truncados del perfil modificado cuentan como fallos; una apertura correcta seguida de falsedades tampoco aprueba.

Los veredictos nuevos se sellaron antes de unir los anteriores. Se reutilizó un control histórico de una semilla: no es una réplica aleatorizada ni una medida universal de causalidad o calidad. Los picos se muestrean cada250ms y corresponden sólo al árbol del servidor; no acreditan UI/voz ni el techo conjunto del producto. La tanda terminó50/50, exit0, sin infracciones del guardián de recursos; después el conductor cerró su servidor. Runtime registrado y fuente de BAXY quedaron intactos.

**Decisión:** K2 debe conservar razonamiento nativo en su adaptador experimental. La comparación integrada sigue pendiente: hay que mantener su receta también en los demás roles y comprobar la primera transformación incorrecta en catálogo, argumentos, validación y publicación. Qwen permanece provisional. Ninguna adopción ni crédito de encuesta:26cubiertos/716abiertos/0NA; C03 sigue abierto.

[Entradas y respuestas completas](RESPUESTAS.md) · [Resumen y pares](SUMMARY.json) · [Criterios originales](../K2_HORIZON_NATIVE699/PANEL.json) · [Adjudicación previa a la comparación](ADJUDICATION.json).
"""
assert not (OUT / "REPORT.md").exists()
(OUT / "REPORT.md").write_text(report, encoding="utf-8")
answers = ["# K2 — mismas50 tareas con thinking desactivado\n\nDesarrollo sintético, no aceptación del producto. Se preservan íntegros los errores y cortes.\n"]
for row in results:
    ident = row["case"]
    case = panel[ident]
    verdict = adjudication["cases"][ident]
    answers.append(f"\n## {ident} — {'cumple' if verdict['correct'] else 'falla'}\n\n")
    for message in case["payload"]["messages"]:
        answers.append(f"**{message['role']}:**\n\n" + "\n".join("> " + line for line in message["content"].splitlines()) + "\n\n")
    answers.append("**Respuesta visible completa:**\n\n" + "\n".join("> " + line for line in row["content"].splitlines()) + "\n\n")
    answers.append(f"Criterio original: {case['rubric']}\n\nJuicio: {verdict['reason']}\n\n")
    answers.append(f"Final:{row.get('finish_reason')}; tiempo:{row['seconds']:.3f}s; error:{row.get('error')}.\n")
assert not (OUT / "RESPUESTAS.md").exists()
(OUT / "RESPUESTAS.md").write_text("".join(answers), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("before_correct", "after_correct", "gains", "losses", "shared_failures", "timings_native_high", "timings_thinking_disabled", "by_input_language")}))
