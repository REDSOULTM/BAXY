"""Seal227–235 and checkpoint the source230 acoustic work without claiming acceptance."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for relative, expected in read(BASE / "astra-source230-snapshot/FILES.json").items():
    assert sha(ROOT / relative) == expected, relative
assert read(BASE / "astra-baseline235/PREREG.json")["sourceSha256"] == read(BASE / "astra-source225-snapshot/FILES.json")["src/baxy_mind/voice.py"]
assert "127 passed" in (BASE / "astra-segmentation230/OWNERS.log").read_text(encoding="utf-8-sig")
assert "source_quality_gate_passed: mode=Fast" in (BASE / "astra-segmentation230/Fast.log").read_text(encoding="utf-8-sig")
physical = read(BASE / "astra-voice232/RESULTS.json")
assert physical["restoredExactly"] and not any(physical["workersAlive"].values()) and not physical["outputWorkerAlive"]
assert physical["bargeInCount"] == 2 and physical["transcriptCount"] == 1
assert read(BASE / "astra-replay233/RESULTS.json")["segments"] == read(BASE / "astra-baseline235/RESULTS.json")["segments"]
rows = read(BASE / "astra-human231/RESULTS.json")
lines = ["# C03 — comparación literal231: fuente225 frente230", "",
    "Ocho controles213. Todos los segmentos humanos se conservan exactamente; sólo se retiran dos segmentos espurios separados.",
    "La paridad conserva errores ASR previos; no equivale a ocho pases semánticos.", ""]
for row in rows:
    before, after = row["variants"]
    expected = before["segments"][1:] if row["human"] in {0, 1} and row["condition"] == "raw_speex" else before["segments"]
    assert after["segments"] == expected
    assert before["cancellations"] == after["cancellations"]
    lines += [f'## Humano{row["human"]} — {row["condition"]}', "", "Referencia:", "", f'> {row["reference"]}', ""]
    for variant in row["variants"]:
        lines += [f'### {variant["source"]}', "", f'Cancelaciones con máscara fija: {variant["cancellations"]}.', ""]
        for index, segment in enumerate(variant["segments"]):
            lines += [f'Segmento{index}, muestras{segment["firstSample"]}–{segment["lastSample"]} (fin exclusivo):', "", f'> {segment["text"] or "[vacío]"}', ""]
(BASE / "COMPARACION_LITERAL231.md").write_text("\n".join(lines), encoding="utf-8")
diff = []
for relative in ["src/baxy_mind/voice.py", "tests/test_mind_voice_runtime.py"]:
    before = (BASE / "astra-source225-snapshot" / relative).read_text(encoding="utf-8")
    after = (ROOT / relative).read_text(encoding="utf-8")
    diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=f"225/{relative}", tofile=f"230/{relative}"))
(BASE / "astra-segmentation230/DELTA_FROM225.diff").write_text("".join(diff), encoding="utf-8")
folders = ["astra-admission227", "astra-segmentation228", "astra-replay228", "astra-human229", "astra-source228-snapshot",
    "astra-segmentation230", "astra-replay230", "astra-human231", "astra-source230-snapshot", "astra-voice232",
    "astra-replay233", "astra-echo234", "astra-baseline235"]
scripts = ["c03-admission227.py", "c03-replay228.py", "c03-human229.py", "c03-replay230.py", "c03-human231.py",
    "c03-voice232.py", "c03-replay233.py", "c03-echo234.py", "c03-baseline235.py", "c03-seal235.py"]
public = [ROOT / "scratchpad" / name for name in scripts]
public += [BASE / name for name in ["DIAGNOSTICO_ADMISION227_229.md", "PRUEBAS_ADMISION230_232.md",
    "DIAGNOSTICO_ECO233_235.md", "COMPARACION_LITERAL231.md"]]
for folder in folders:
    public += [p for p in (BASE / folder).rglob("*") if p.is_file()]
private = []
for folder in ["astra-replay228", "astra-replay230", "astra-voice232", "astra-replay233", "astra-baseline235"]:
    private += read(BASE / folder / "RESULTS.json")["privateFiles"]
for folder in ["astra-human229", "astra-human231"]:
    for row in read(BASE / folder / "RESULTS.json"):
        private += [{"path": v["privatePath"], "sha256": v["sha256"]} for v in row["variants"]]
for row in private:
    assert sha(Path(row["path"])) == row["sha256"]
save(BASE / "TRAMO227_235_PINS.json", {"utc": datetime.now(timezone.utc).isoformat(),
    "public": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in public], "private": private})
state = """Fuente230 vigente (snapshot230), RAW220 y baxy.2 intactos. Admisión de barge
usa el búfer utterance existente como candidato, sin ducking/streaming/ASR
hasta3frames consecutivos o voz después de terminar TTS; descarta candidato
no admitido al finalizar. Helperadmit_utterance retira duplicación previa.
228esperaba3frames antes de guardar y perdió Se; rechazada/snapshot228.
230preserva prefijo y continuidad:127pass/0skips5.37s,Ruff/Fast verdes,
Release1.14s0avisos/errores.231 conserva exactamente8segmentos humanos213;
sólo elimina dos segmentos espurios separados.8/8cancelaciones iguales.
La fidelidad ASR previa (30→3,otraspalabras) sigue abierta.

