"""Seal the segmentation fix, human comparisons and current225 source."""
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
assert read(BASE / "astra-human226/COMPLETE.json") == {
    "cases": 8, "identicalSegments": 8, "identicalCancellations": 8, "exitCode": 0}
assert not read(BASE / "astra-replay225/RESULTS.json")["segments"]
assert "123 passed" in (BASE / "astra-segmentation225/OWNERS.log").read_text(encoding="utf-8-sig")
assert "source_quality_gate_passed: mode=Fast" in (BASE / "astra-segmentation225/Fast.log").read_text(encoding="utf-8-sig")
prior = read(BASE / "astra-source220-snapshot/FILES.json")
snapshot = BASE / "astra-source225-snapshot"
snapshot.mkdir(exist_ok=False)
for relative, expected in prior.items():
    if relative not in {"src/baxy_mind/voice.py", "tests/test_mind_voice_runtime.py"}:
        assert sha(ROOT / relative) == expected, relative
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, target)
save(snapshot / "FILES.json", {p: sha(ROOT / p) for p in prior})
diff = []
for relative in ["src/baxy_mind/voice.py", "tests/test_mind_voice_runtime.py"]:
    before = (BASE / "astra-source220-snapshot" / relative).read_text(encoding="utf-8")
    after = (ROOT / relative).read_text(encoding="utf-8")
    diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=f"220/{relative}", tofile=f"225/{relative}"))
(BASE / "astra-segmentation225/DELTA_FROM220.diff").write_text("".join(diff), encoding="utf-8")
lines = ["# C03 — comparación literal226, fuente220 frente225", "",
    "Cuatro humanos195, cada uno solo+Speex y con eco RAW+Speex. Entradas213 congeladas.",
    "8/8paridades de segmentos y cancelaciones; errores ya existentes conservados.", ""]
for row in read(BASE / "astra-human226/RESULTS.json"):
    lines += [f'## Humano{row["human"]} — {row["condition"]}', "", "Referencia humana:", "", f'> {row["reference"]}', ""]
    for variant in row["variants"]:
        lines += [f'### {variant["source"]}', "", f'Frames de solicitud de interrupción con máscara fija: {variant["cancellations"]}.', ""]
        for index, segment in enumerate(variant["segments"]):
            lines += [f'Segmento{index}, muestras{segment["firstSample"]}–{segment["lastSample"]} (fin exclusivo):', "", f'> {segment["text"] or "[vacío]"}', ""]
(BASE / "COMPARACION_LITERAL226.md").write_text("\n".join(lines), encoding="utf-8")
public = [ROOT / "scratchpad" / p for p in ["c03-replay223.py", "c03-human224.py", "c03-replay225.py", "c03-human226.py", "c03-seal226.py"]]
public += [BASE / p for p in ["PRUEBAS_SEGMENTACION223_226.md", "COMPARACION_LITERAL226.md"]]
folders = ["astra-segmentation223", "astra-replay223", "astra-human224", "astra-segmentation225", "astra-replay225", "astra-human226", "astra-source223-snapshot", "astra-source225-snapshot"]
for folder in folders:
    public += [p for p in (BASE / folder).rglob("*") if p.is_file()]
private = []
for folder in ["astra-replay223", "astra-replay225"]:
    private += read(BASE / folder / "RESULTS.json")["privateFiles"]
for folder in ["astra-human224", "astra-human226"]:
    for row in read(BASE / folder / "RESULTS.json"):
        private += [{"path": v["privatePath"], "sha256": v["sha256"]} for v in row["variants"]]
for row in private:
    assert sha(Path(row["path"])) == row["sha256"]
save(BASE / "TRAMO223_226_PINS.json", {"utc": datetime.now(timezone.utc).isoformat(),
    "public": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in public], "private": private})
state = """Fuente225 vigente: RAW220 y baxy.2 conservados; en energía insuficiente
durante salida, speech=speech_started impide abrir turno espurio sin dividir
una frase admitida. Umbrales/guardas/modelos intactos. Candidata223
speech=False rechazada por fragmentación humana224; snapshot223 conservado.
Pruebas rojas primero:223abría1segmento indebidamente;225dos segmentos en
frase continua. Final123pass/0skips5.37s,Fast exit0/Release1.17s0avisos/errores.

Replay225 exacto1316frames221:0segmentos/0cancelaciones,7guardas idénticas.
VAD difiere máximo0.00906166 después de cambiar los resets de segmentación.
2268controles213 (4humanos×solo/RAWconeco) contra220:8/8idénticos en muestras,
rangos,textos y solicitudes de cancelación. No8pases semánticos: errores de
palabras/número30→3 y saludos espurios prehumanos ya existentes permanecen.
PRUEBAS_SEGMENTACION223_226 y COMPARACION_LITERAL226 recogen literales/límites.

Siguiente: abordar el inicio espurio de mayor energía que aún aparece en
controles RAW213. Comprobar con sus mismas señales si abre un turno antes de
cumplir los3frames consecutivos que ya exige barge-in; preservar pre-roll y
continuidad humana, sin cambiar umbrales ni filtrar texto. Reutilizar226 como
control antes/después y221 como eco puro. Después verificación física225+ y
resolver fallosASR217. No repetir hardware/filtros sin localizar causa nueva.

Procesos24527/3716humanos,64651/19191Fast recogidos exit0;225tests/replay
síncronos terminados. Ninguno propio activo. Último audio físico221 previo225:
42.112s4Piper/0barge/1texto espurio, volumen restaurado exactamente0/mutedtrue.
Fuente225snapshot actual; no usar223 ni220 como actual. TRAMO223_226_PINS
sellado. No Full/UI/LLM/aceptación física humana nuevos.

Goal íntegro EN_CURSO: wake calibrado,voz humana y erroresASR,8rutas,
100humanos frescos aún sin congelar y100/100,averías/recuperación,UI/audio
final,4GB conjuntos,runtime/instalación,C04–C09,Full/publicación fuera main.
No bloqueo externo. Tres ingleses admitidos; búsqueda de audioPC autorizada
y parcial; no esperar respuesta opcional para continuar.
"""
for filename, title in [("CHECKPOINT.md", "checkpoint226"), ("HANDOFF.md", "handoff226")]:
    path = BASE / filename
    text = path.read_text(encoding="utf-8")
    path.write_text(f"# C03 — {title} — EN_CURSO —2026-09-07\n\n{state}\n## Estado anterior conservado —222\n\n{text}", encoding="utf-8")
path = BASE / "RELEVO_ACTIVO.json"
relevo = read(path)
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="226: fuente225 elimina apertura espuria de221; 8/8paridad de controles humanos213 frente220;123tests/Fast verdes. C03 íntegro activo.", continuation="Localizar aperturas de mayor energía antes de3frames consecutivos con señales213; preservar pre-roll/continuidad y controles226; luego verificación física y fallosASR217.")
save(path, relevo)
print(json.dumps({"public": len(public), "private": len(private), "checkpoint": 226}))
