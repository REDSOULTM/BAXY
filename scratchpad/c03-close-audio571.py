"""Checkpoint the validated audio projection fix before publication and product572."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio-observation571'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

for suffix in ('owners', 'fast'):
    (out / (suffix + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-audio571-{suffix}.log').read_bytes())
assert '1966 passed, 1 skipped, 121 subtests passed' in (out / 'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
note = '''# Handoff C03 — 571

Goal activo, ninguna decisión pendiente del dueño. RamaGoal-c03, main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Fuente569 publicadaa9f053b7; producto570 verifica red local. Encuesta12 cubiertos/730 abiertos/0NA; nuevoH0080 después de H0063/H0073/H0057 en568. Original742/rev1248 intacto. BAXY manual cerrado.

Fuente571 reusa merged_audio para decidir si falta muted; la proyección y la guarda ya usaban esos mismos datos. Se retira la consulta redundante a observed superior. Native568:13/570:11 contenía muted:false y a la vez instrucción que lo declaraba ausente. Test-first12fallos/6pass,0,90s; focal18pass,0,50s. Dueñas+declaracionesSTT:1966pass+121subtests,1skip ambiental por entradas de campaña ciega ausentes,9,86s. Fast verde, Release19,77s,0advertencias/errores. Sin cambio de validadores, hechos inventados, modelo ni plantillas visibles. SóloPython, Full final pendiente.

Árbol STT actual564e880c9d37bf3c26965006e34c98288a8793d7c37313c59e34271cd595d0b6/403archivos; sellos históricos intactos. Publicar571 y verificar producto572 sobre las dos formas de audio ES/EN y resultado combinado. Source quality terminado; no procesos de ensayo pendientes. Los build servers propios se apagaron.

Producto570:8finales/sin cortes, GPU3497,559MiB/RAM1840,793MiB,24,188s. Siete variantes de red conservan online:true; la compuesta conserva02:37 y red en pasos ordenados. Sinweb.search sustituta. Sin UI/voz ni desconexión física. Audio sigue como control, no nuevo caso adjudicado automáticamente.

Antecedentes:565 destinatario de progreso y566 configuración acotada no generalizan; no adoptados.567 Qwen9Bthinking agota180s en primer caso sin final, corte deliberado en segundo, cero finales semánticos; GPU3426,148MiB/RAM3037,359MiB. Errores posteriores de conexión son del corte.558/559 CPU y552/553 unidades fueron comparaciones fallidas; no repetir renombrados/instrucciones equivalentes.561LoRA mejora CPU pero cambia sujeto del nombre y niega capacidad: no promoción ni entrenamiento nuevo. Selector de memoria no equivale a Label ni debe exponerse por inferencia.

Pendiente: CPU total atribuida a BAXY, procesadores lógicos llamados núcleos, GPU/unidades, capacidad de memoria versus configuración, recibos y progreso natural, curiosidades, resto de encuesta/ocho rutas. H0037 permanece abierto: isCharging:false no demuestra ausencia de descarga. Después UI real, loopback completo/AEC como supresión, recursos conjuntos, Full final y aceptación. Full526 rojo con25fallos reparados en dueñas528–531; no volver a presentar aquel Full como verde. C08humano sólo evidencia y reanudación, sin cerrar filas ajenas.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'baseline': {'failed': 12, 'passed': 6, 'seconds': .90}, 'focal': {'passed': 18, 'seconds': .50}, 'owners_and_stt': {'passed': 1966, 'subtests': 121, 'environmental_skips': 1, 'seconds': 9.86}, 'fast': 'passed', 'release_seconds': 19.77, 'product': 'pending572', 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-audio-observation571/** -text\n')
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(checkpoint='571: nested audio observations retained;1966pass+121subtests/1environmental skip,Fast green. Survey12/730/0; product572 pending.', continuation='Publish571, verify product572. Investigate missing verified CPU physical topology instead of repeating ownership/units prompt sweeps; remaining C03 obligations open.', confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('Source571 validated, product572 pending; survey12/730/0.')
