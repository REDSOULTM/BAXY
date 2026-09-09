"""Seal209–214 and preserve current handoff without mutating earlier evidence."""
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

source = read(BASE / "astra-source207-snapshot/FILES.json")
assert all(sha(ROOT / name) == expected for name, expected in source.items())
manifest = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
assert sha(manifest) == "13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed"
groups = ["aec-capability209", "aec-capability210", "raw-capture211", "raw-analysis212", "raw-human213", "native-boundary214"]
public = [BASE / "PRUEBAS_RAW209_214.md", Path(__file__)]
private = []
for name in groups:
    folder = BASE / f"astra-{name}"
    assert (folder / "COMPLETE.json").is_file()
    public.extend(p for p in folder.iterdir() if p.is_file())
    for suffix in [".py", ".cpp"]:
        path = ROOT / "scratchpad" / f"c03-{name}{suffix}"
        if path.is_file():
            public.append(path)
    folder = PRIVATE / f"C03-{name}-private"
    if folder.is_dir():
        private.extend(p for p in folder.iterdir() if p.is_file())
def pin(path, public):
    return {"path": path.relative_to(ROOT).as_posix() if public else str(path),
            "sha256": sha(path), "bytes": path.stat().st_size}
pins = {"public": [pin(p, True) for p in public], "private": [pin(p, False) for p in private],
        "source207Verified": True, "registrationUnchanged": True}
target = BASE / "TRAMO209_214_PINS.json"
assert not target.exists()
save(target, pins)
header = """# C03 — checkpoint214 — EN_CURSO —2026-09-07

Manda PRUEBAS_RAW209_214.md. Fuente207, sherpa1.13.4+baxy.1 y registro13b971b3…
verificados intactos.209 consulta efectos Windows: AEC/NS ON, control AEC ausente.
210 RAW deja lista vacía.211 verifica efectos sobre clientes PortAudio reales y
captura simultánea normal/RAW con referencia ADC4512; una reproducción30s de PCM187.
1020/1021frames, cero errores, volumen exactamente restaurado0/mutedtrue.
212 Speex igual en ambos: normal1 candidata offline a interrupción, RAW0; no evento
real BAXY ni aceptación. Sin Speex10 en ambos. No promover por puro eco.

213 cuatro humanos195 ×4condiciones=16lecturas; vacíos: h0RAW+Speex, h1RAW+Speex
y h1solo+Speex. Onda conserva correlación0,939/0,941/0,954.214 confirma vacío NATIVO
greedy antes del corrector, appliedMethod verificado; Nemotron recupera contenido
de las tres con errores.207 sólo resolvió los controles208, no todo vacíoASR.

Siguiente: localizar pérdida dentro del reconocedor nativo con cuatro ventanas214
congeladas(3fallos+1positivo), antes de sustituir modelo o añadir filtros. Conservar
mejora212 y RAW como candidato NOadoptado. No repetir capturas sin causa nueva.
Scripts/resultados y entradas sellados en TRAMO209_214_PINS. No editar lo sellado.
Procesos10218/70723/45944 recogidos exit0, resto síncronos. Ninguno propio activo.
Sin fuente nueva ni Fast/Full nuevos; últimos verdes207/208 siguen con su alcance.

Goal completo activo: activación/voz, ocho rutas,100humanos frescos aún sin congelar
y100/100,averías/UI/audio físico/4GB/runtime/instalación/continuidadC04–C09/Full/
publicación fuera main. Tres ingleses YA admitidos; no preguntar de nuevo. Procedencia
Grabación(2) opcional sin respuesta; no bloqueo externo. La búsqueda196 sigue parcial.

## Estado anterior conservado —208

"""
checkpoint = BASE / "CHECKPOINT.md"
checkpoint.write_text(header + checkpoint.read_text(encoding="utf-8"), encoding="utf-8")
handoff = BASE / "HANDOFF.md"
handoff.write_text(header.replace("checkpoint214", "handoff214") + handoff.read_text(encoding="utf-8"), encoding="utf-8")
relevo = read(BASE / "RELEVO_ACTIVO.json")
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint="214: AEC Windows declarado; RAW comprobado en PortAudio y comparación física211. Mejora eco212, pero nuevos vacíos ASR humanos213 aislados en nativo214. Sin promoción.",
    continuation="Investigar cuatro ventanas214 congeladas dentro de Parakeet; conservar RAW candidato y fuente207. Ningún proceso activo; alcance completo pendiente.")
save(BASE / "RELEVO_ACTIVO.json", relevo)
assert all(sha(ROOT / row["path"]) == row["sha256"] for row in pins["public"])
assert all(sha(Path(row["path"])) == row["sha256"] for row in pins["private"])
print(json.dumps({"public": len(pins["public"]), "private": len(pins["private"]),
                  "source207Verified": True, "registrationUnchanged": True}))
