"""Publish root's already recorded judgments for the two803 segments; no grading rules."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
base = Path("C:/Users/usuario/AppData/Local/BAXY")
out = root / "artifacts/comprobaciones/C03/PROCESS_BATCH803"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


panel = read(base / "C03-process-panel795-private/panel.json")
first = base / "C03-process-batch803-private"
second = base / "C03-process-batch803-resume-private"
segments = [(first, "live-review.json"), (second, "review.json")]
cases = []
markdown = ["# Respuestas803 — adjudicación de la raíz",
            "50 casos en segmentos9+41 con perfiles distintos. El intento interrumpido queda en el primer segmento.\n"]
for private, review_name in segments:
    review = read(private / review_name)
    judgments = read(private / "root-adjudication.json")
    assert len(review) == len(judgments)
    for row in review:
        judgment = judgments[row["case_id"]]
        cases.append({"case_id": row["case_id"], "group": row["group"], **judgment,
                      "segment": private.name, "turn_id": row["turn_id"],
                      "terminal_kind": row["terminal"]["kind"]})
        label = "VÁLIDO" if judgment["passed"] else "SIN CRÉDITO"
        markdown += [f"## {row['case_id']} · {label}",
                     f"**Entrada:** {row['text']}", f"**Respuesta:** {row['terminal']['final']}",
                     f"**Juicio raíz:** {judgment['reason']}",
                     f"**Evidencia:** {private.name}/{review_name}, {row['turn_id']}",
                     "```json\n" + json.dumps({"criterion": row["criterion"],
                        "core_calls": row["core_calls"], "compose": row["compose"]},
                        ensure_ascii=False, indent=2) + "\n```"]
assert [c["case_id"] for c in cases] == [c["case_id"] for c in panel]
assert len(cases) == 50
old_text = (base / "C03-process-batch801-private/RESPUESTAS.md").read_text(encoding="utf-8-sig")
old = {case: label == "VÁLIDO" for case, label in re.findall(r"^## t\d+ · (\S+) · (.+)$", old_text, re.M)}
assert len(old) == 50 and sum(old.values()) == 35
gains = [c["case_id"] for c in cases if c["passed"] and not old[c["case_id"]]]
losses = [c["case_id"] for c in cases if not c["passed"] and old[c["case_id"]]]
valid = sum(c["passed"] for c in cases)
by_group = {group: dict(Counter("valid" if c["passed"] else "failed" for c in cases if c["group"] == group))
            for group in dict.fromkeys(c["group"] for c in cases)}
result = {"method": "Root read every final against observed facts and the original criterion. This script only assembles those saved verdicts.",
          "candidate": 802, "adopted": False, "segments": [9, 41], "continuous_50": False,
          "valid": valid, "failed": 50 - valid, "by_group": by_group,
          "versus801": {"valid": 35, "gains": gains, "losses": losses}, "cases": cases,
          "evidence_sha256": {str(p): sha(p) for p in (
              first / "root-adjudication.json", second / "root-adjudication.json",
              first / "live-review.json", second / "review.json")},
          "survey_counts": {"covered": 28, "open": 714, "not_applicable": 0}}
write(out / "COMBINED_ROOT_ADJUDICATION.json", result)
write(out / "VERIFICATION_STATUS.json", {
    "source_candidate": 802, "source_adopted": False, "new_coverage": 0,
    "survey_counts": result["survey_counts"],
    "cases": [{"case_id": c["case_id"], "verification_status": "open", "candidate_pass": c["passed"],
               "reason": c["reason"]} for c in cases if c["case_id"].startswith("H")]})
destination = second / "RESPUESTAS_COMBINADAS_ADJUDICADAS.md"
assert not destination.exists()
destination.write_text("\n\n".join(markdown) + "\n", encoding="utf-8")
report = f"""# Confirmación803 de procesos — candidato802 sin adoptar

La raíz adjudicó **{valid}/50 válidos y{50-valid}/50 fallidos**. Frente801 (35/50), hay{len(gains)} ganancias y{len(losses)} pérdidas; no se adopta800/802. Los hechos del PC cambiaron entre momentos: cada respuesta se juzga contra su observación propia. Se conservan todos los veredictos801.

| Segmento | Finales | Válidos | Salida | Pico VRAM | Pico RAM residente |
|---|---:|---:|---|---:|---:|
|803 inicial|9|3|1, guarda RAM; siguiente intento interrumpido|3497,56MiB|2350,11MiB|
|803 continuación|41|25|0;617,734s; sin violaciones|3497,56MiB|2436,58MiB|

Son9+41 en perfiles distintos, no50 continuos. Techo conjunto GPU4GB; las guardas3800MiB GPU/768MiB RAM libre no se relajaron. La fuente, manifiesto y DLL quedaron intactos en ambos segmentos. El primer fallo de recursos permanece registrado.

Las listas largas agotan la composición: el selector C# conserva5s de transporte/4s internos para procesos aunque Python802 permita512tokens. Los conteos12/12 funcionan. Los casos con listas parciales, identidades ambiguas y memoria de proceso atribuida a una app siguen fallando. La cifraCPU5,72% del caso cpu_rank-02 conserva un truncamiento de5,725877% inferior a una centésima de punto; se registra expresamente esa precisión limitada.

Siguiente diferencia804: ampliar el selector de inventario denso existente a procesos, conservando5/10s GPU y60/130s CPU. Validar pruebas dueñas, Fast y Full en ventana sin inferencia, y confirmar el mismo panel. La propuesta de nuevo verificador de identidades queda fuera: todavía rechaza un orden válido de columnas y no demuestra recuperación de producto. No acumular otra capa antes de medir el plazo.

Encuesta28 cubiertos/714 abiertos/0 no aplican sobre742;0 créditos nuevos. Matriz3/11 cumplidas. Esta confirmación no acredita UI visible ni audio.

Entradas, respuestas, payloads y motivos de la raíz: [respuestas privadas]({destination.as_posix()}). Per-case y comparación: [adjudicación](COMBINED_ROOT_ADJUDICATION.json). El proceso de continuación terminó y fue recogido en sesión39798; no hay procesos BAXY activos.
"""
assert not (out / "COMBINED_REPORT.md").exists()
(out / "COMBINED_REPORT.md").write_text(report, encoding="utf-8")
print(json.dumps({"valid": valid, "failed": 50-valid, "gains": gains, "losses": losses, "by_group": by_group}))