232físico source230:1316frames42.112s,4Piper,2barge/1texto espurio Toll.
Segundo ASR S descartado por dudoso. EfectosRAW[],0erroresdispositivo,
volumen exactamente0/mutedtrue restaurado y workers cerrados. NOaceptación.
233replay reproduce2cortes135/442,VAD1316exactos,10guardasexactas,
segmentos125–163 y432–470,1.248s,Toll./S.235source225 anterior produce
exactamente lo mismo con señal232: no atribuir el fallo acústico al cambio230.
234Speexfresh221+232 reproduce2632/2632frames exactamente. Guardas512 de
los6frames de disparo0.446–0.522<0.55; referencia sí existe, largas1024/2048/
4096 tampoco superan0.55,lag largo~314samples20ms dentro250ms. No barrer
umbrales ni ampliar historial. DIAGNOSTICO_ECO233_235 recoge datos/límites.

Siguiente236: comparación acotada con DTLN128 heredado182, leyendo primero
adaptador/evidencia concreta. Causas nuevas respecto al rechazo anterior:
RAWsinAEC/NS Windows y normalización baxy.2 corregida218. Señales232fallida,
221control y mismos4humanos195 con construcción RAW213, condiciones
congeladas antes de ASR. Medir fidelidad y eco juntos; no adoptar por cero
eco ni instalar bundle experimental. No repetir capturas físicas a ciegas.

Procesos39431/8079humanos,99257Fast,98403físico232 recogidos exit0;
227/228/230/233/234/235resto síncronos terminales. Ninguno propio activo.
TRAMO227_235_PINS y snapshot230 sellados; no editar scripts/resultados.
Último verdeFull noactual: NOFull/UI/LLM final nuevos. Wake sigue unavailable
porwake_verifier_manifest_missing, sin eludircalibración.

C03 íntegro EN_CURSO:ASR/eco/wake/voz humana física,8rutas,100humanos
frescos aún sin congelar y100/100,averías/recuperación,UI/audiofinal,4GB
conjuntos,runtime/instalación,C04–C09,Full/publicaciónfuera main. Sin bloqueo
externo.3ingleses admitidos,búsquedaaudioPC autorizada/parcial.
"""
for filename, label in [("CHECKPOINT.md", "checkpoint235"), ("HANDOFF.md", "handoff235")]:
    path = BASE / filename
    path.write_text(f"# C03 — {label} — EN_CURSO —2026-09-07\n\n{state}\n## Estado anterior229\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
path = BASE / "RELEVO_ACTIVO.json"
relevo = read(path)
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="235: fuente230 admisión provisional conserva humanos y elimina2segmentos espurios; físico232 aún2cortes, reproducidos en225y230; DSP234exacto. C03 íntegro activo.", continuation="236 comparación heredada DTLN128 con nuevas condiciones RAW/baxy.2, señales232/221 y humanos213; sinpromoción ni umbrales. Snapshot230actual.")
save(path, relevo)
print(json.dumps({"public": len(public), "private": len(private), "checkpoint": 235}))
