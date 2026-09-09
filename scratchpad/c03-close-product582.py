"""Adjudicate CPU582 once, preserving the two actual failures."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = local / 'C03-cpu-actor-product582-private'
out = base / 'astra-cpu-actor-product582'
commit = '1dc8b33dcd60cc1dcc99586d51ac108f7e127ba5'


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
assert len(panel) == len(finals) == 17
assert read(out / 'EXIT.json')['exitCode'] == 0
assert not read(out / 'resources.json')['violations']
notes = [
    'Modelo AMD y ocho núcleos físicos/dieciséis lógicos coinciden con la observación real.',
    'Modelo y ocho físicos correctos en inglés.',
    'Ambos conteos físicos/lógicos correctos, sin confundirlos.',
    'Tres atributos correctos y etiquetas inglesas inequívocas.',
    'Ahora conserva modelo y ocho físicos sin propiedad del asistente. Native8 repara el borrador Tengo usando Este ordenador.',
    'Ocho físicos correctos en pregunta inglesa breve.',
    'FALLO: Esto computadora está usando el 22,5% de la CPU. Cifra y sujeto correctos, gramática española incorrecta. Native11 aplica el perfil cualificado, por tanto no es un override perdido.',
    'Native13 corrige I am using por the CPU is using; conserva21,875%.',
    '25,5% correcto y sujeto de segunda persona correcto.',
    '25,5% correcto en inglés.',
    'FALLO: Tengo un uso del 50 por ciento de CPU. Cifra correcta, sujeto del asistente indebido; la guarda no reconoce Tengo un uso.',
    'Native22 corrige primera persona; conserva58,125%, ocho físicos y dieciséis lógicos.',
    '45% correcto en inglés.',
    'Nombre sintético Luisa recuperado correctamente en la conversación.',
    'Identidad BAXY conservada.',
    'Hora03:49 y audio no silenciado/volumen100 correctos.',
    'Conectividad online correcta en inglés.',
]
adjudication = [{**c, 'ordinal': i + 1, 'terminal': finals[i], 'passed': i not in (6, 10), 'adjudication': notes[i]} for i, c in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto582 — CPU y controles', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]} · {row["case_id"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
lines += ['## Payloads y respuestas nativas', '', '```json', json.dumps(rows(private / 'http-posts.jsonl'), ensure_ascii=False, indent=2), '```']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
backup = private / 'requirements-before-adjudication.jsonl'
assert not backup.exists(), 'One-shot registry mutation already executed'
backup.write_bytes(registry.read_bytes())
requirements = rows(backup)
assert Counter(r['verification_status'] for r in requirements) == {'covered': 12, 'open': 730}
now = datetime.now(timezone.utc).isoformat()
for case_id, ordinals, reason in [
    ('H0007', list(range(1, 7)), 'Seis variantes reales582 conservan modelo, conteos físicos/lógicos y sujeto correcto en ES/EN, con reordenación y posesivo.573/580 añaden fixtures explícitamente sintéticos que cambian nombres y valores, sin inferir la topología por dividir lógicos. No UI/voz ni aceptación ciega.'),
    ('H0065', list(range(7, 11)), notes[6]),
    ('H0350', list(range(11, 14)), notes[10]),
]:
    row = next(r for r in requirements if r['case_id'] == case_id)
    assert row['verification_status'] == 'open'
    row.update(verification_reason=reason, verification_updated_at=now)
    if case_id == 'H0007':
        row.update(verification_status='covered', generalization_status='verified_product_variants')
    row['verification_evidence'].append({'campaign': 'astra-cpu-actor-product582', 'source_commit': commit, 'private_adjudication': str(private / 'adjudication.json'), 'ordinals': ordinals, 'ui_or_voice_credit': False})
counts = {'covered': 13, 'open': 729, 'not_applicable': 0}
assert Counter(r['verification_status'] for r in requirements) == {'covered': 13, 'open': 729}
registry.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in requirements), encoding='utf-8', newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), validated_current=13, verification_counts=counts, updated_at=now)
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
note = '''# Producto582 — topología cubierta; dos fallos de uso CPU conservados

Fuente581 publicada1dc8b33dcd60cc1dcc99586d51ac108f7e127ba5.17 finales sin cortes,15 correctos y dos fallos. Las seis variantes de H0007 dan modelo/conteos/sujeto correctos: nuevo requisito cubierto, apoyado por fixtures573/580 con otros valores y modelos. Encuesta13 cubiertos/729 abiertos/0NA; original742/rev1248 intacto. H0065 sigue abierto: «Esto computadora está usando el 22,5% de la CPU» rompe gramática aun con el perfil cualificado. H0350 sigue abierto: «Tengo un uso del50 por ciento de CPU» pasa una guarda de actor incompleta. Los demás usos y los cuatro controles de nombre/identidad/hora-audio/red son correctos. No presentar una corrección de sujeto como calidad completa.

Reparaciones efectivas native8/11/13/22: mismos hechos, borrador rechazado, feedback y Qwen0,7/0,8/k20/min0/presence0/repeat1/seed0; native11 demuestra que el fallo gramatical no se debe a un perfil omitido. Nombres sintéticos sólo en perfil aislado, sin persistencia permanente. GPU3499,559MiB/RAM2475,281MiB,45,375s. Sin UI/voz ni consumo conjunto final.

Fuente581 dueñas2156pass+121subtests/0skip; focalCPU46+STT12pass/1skip ambiental; Fast verde, Release1,76s. Full final pendiente. Main5f572ee intacto. No decisión del dueño pendiente, BAXY manual cerrado, goal activo.

Siguiente: tras los intentos de instrucciones558/559 y reparación578–582, contrastar estrategia de razonamiento acotado9B con capturas reales sin cambiar sus instrucciones.567 tenía razonamiento ilimitado y no dio finales antes del timeout; no repetirlo ni inferir incapacidad semántica. Medir límite efectivo y calidad/recursos antes de adoptar. Continúan resto de encuesta/ocho rutas, UI real, loopback íntegro/AEC separado, consumo conjunto, aceptación y Full final. C08 humano sólo evidencia/reanudación.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'finals': 17, 'correct_ordinals': [i for i in range(1, 18) if i not in (7, 11)], 'failed_ordinals': [7, 11], 'newly_covered': ['H0007'], 'survey_counts': counts, 'source_commit': commit, 'resources': read(out / 'resources.json'), 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json')})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-cpu-actor-product582/** -text\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=now, checkpoint='582 adjudicated:17 finals,15 correct; H0007 covered. CPU grammar/actor gaps remain. Survey13/729/0.', surveyVerificationCounts=counts, publishedSourceCommit=commit, continuation='Bounded reasoning native583 before any model adoption; all remaining C03 closure criteria stay open.')
write(base / 'RELEVO_ACTIVO.json', state)
matrix = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
content = matrix.read_text(encoding='utf-8')
old = 'Última publicación de fuente comprobada: HEAD=origin/Goal-c03=ad6d9a1a69efc3b71b654e2ca9a0bb7185085305 al publicar574, sin fuente propia pendiente en ese punto. Main intacto5f572ee. Dueñas574:31 proveedor+80 integración pass,0 skips; Fast verde, Release6,15s sin advertencias/errores. Producto575 comprueba topología; sujeto de una variante sigue abierto. Fuente576 posterior en desarrollo; Full final y aceptación C03 siguen pendientes.'
new = 'Última fuente publicada1dc8b33dcd60cc1dcc99586d51ac108f7e127ba5 (581), comprobada582:17 finales,15 correctos; topología H0007 cubierta, dos fallos de uso CPU aún abiertos. Dueñas2156 pass+121 subtests/0 skips; Fast verde, Release1,76s sin advertencias/errores. Encuesta13/729/0. Main intacto5f572ee. Full final y aceptación C03 pendientes.'
assert content.count(old) == 2
matrix.write_text(content.replace(old, new), encoding='utf-8', newline='\n')
print(json.dumps(counts))
