"""Keep H0007 open for the remaining actor error after verified topology575."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = local / 'C03-cpu-product575-private'
out = base / 'astra-cpu-product575'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rows(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines()]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


panel = read(private / 'panel.json')
finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
posts = rows(private / 'http-posts.jsonl')
assert len(panel) == len(finals) == 10 and read(out / 'EXIT.json')['exitCode'] == 0
notes = [
    'Conteo físico8/lógico16 y modelo correctos; literal histórico.',
    'Modelo y8 físicos correctos en inglés; el producto hace dos lecturas CPU para la coordinación, visibles en native2.',
    'Ambos conteos correctos con pedido que explicita las dos magnitudes.',
    'Conteos y modelo correctos; formato de lista breve para los tres datos solicitados.',
    'Conteo8/modelo correctos pero sujeto incorrecto: Tengo atribuye el procesador a BAXY cuando la persona pregunta por su PC. H0007 sigue abierto.',
    'Conteo8 físicos correcto con pregunta inglesa más breve.',
    'Uso18,75% con sujeto impersonal correcto para esta variante. No acredita el literal antiguo que decía Estoy usando.',
    'Uso18,75% correcto en inglés.',
    'Red online correcta.',
    'Volumen100 y no silenciado correctos.',
]
adjudication = [{**case, 'ordinal': i + 1, 'terminal': finals[i], 'adjudication': notes[i]} for i, case in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto575 — topología real CPU', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
lines += ['## Capturas nativas completas', '', '```json', json.dumps(posts, ensure_ascii=False, indent=2), '```']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
backup = private / 'requirements-before-adjudication.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = rows(backup)
case = next(r for r in requirements if r['case_id'] == 'H0007')
assert case['verification_status'] == 'open'
case['verification_reason'] = '575 verifica conteos físicos/lógicos y modelo en seis variantes reales ES/EN, pero la quinta responde Tengo ante Qué procesador tengo. El sujeto no generaliza todavía.573 aporta dos controles sintéticos6/8, sin sustituir producto. La conducta sigue abierta por ese error de perspectiva, no por falta de topología.'
case['verification_updated_at'] = datetime.now(timezone.utc).isoformat()
case['verification_evidence'].append({'campaign': 'astra-cpu-product575', 'source_commit': 'ad6d9a1a69efc3b71b654e2ca9a0bb7185085305', 'private_adjudication': str(private / 'adjudication.json'), 'ordinals': list(range(1, 7)), 'ui_or_voice_credit': False})
registry.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in requirements), encoding='utf-8', newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), updated_at=datetime.now(timezone.utc).isoformat())
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
note = '''# Producto575 — topología llega completa; perspectiva aún abierta

Fuente574 publicada ad6d9a1a69efc3b71b654e2ca9a0bb7185085305. Diez finales, sin cortes: seis peticiones CPU reciben8 núcleos físicos/16 procesadores lógicos y modelo AMD verificado; cinco conservan además el sujeto correcto, la quinta dice Tengo ante una pregunta por el PC de la persona. H0007 sigue abierto. Las dos peticiones coordinadas hacen dos lecturas CPU: no atribuir esa redundancia a la API nueva ni afirmar consumo mínimo definitivo.

Cuatro controles de uso CPU ES/EN, red y audio correctos. El uso español impersonal correcto de esta variante no arregla por sí solo el literal anterior que decía Estoy usando. Recursos medidos: GPU3497,559MiB/RAM1587,402MiB,103,282s incluyendo compilación/publicación nativa de Core antes de arrancar el conductor. No es latencia de diez turnos ni consumo conjunto UI/voz. Sin modificación de runtime. Encuesta12 cubiertos/730 abiertos/0NA,742/rev1248 intacto.

576 en validación: primera transformación de hora+silencio localizada en división de cláusulas y clasificación de si/if como condición diferida, incluso en preguntas indirectas.29 pruebas focales verdes tras añadir controles de temporalidad/cita; dueñas amplias pendientes. No nuevo cambio de modelo ni barrido de instrucciones.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'finals': 10, 'correct': [1, 2, 3, 4, 6, 7, 8, 9, 10], 'open': [5], 'newly_covered': [], 'physical_observation_verified_in_product': True, 'source_commit': 'ad6d9a1a69efc3b71b654e2ca9a0bb7185085305', 'resources': read(out / 'resources.json'), 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json'), 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-cpu-product575/** -text\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='575: verified physical count in product; H0007 remains open for actor, survey12/730/0.576 focal29pass, broad validation running.', publishedSourceCommit='ad6d9a1a69efc3b71b654e2ca9a0bb7185085305', continuation='Finish compound576 owners and source gates, validate actual product. CPU perspective remains independent; final C03 obligations still open.')
write(base / 'RELEVO_ACTIVO.json', state)
matrix = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
content = matrix.read_text(encoding='utf-8')
old = 'Fuente adoptada HEAD=origin/Goal-c03=8027c2220997ee9407f04aac94b383e0647225c4 al publicar555; sin fuente propia pendiente después. Main intacto5f572ee. Incluye control892c506 y correcciones528–555. Dueñas555:1936 pass+121 subtests,0 skips; Fast verde, Release21,57s sin advertencias/errores; Full final y aceptación C03 siguen pendientes.'
new = 'Última publicación de fuente comprobada: HEAD=origin/Goal-c03=ad6d9a1a69efc3b71b654e2ca9a0bb7185085305 al publicar574, sin fuente propia pendiente en ese punto. Main intacto5f572ee. Dueñas574:31 proveedor+80 integración pass,0 skips; Fast verde, Release6,15s sin advertencias/errores. Producto575 comprueba topología; sujeto de una variante sigue abierto. Fuente576 posterior en desarrollo; Full final y aceptación C03 siguen pendientes.'
assert content.count(old) == 2
matrix.write_text(content.replace(old, new), encoding='utf-8', newline='\n')
print('575 adjudicated; H0007 remains open, survey12/730/0; publication evidence574 updated.')
