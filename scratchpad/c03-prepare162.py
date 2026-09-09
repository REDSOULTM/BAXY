from pathlib import Path
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
driver = (root / 'scratchpad/c03-sidecar161.py').read_text(encoding='utf-8').replace('161', '162')
driver = driver.replace('Only timed faulthandler entry and protocol observation;', 'Single experimental difference from161: preload scipy.signal on main before runpy/control-plane reader; timed faulthandler and protocol observation;')
(root / 'scratchpad/c03-sidecar162.py').write_text(driver, encoding='utf-8')
entry = (root / 'scratchpad/c03-sidecar161-entry.py').read_text(encoding='utf-8').replace('161', '162')
entry = entry.replace('import runpy', 'import runpy\nimport json\nimport time')
entry = entry.replace("        runpy.run_module", "        started = time.monotonic()\n        import scipy.signal\n        (private/'preload.json').write_text(json.dumps({'seconds': time.monotonic()-started}), encoding='utf-8')\n        runpy.run_module")
(root / 'scratchpad/c03-sidecar162-entry.py').write_text(entry, encoding='utf-8')
note = '''
161 terminado: voice.start agota 60 s; driver exit1 tras ~68 s. Stack repetido:
request_dispatch -> VoiceEngine._start (lock de voz retenido) -> LoopbackReference.start
-> scipy.signal -> scipy.linalg.blas -> carga nativa _fblas. TTS espera ese lock
en _on_tts_state. Cleanup del root exit0 NO prueba cierre cooperativo: stderr
registra request_dispatch_thread y voice_engine_shutdown timed_out; descendientes
propios recogidos. Sin procesos de esta prueba pendientes.
162 prepara una única diferencia experimental: importar scipy.signal en el hilo
principal antes de runpy/lector JSONL. Fuente147 sigue intacta. OpenBLAS documenta
un bloqueo de inicialización gfortran/pipes en Windows para Java; es hipótesis
análoga, todavía no demostración de la causa nativa de BAXY.
https://github.com/OpenMathLib/OpenBLAS#considerations-for-using-the-library-from-java
'''
with (base / 'ASTRA-TRAMO-158_161.md').open('a', encoding='utf-8') as stream:
    stream.write(note)
p = base / 'CHECKPOINT.md'
p.write_text('# Actualización: 161 terminado; diagnóstico162 siguiente\n\n' + note + '\n' + p.read_text(encoding='utf-8'), encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
data = json.loads(p.read_text(encoding='utf-8'))
data.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Fuente147 intacta. UI158 falla;161 localiza bloqueo importación nativa scipy.linalg._fblas. Driver161 exit1; limpieza propia terminada.', continuation='Ejecutar scratchpad/c03-sidecar162.py con runtime Python; preimport SciPy antes lector JSONL como única diferencia experimental. No Full/UI/umbrales hasta resolver el bloqueo.')
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
