"""Publish owner-validated clause conservation before actual product577."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-compound-mute576'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('turns-stt', 'fast'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-compound576-{part}.log').read_bytes())
assert '1632 passed, 1 skipped' in (out / 'turns-stt.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
note = '''# Handoff C03 — fuente576 validada

Goal activo, ninguna decisión pendiente del dueño. Encuesta12 cubiertos/730 abiertos/0NA; original742/rev1248 intacto. BAXY manual cerrado. Fuente574 publicadaad6d9a1a69efc3b71b654e2ca9a0bb7185085305, main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto.

576 repara primera transformación de hora+silencio en572: faltaba separar la pregunta copular/subordinada; si español disparaba condición diferida. Ahora se conserva cada cláusula y su coma; la pregunta indirecta completa de estado actual conserva el verbo de observación omitido. Sólo su si/if deja de ser condición; las demás condiciones y la temporalidad permanecen visibles. El contenido citado de nota no se interpreta como condición para ejecutar; se conserva lo situado fuera de sus comillas. Sin operación nueva, prosa fija ni cambio de modelo. La prueba de subconjunto no permite ejecutar sólo audio cuando falta hora en el catálogo.

Baseline original26casos:11fallos/15pass,0,75s. Tres controles adicionales de cita/temporalidad después. Focal29pass,0,64s. Dueñas2651pass+121subtests/0skip,52,54s. Conversación+STT1632pass/1skip ambiental,8,45s (archivos de campaña ciega ausentes; no aceptación de voz). Fast verde, Release11,36s,0advertencias/errores. Primer comando de dueñas tenía nombre de archivo incorrecto y no ejecutó tests; retenido y corregido antes del resultado. Árbol Python actual9b75b8a888b69ddffdd90bd07d3acd3ea5fed2add9ef513fde1a57453ecfbeb7/403. Sellos históricos intactos. SóloPython en576; Full final pendiente.

Fuente574: lectura real física independiente;31proveedor+80integración pass/0skip, Fast verde. Producto575 diez finales y conteos correctos8/16 en seis variantes; la quinta todavía dice Tengo sobre el procesador de la persona. H0007 sigue abierto, adjudicación y registro actualizados. Cuatro controles de uso/red/audio correctos; no usar la variante impersonal de uso para acreditar el literal que decía Estoy usando. Recursos575GPU3497,559MiB/RAM1587,402MiB;103,282s incluye publicación AOT previa, no latencia de turnos. Sin UI/voz.

Publicar576 y ejecutar577: seis variantes de hora+silencio, pregunta indirecta y controles audio/red, todo sólo lectura real. No ensayar condiciones de apagado sobre el PC; sólo fixtures de dueñas. Después investigar el error de perspectiva CPU aprovechando la guarda y reintento existentes, sin repetir las hipótesis de renombrado/instrucciones558/559. Continúan GPU/unidades, capacidad/recibos de memoria, progreso, curiosidades, resto de encuesta/ocho rutas, UI real, loopback completo/AEC como supresión, recursos conjuntos, aceptación y Full final. Full526 rojo reparado por dueñas528–531, nunca atribuirle verde; C08 humano sólo evidencia y reanudación.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'focal_passed': 29, 'owners': {'passed': 2651, 'subtests': 121, 'skipped': 0, 'seconds': 52.54}, 'turns_and_stt': {'passed': 1632, 'environmental_skips': 1, 'seconds': 8.45}, 'fast': 'passed', 'release_seconds': 11.36, 'product': 'pending577', 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-compound-mute576/** -text\n')
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(checkpoint='576: compound clock/mute conservation adopted;2651pass+121subtests,1632pass/1STTskip,Fast green. Survey12/730/0.', continuation='Publish576; run read-only product577. CPU ownership guard investigation after575; remaining C03 requirements open.', confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('576 source validated and checkpointed; product577 pending.')
