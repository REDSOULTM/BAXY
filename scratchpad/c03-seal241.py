"""Seal236–241 comparisons, physical result and candidate integration handoff."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"

def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for relative, expected in read(BASE / "astra-source230-snapshot/FILES.json").items():
    assert sha(ROOT / relative) == expected, relative
assert read(BASE / "astra-dsp236/COMPLETE.json")["speexExactParities"] == 10
assert read(BASE / "astra-product237/COMPLETE.json")["speexPriorParities"] == 10
assert read(BASE / "astra-product239/COMPLETE.json")["timelines"] == 10
assert read(BASE / "astra-recognizer241/COMPLETE.json")["readings"] == 20
physical = read(BASE / "astra-voice240/RESULTS.json")
assert physical["bargeInCount"] == physical["transcriptCount"] == 0
assert physical["restoredExactly"] and not any(physical["workersAlive"].values()) and not physical["outputWorkerAlive"]
assert not physical["voiceErrors"] and not physical["driverErrors"]
metrics = read(BASE / "astra-voice240/TRACE_METRICS.json")
assert metrics["microphoneRmsWhileSpeaking"] > .001 and metrics["referenceRmsPcmWhileSpeaking"] > 20
lines = ["# C03 — literales239 y241: DTLN512 y reconocimiento independiente", "",
    "239 usa Parakeet baxy.2.241 reutiliza exactamente los segmentos/ventanas y añade los cuatro originales195, sin procesamiento AEC.",
    "No se equipara la ejecución con pases semánticos. Las referencias no se enviaron a los reconocedores.", ""]
for row in read(BASE / "astra-product239/RESULTS.json"):
    lines += [f'##239 — {row["case"]}', "", f'Cancelaciones con máscara fija: {row["cancellations"]}.', ""]
    if row["referenceText"]:
        lines += ["Referencia:", "", f'> {row["referenceText"]}', "", "Ventana fija:", "", f'> {row["humanWindowText"] or "[vacío]"}', ""]
    for index, segment in enumerate(row["segments"]):
        lines += [f'Segmento{index}, muestras{segment["firstSample"]}–{segment["lastSample"]} (fin exclusivo):', "", f'> {segment["text"] or "[vacío]"}', ""]
    if not row["segments"]:
        lines += ["Sin segmentos.", ""]
for row in read(BASE / "astra-recognizer241/RESULTS.json"):
    lines += [f'##241 — {row["case"]} / {row["kind"]}', "", "Referencia:", "", f'> {row["reference"]}', "",
        "Parakeet (resultado previo exacto):", "", f'> {row["parakeet"] or "[vacío]"}', "",
        "Nemotron:", "", f'> {row["nemotron"] or "[vacío]"}', ""]
(BASE / "COMPARACION_LITERAL239_241.md").write_text("\n".join(lines), encoding="utf-8")
folders = ["astra-dsp236", "astra-product237", "astra-dsp238", "astra-product239", "astra-voice240", "astra-recognizer241"]
scripts = ["c03-dsp236.py", "c03-product237.py", "c03-dsp238.py", "c03-product239.py", "c03-voice240.py", "c03-recognizer241.py", "c03-seal241.py"]
public = [ROOT / "scratchpad" / name for name in scripts]
public += [BASE / name for name in ["COMPARACION_DTLN236_237.md", "COMPARACION_LITERAL237.md", "RESULTADOS_DTLN238_241.md", "COMPARACION_LITERAL239_241.md"]]
for folder in folders:
    public += [p for p in (BASE / folder).rglob("*") if p.is_file()]
private = []
for folder in ["astra-dsp236", "astra-product237", "astra-dsp238", "astra-product239"]:
    private += [{"path": row["privatePath"], "sha256": row["sha256"]} for row in read(BASE / folder / "RESULTS.json")]
private += physical["privateFiles"]
for row in private:
    assert sha(Path(row["path"])) == row["sha256"]
save(BASE / "TRAMO236_241_PINS.json", {"utc": datetime.now(timezone.utc).isoformat(),
    "public": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in public], "private": private})
state = """Fuente230 y runtime baxy.2 intactos; Speex sigue productivo.236 compara
10timelines (221/232+8humanos213)×Speex/DTLN128, salidasSpeex10/10exactas.
237segmentación230+ASR de20timelines y16ventanas humanas:Speex10/10paridad;
128quita2cortes232 pero pierde cláusulas/palabras. No se adopta128.
238calcula sólo512 mismas10entradas;239segmenta10+8ventanas.512quita eco
221/232 y conserva las cláusulas que128perdía. Sigue alguna regresión ASR:
h1-near pudier acceder;h3-raw world porword;h2-raw can porcould. Recupera30
años en h2-near (Speex3). No contar8pasessemánticos ni ocultar diferencias.

