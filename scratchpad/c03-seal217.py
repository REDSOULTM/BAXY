"""Seal numeric cause215–217 and checkpoint the remaining integration."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert all(sha(ROOT / name) == value for name, value in read(BASE / "astra-source207-snapshot/FILES.json").items())
manifest = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
assert sha(manifest) == "13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed"
rows = read(BASE / "astra-normalize-regression217/RESULTS.json")
assert len(rows) == 126
lines = ["# C03 — comparación literal217", "", "126 lecturas, no126 pases. Índices0–46 corresponden a203/205;47–62 a213.", ""]
for row in rows:
    lines.extend([f'## Entrada{row["index"]} · {row["method"]}', "",
        f'Contexto: {json.dumps({k: v for k, v in row.items() if k in ["source", "case", "segment", "human", "condition"]}, ensure_ascii=False)}', "",
        f'Antes: {json.dumps(row["previous"], ensure_ascii=False)}', "",
        f'Después: {json.dumps(row["text"], ensure_ascii=False)}', ""])
(BASE / "COMPARACION_LITERAL217.md").write_text("\n".join(lines), encoding="utf-8")
groups = ["native-trace215", "native-trace215-retry", "normalize216", "normalize-regression217"]
public = [BASE / "PRUEBAS_NORMALIZACION215_217.md", BASE / "COMPARACION_LITERAL217.md", Path(__file__)]
private = []
for name in groups:
    folder = BASE / f"astra-{name}"
    assert (folder / ("FAILURE.json" if name == "native-trace215" else "COMPLETE.json")).exists()
    public.extend(p for p in folder.iterdir() if p.is_file())
    folder = PRIVATE / f"C03-{name}-private"
    if folder.exists():
        private.extend(p for p in folder.iterdir() if p.is_file())
for name in ["c03-prepare-native215.py", "c03-prepare-native215-retry.py", "c03-native-trace215.py",
             "c03-normalize216.cpp", "c03-prepare-normalize216.py", "c03-normalize216.py", "c03-normalize-regression217.py"]:
    public.append(ROOT / "scratchpad" / name)
for name in ["astra-native-trace215-retry", "astra-normalize216"]:
    build = read(BASE / name / "BUILD_COMPLETE.json")
    for row in build["binaries"]:
        path = Path(row["path"])
        assert sha(path) == row["sha256"]
        private.append(path)
    for name, expected in read(BASE / name / "SOURCE_RESTORED.json").items():
        assert sha(Path("D:/BAXYRuntime/experiments/voice/sherpa205/source") / name) == expected
def pin(path, is_public):
    return {"path": path.relative_to(ROOT).as_posix() if is_public else str(path), "sha256": sha(path), "bytes": path.stat().st_size}
target = BASE / "TRAMO215_217_PINS.json"
assert not target.exists()
pins = {"public": [pin(p, True) for p in public], "private": [pin(p, False) for p in private]}
save(target, pins)
header = """# C03 — checkpoint217 — EN_CURSO —2026-09-07

215 localiza tensor anómalo ANTES del encoder: máximos24348/2392/24335 en3vacíos,
control15.1. Observador nativo reproduce4/4 resultados214; sinNaN/Inf, todo blank
en3fallos. Causa: NemoNormalizePerFeature usa varianza E[x²]−E[x]² float32.
216 aplica PR3857 oficial fusionada(merge0967a08db705d8eec9cf5cef962c8ec57c16e4a8).
Mismo observador, sólo math.cc/math-test.cc: características acotadas24–34/std1;
3vacíos recuperan contenido/controlidéntico. Witness nativo7510.85→31.46; constante0.

217126lecturas(63PCM×greedy/beam),13cambiosgreedy/63 y16beam/47baseline. No126pases.
Regresiones abiertas: índice3case3 mezcla sinAEC pierde humano por saludo;11pierde
acceder;56h2nearSpeex cambia30→3años enambosdecoders.50RAW+Speex recupera humano
coneco inicialgreedy. Beam silencioGracias y pierde cláusula case15: no volver a
beam principal. PRUEBAS_NORMALIZACION215_217 y COMPARACION_LITERAL217 conservan todo.

Fuente207/baxy.1/registro intactos y verificados; corrección216 NOinstalada. Siguiente:
integrar matemática3857 como candidata reproducible baxy.2, SIN observación215,
actualizar receta/patch/lock/licencias y tests correspondientes; no afirmar ASR
resuelto ni regresión217verde. Después retomar RAW/Speex212 y audio físico con
normalizador válido; defectos de fidelidad/eco217 siguen pendientes del mismo goal.
No instalar bundle-normalize216, contiene observación. No barrer gains/umbrales.

Todos procesos recogidos:45736/92403builders,94064regresión exit0; runs215/216síncronos.
Primer preparador215 falló marcadorCRLF antes de editar; reintento conserva/restaura
bytes originales. Fuentes externas restauradas a207; bundles aislados conservados.
TRAMO215_217_PINS sella evidencia. Ningún proceso propio activo. NoFast/Full nuevos.

Mantener C03 completo activo: voz/wake/ocho rutas/100humanos aún sin congelar y100/100/
averías/recuperación/UI/audiofísico/4GB/runtime/instalación/C04–C09/Full/publicación.
No bloqueo externo. Tres ingleses admitidos; Grabación(2) opcional sinrespuesta.

## Estado anterior conservado —214

"""
for name in ["CHECKPOINT.md", "HANDOFF.md"]:
    path = BASE / name
    prefix = header if name == "CHECKPOINT.md" else header.replace("checkpoint217", "handoff217")
    path.write_text(prefix + path.read_text(encoding="utf-8"), encoding="utf-8")
relevo = read(BASE / "RELEVO_ACTIVO.json")
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint="217: normalización float32 defectuosa demostrada; PR3857 recupera3vacíos.126lecturas con regresiones explícitas, no aceptación. Fuente207/baxy.1 intactos.",
    continuation="Integrar corrección matemática sin instrumentación como candidata baxy.2 reproducible, preservando fallos217 y alcance completo. Ningún proceso activo.")
save(BASE / "RELEVO_ACTIVO.json", relevo)
assert all(sha(ROOT / r["path"]) == r["sha256"] for r in pins["public"])
assert all(sha(Path(r["path"])) == r["sha256"] for r in pins["private"])
print(json.dumps({"public": len(public), "private": len(private), "source207Verified": True}))
