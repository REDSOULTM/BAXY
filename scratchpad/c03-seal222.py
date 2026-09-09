"""Seal220–222 evidence and preserve the source before the segmentation edit."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

old = json.loads((BASE / "astra-source218-snapshot/FILES.json").read_text(encoding="utf-8"))
snapshot = BASE / "astra-source220-snapshot"
snapshot.mkdir(exist_ok=False)
for relative, expected in old.items():
    if relative != "src/baxy_mind/voice_capture.py":
        assert sha(ROOT / relative) == expected, relative
paths = list(old) + ["tests/test_voice_capture_clock.py"]
for relative in paths:
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, target)
save(snapshot / "FILES.json", {p: sha(ROOT / p) for p in paths})
public = [ROOT / "scratchpad" / name for name in ["c03-capture220.py", "c03-voice221.py", "c03-replay222.py", "c03-seal222.py"]]
public += [BASE / name for name in ["PRUEBAS_RAW220_221.md", "DIAGNOSTICO_SEGMENTACION222.md"]]
for folder in ["astra-capture220", "astra-voice221", "astra-replay222", "astra-source220-snapshot"]:
    public += [p for p in (BASE / folder).rglob("*") if p.is_file()]
private = []
for folder in ["astra-voice221", "astra-replay222"]:
    rows = json.loads((BASE / folder / "RESULTS.json").read_text(encoding="utf-8"))["privateFiles"]
    for row in rows:
        assert sha(Path(row["path"])) == row["sha256"]
        private.append(row)
pins = {"utc": datetime.now(timezone.utc).isoformat(),
    "public": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in public], "private": private}
save(BASE / "TRAMO220_222_PINS.json", pins)
state = """Fuente220: captura RAW integrada, sounddevice0.5.5 CFFI streamOption; Speex y
umbrales intactos. Componente físico250frames/8s, efectos[] y reloj creciente.
35tests pass/0skips en53.05s; Ruff/Fast verdes, Release7.06s0avisos/errores.
221VoiceEngine directo físico42.112s/1316frames,4Piper,0barge/errores,1texto
espurio Let's see. Volumen exactamente restaurado0/mutedtrue, workers cerrados.
222 reproduce ese segmento frames162–195/1.088s y texto, VAD1316exactos,
7guard exactos.4frames bajo energía vigente se rechazan para barge pero dejan
speech=True y abren ASR. DIAGNOSTICO_SEGMENTACION222 documenta causa/propuesta.

Siguiente223: prueba dueña roja antes del arreglo; en la rama de energía
insuficiente durante speaking, speech=False con el umbral existente. Conservar
primeros bloques humanos válidos y voz baja fuera TTS. Repetir exacto221 sin
nueva captura a ciegas; luego controles humanos. Fuente220snapshot sellada;
no modificar scripts220–222/resultados. Runtime baxy.2 y modelos intactos.
Procesos27267/58031/23497 recogidos exit0;220/222 síncronos terminales. Ninguno
propio activo. No Full ni UI nuevos. TRAMO220_222_PINS conserva evidencia.

C03 íntegro EN_CURSO: errores de contenido217, wake calibrado,voz humana,
ocho rutas,100humanos aún sin congelar y100/100,averías/recuperación,UI/audio
final,4GB conjuntos,runtime/instalación,C04–C09,Full/publicación. Sin bloqueo
externo. Tres turnos ingleses admitidos; búsqueda de audioPC autorizada y parcial.
"""
for filename, title in [("CHECKPOINT.md", "checkpoint222"), ("HANDOFF.md", "handoff222")]:
    path = BASE / filename
    text = path.read_text(encoding="utf-8")
    path.write_text(f"# C03 — {title} — EN_CURSO —2026-09-07\n\n{state}\n## Estado anterior conservado —219\n\n{text}", encoding="utf-8")
path = BASE / "RELEVO_ACTIVO.json"
relevo = json.loads(path.read_text(encoding="utf-8"))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="222: RAW220 integrado/Fast verde; voz221 sin cortes pero texto espurio; replay222 exacto localiza rama speech=True bajo energía.", continuation="223: prueba dueña y corrección de admisión coherente con energía de barge; controles humanos sin relajar umbrales. C03 íntegro activo.")
save(path, relevo)
print(json.dumps({"public": len(public), "private": len(private), "checkpoint": 222}))