240físico candidataDTLN512 con source230/RAW/Piper/baxy.2:1316frames42.112s,
4síntesis,0barge,0transcripciones,0errores. Volumen exactamente0/mutedtrue
restaurado, workerscerrados, efectosWindows[]. No entrada vacía:423frames
speaking,micRMS0.006853,refRMS896.7PCM,cleanRMS0.000734. DSPreal media10.80ms,
p9916.59ms,máx31.78ms; no presupuesto conjunto UI/LLM. Sin voz humana física
simultánea ni bypass wake. Candidata NOintegrada ni promovida aún.

241Nemotron independiente sobre8segmentos512+8ventanas+4originales195:
20lecturas con pérdidas incluso sinAEC. No justifica sustituir Parakeet ni
atribuir toda palabra ausente aDTLN. Ejemplos:originalh0 Se recomie;
h1-rawventana no todos→nos. Motor/harnessstreaming no acep. comooracle.
Leer RESULTADOS_DTLN238_241,COMPARACION_LITERAL237/239_241 completos.

Siguiente242: preparar integración reproducible DTLN512 como candidataAEC,
sin afirmar ASRresuelto. Leer ownership/schema assets/lock y guardar snapshot
previo de todoslos archivos a tocar. Una sola implementación; retirarSpeex
productivo al sustituir, conservar evidencia/DLL histórica fuera producto.
Activos/hashes/licencias/dependencias, tests dueños y Fast; después medir
producto completo con UI/LLM/voz y recursos. Mantener controles humanos239
y erroresASR explícitos; continuar su resolución antes de cierreC03.

Procesos37341/6953DSP,88245/19291ASR,63747físico,51842Nemotron recogidosexit0.
Ninguno propio activo. NoFull/Fast nuevos (sin fuente nueva); últimoFast230
verde sigue aplicando. TRAMO236_241_PINS sella evidencia. ModelosD:/experiments
dtln179/180 y LiteRTaislado; NOinstalación runtime ni cambiosregistro.
Fuenteactualsnapshot230. Wakeunavailable/wake_verifier_manifest_missing.

C03 íntegro EN_CURSO:integraciónAEC,ASR/wake/voz humana física,8rutas,
100humanos frescos aún sin congelar y100/100,averías/recuperación,UI/audio
final,4GBconjuntos,runtime/instalación,C04–C09,Full/publicaciónfuera main.
Sin bloqueo externo.3inglesesadmitidos,búsquedaaudioPCautorizada/parcial.
"""
for filename, title in [("CHECKPOINT.md", "checkpoint241"), ("HANDOFF.md", "handoff241")]:
    path = BASE / filename
    path.write_text(f"# C03 — {title} — EN_CURSO —2026-09-07\n\n{state}\n## Estado anterior235\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
path = BASE / "RELEVO_ACTIVO.json"
relevo = read(path)
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="241: DTLN512 candidato; físico240 sin cortes/textos espurios; regresiones ASR239 explícitas. Speex/source230/runtimeintactos. C03 íntegro activo.", continuation="242 integración reproducible candidataDTLN512 con activos/dependencias/owner tests, preservar controles y resolver ASR; no promoción completa C03.")
save(path, relevo)
print(json.dumps({"public": len(public), "private": len(private), "checkpoint": 241}))
