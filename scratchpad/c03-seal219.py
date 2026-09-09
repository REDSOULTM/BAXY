"""Seal installed normalization218–219 with exact validation and open quality limits."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
product = read(BASE / "astra-product219/COMPLETE.json")
assert product["nativeParity217"] == 63 and product["registrationUnchanged"]
install = read(BASE / "astra-install218-retry/COMPLETE.json")
assert install["onlyExpectedDistributionChanged"] and install["registrationUnchanged"]
build_log = (BASE / "astra-runtime218/BUILD.log").read_text(encoding="utf-8", errors="replace")
assert "[  PASSED  ] 8 tests." in build_log
build = json.loads(next(line for line in reversed(build_log.splitlines()) if line.startswith('{"wheel":')))
wheel = Path(build["wheel"])
assert sha(wheel) == build["sha256"]
assert "source_quality_gate_passed: mode=Fast" in (BASE / "astra-runtime218/FAST.log").read_text(encoding="utf-8", errors="replace")
assert "12 passed" in (BASE / "astra-runtime218/LOCK-FINAL.log").read_text(encoding="utf-8", errors="replace")
assert "python_dependency_lock_current: profile=Runtime" in (BASE / "astra-runtime218/LOCK-CHECK.log").read_text(encoding="utf-8", errors="replace")
save(BASE / "astra-runtime218/BUILD_RESULT.json", build)
save(BASE / "astra-runtime218/COMPLETE.json", {"nativeMathPass": 8, "voicePass": 91,
    "correctorPass": 6, "wheelPass": 1, "lockFinalPass": 12, "skips": 0,
    "initialCombined": "109pass/1fail; obsolete version string in mutation test corrected",
    "fastExitCode": 0, "lockCheckExitCode": 0, "releaseSeconds": 2.93,
    "productNativeParity": 63, "semanticAcceptance": False})
sources = ["src/baxy_mind/voice.py", "src/baxy_mind/voice_capture.py", "src/baxy_mind/speex_aec.py",
    "src/baxy_mind/requirements-voice.txt", "scripts/build_sherpa_runtime.py",
    "scripts/verify_python_runtime_lock.py", "scripts/lock_python_dependencies.ps1",
    "constraints-runtime-win-x64.txt", "pylock.runtime-win-x64.toml",
    "tests/test_mind_voice_runtime.py", "tests/test_python_runtime_lock.py", "tests/test_sherpa_runtime_package.py",
    "runtime_wheels/sherpa-nemo-stream-decoder.patch", "runtime_wheels/sherpa-nemo-normalization.patch",
    "runtime_wheels/README.md", "docs/AI_CONTEXT_MAP.md"]
snapshot = BASE / "astra-source218-snapshot"
snapshot.mkdir(exist_ok=False)
hashes = {}
for name in sources:
    destination = snapshot / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / name, destination)
    hashes[name] = sha(ROOT / name)
save(snapshot / "FILES.json", hashes)
report = f'''# C03 — runtime218–219 — normalización integrada, fidelidad aún abierta

La dependencia instalada es sherpa-onnx1.13.4+baxy.2. La única distribución que
cambió fue sherpa-onnx(baxy.1→baxy.2); core sigue1.13.4. Los modelos y el manifiesto
registrado13b971b3… permanecen intactos. No se promocionó Qwen3.5 ni RAW en esta tanda.

## Cambio reproducible

El wheel contiene la selección por stream207 y la corrección matemática3857 de
Eoin Houstoun, merge0967a08db705d8eec9cf5cef962c8ec57c16e4a8. No incluye las sondas
215/216: la receta rechaza cualquier diff distinto de los tres archivos previstos.
Comprueba ambos parches por hash, diff exacto y aplicación inversa; no hace reset.

Wheel: runtime_wheels/{wheel.name}
SHA256: {build['sha256']}
Extensión: {build['extensionSha256']}
Parche de normalización: {build['normalizationPatchSha256']}

scripts/build_sherpa_runtime.py habilita y ejecuta math-test antes de empaquetar.
Conserva wrapper/licencias/core y añade procedencia de3857 al aviso y metadata.
baxy.1 y los parches anteriores se conservan como rollback/evidencia, sin cambiar
sus hashes. CMake y su fuente externa quedan preparados para los dos parches
productivos; los bundles de observación permanecen aislados.

## Validación ejecutada

- Receta build_sherpa_runtime.py, workspace externo sherpa205, VS2022CMake:
  exit0; suite original math-test8pass/0skips, incluidos los dos tests3857.
- pytest tests/test_sherpa_runtime_package.py -q:1pass/0skips,0,31s.
- Combinada de voz/lock/paquete/corrector:109pass/1fail,7,37s. El fallo era el
  reemplazo de un nombre baxy.1 que ya no estaba en el lock. La prueba ahora
  modifica el prefijo del wheel independientemente de versión y exige que la
  mutación ocurra; no se relajó el verificador.
- Reintento dueño --lf -x -q verde; suite completa test_python_runtime_lock.py:
  12pass/0skips,0,66s. Voz91/corrector6/paquete1 habían pasado en la combinada.
- .\\scripts\\lock_python_dependencies.ps1 -Profile Runtime -Check:exit0,
  regeneración idéntica. Se usa el Python registrado explícito.
- .\\scripts\\test_source_quality.ps1:Fast exit0; Release2,93s,0avisos/errores.
- Instalación del lock entero con pip --only-binary=:all: --require-hashes
  --no-deps:exit0; delta de distribuciones exactamente el previsto.

Primer instalador218 falló antes de pip al buscar el nombre de metadata con
guion en lugar de underscore. Se conserva el fallo; el reintento normaliza
nombres para comparar. No hubo cambio de runtime en ese primer intento.

## Producto219

VoiceEngine real y extensión instalada, sin inyección nativa, con salida TTS
inerte. Los63 PCM exactos217 pasan por transcribe_pcm; el helper observado
reproduce63/63 transcripciones nativas217. Correcciones públicas adicionales:
{product['publicCorrections']}. Tres casos recuperados213 producen callbacks directos.
Los literales de esos callbacks se conservan en DIRECT.json.

Carga:{product['engineLoadSeconds']:.3f}s; RSS:{product['rssMiB']:.2f}MiB.
No son medición de presupuesto conjunto ni aceptación física. Wake:
{product['wakeBackend']}/{product['wakeError']}. No se elude la calibración.

**63 paridades no son63 pases de fidelidad.** Se conservan las regresiones217:
eco añadido, pérdida de palabras y30→3años en un control inglés. No se afirma
que integrar la normalización resuelva toda la voz. No se ejecutó Full durante
esta reparación; su verde final sigue siendo obligatorio para cerrar C03.

## Continuación

Retomar RAW/Speex212 con el normalizador válido ya instalado. La evidencia211
demuestra que RAW excluye los efectos Windows en el cliente real. Falta incorporar
esa captura de forma mantenible y verificar interrupción física/voz humana,
conservando los controles que detectaron pérdidas. No repetir filtros con el
normalizador antiguo ni hacer barridos de umbrales/ganancias.

Todos los procesos propios se recogieron:95776build,12778Fast,18567producto219;
resto terminaron directamente. No procesos vivos ni cambios de volumen esta tanda.
Snapshot218 y TRAMO218_219_PINS conservan fuente/logs/paquete/resultados.

C03 completo sigue activo: wake/voz/ocho rutas,100humanos frescos aún sin congelar
y100/100 útiles, averías y recuperación, UI/audio físico final,4GB conjuntos,
runtime/instalación/continuidadC04–C09,Full/publicación fuera main.
'''
(BASE / "PRUEBAS_RUNTIME218_219.md").write_text(report, encoding="utf-8")
public = [BASE / "PRUEBAS_RUNTIME218_219.md", Path(__file__), wheel]
for name in ["astra-runtime218", "astra-install218", "astra-install218-retry", "astra-product219"]:
    public.extend(p for p in (BASE / name).iterdir() if p.is_file())
public.extend(snapshot / name for name in sources)
public.append(snapshot / "FILES.json")
for name in ["c03-prepare-runtime218.py", "c03-install218.py", "c03-install218-retry.py", "c03-product219.py"]:
    public.append(ROOT / "scratchpad" / name)
target = BASE / "TRAMO218_219_PINS.json"
assert not target.exists()
pins = {"public": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in public], "private": []}
save(target, pins)
header = f'''# C03 — checkpoint219 — EN_CURSO —2026-09-07

Fuente218 y sherpa-onnx1.13.4+baxy.2 instalados. WheelSHA{build['sha256']}.
ExtensiónSHA{build['extensionSha256']}. Sólo sherpa cambió; core1.13.4/modelos/
registro13b971b3 intactos. Receta verifica2parches exactos, habilita/ejecuta math-test
8pass; sin instrumentación215. Snapshot218 es fuente actual; no usar207 comoactual.

219VoiceEngine real63/63paridad nativa217; {product['publicCorrections']}correcciones públicas,
3callbacks directos. No63pases: regresiones217 de eco/palabras/30→3 siguen abiertas.
Wake unavailable/wake_verifier_manifest_missing, sin calibración eludida.
Voz91/corrector6/wheel1pasaron; lock12finalpass/0skips tras corregir fixture que
buscaba versiónvieja. Fastexit0/Release2,93s0avisos/errores; lock-Checkidéntico.
Primer instalador falló nombreunderscore antes de pip; reintento cambia sólo baxy.1→2.

Siguiente: retomar captura RAW/Speex212 con ASR matemáticamente válido; incorporar
captura mantenible y verificar voz/interrupción física conservando controles217.
No promover por ceroeventosdeeco ni barrer umbrales/gains. Leer PRUEBAS_RUNTIME218_219.
Procesos95776/12778/18567recogidos exit0, ninguno activo. NoFull ni hardware nuevos.
TRAMO218_219_PINS/snapshot218 sellados. Baxy.1 retenido rollback; bundles215/216NOproducto.

Goal íntegro activo: wake/voz/ocho rutas/100frescos aún sin congelar y100/100/
averías/recuperación/UI/audiofísico/4GB/runtime/instalación/C04–C09/Full/publicación.
No bloqueo externo. Tres ingleses admitidos; Grabación(2) opcional sinrespuesta.

## Estado anterior conservado —217

'''
for name in ["CHECKPOINT.md", "HANDOFF.md"]:
    path = BASE / name
    prefix = header if name == "CHECKPOINT.md" else header.replace("checkpoint219", "handoff219")
    path.write_text(prefix + path.read_text(encoding="utf-8"), encoding="utf-8")
relevo = read(BASE / "RELEVO_ACTIVO.json")
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint="219: fuente218/baxy.2 instalados,63paridades nativas217,math8/owners/Fast/lockCheck verdes. Fallos de calidad217 siguen abiertos.",
    continuation="Retomar RAW/Speex212 con normalización corregida. Fuente actual snapshot218. Sin procesos; alcance completo pendiente.")
save(BASE / "RELEVO_ACTIVO.json", relevo)
assert all(sha(ROOT / r["path"]) == r["sha256"] for r in pins["public"])
print(json.dumps({"public": len(public), "private": 0, "installedVersion": "1.13.4+baxy.2"}))
