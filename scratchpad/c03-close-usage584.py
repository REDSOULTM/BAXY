"""Seal source584 only after owned tests and Fast, leaving actual product open."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-usage-actor584'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for stage in ('fast', 'stt'):
    (out / (stage + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-cpu584-{stage}.log').read_bytes())
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
assert '67 passed, 1 skipped' in (out / 'stt.log').read_text(encoding='utf-8-sig')
note = '''# Fuente584 validada — posesión del uso CPU

Se amplía la guarda existente para Tengo + uso/consumo + referencia CPU en la misma frase. Repara el defecto real582 ordinal11; conserva las frases que atribuyen a BAXY una lectura realizada, sin atribuirle el consumo total. No nueva llamada, modelo, prompt ni plantilla. El reintento recibe su borrador real. La gramática incorrecta de582 ordinal7 sigue abierta y no se confunde con esta corrección.

Baseline54:6fallos/48pass,2,25s. Dueñas finales2165pass+121subtests/0skips,28,28s. FocalCPU55+STT12=67pass/1skip ambiental,2,14s; faltan archivos de campaña ciega, no es voz aprobada. Ruff verde. Fast verde completo, Release19,81s/0advertencias/0errores. Árbol Python6ca99187a3a2f97e5ba3736c5b61e2bae9710f97ed44441f8a4819f7bbeadb7d/403; históricos intactos. SóloPython, Full final pendiente. Dueñas se solaparon con inferencia583; no comparar sus tiempos como benchmark limpio.

582 publicado d87997d5, fuente581 en1dc8b33d. Encuesta13 cubiertos/729 abiertos/0NA, original742/rev1248 intacto. BAXY manual cerrado; no decisión del dueño pendiente; goal activo, main5f572ee intacto. Publicar584 y verificar producto587 antes de sumar cobertura.

583: siete respuestas9B con límite256; seisEOS/una length. Fallan dos EOS (apelativo inventado y sujeto del nombre) y una salida que mezcla deliberación/idioma/count físico falso. Detenido su servidor; nueve errores de transporte inducidos, no semánticos. No adopción.585: roles tool conservan exactamente cuatro errores de sujeto de ocho casos;16EOS, sin mejora, no adopción.

586 nativo completado: adaptador heredado piloto4 sóloCPU corrige el sujeto en12entradas, con redondeo entero en algunas; los tres controles fueraCPU mantienen la base. GPU3693,563MiB/RAM1030,723MiB,20,296s, sin UI/voz. Requiere adjudicación, segunda semilla/misiones y recursos conjuntos antes de implementar o promover. No nuevo entrenamiento ni modificación del runtime registrado. Pendientes resto de encuesta/ocho rutas, UI real, loopback íntegro/AEC por separado, aceptación, Full final y publicación final. C08 humano sólo evidencia/reanudación.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'baseline': {'failed': 6, 'passed': 48}, 'owners': {'passed': 2165, 'subtests': 121, 'skips': 0}, 'focal_stt': {'passed': 67, 'environmental_skips': 1}, 'fast': 'passed', 'release_seconds': 19.81, 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'test_sha256': sha(root / 'tests/test_c03_cpu_actor.py'), 'actual_product': 'pending587', 'survey': {'covered': 13, 'open': 729, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-usage-actor584/** -text\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='584 validated2165pass+121subtests,67pass/1STT environmental skip,Fast green. Survey13/729/0.583/585 not adopted;586 promising CPU-only adapter, unpromoted.', continuation='Publish584 and actual product587. Adjudicate586; qualify another seed/missions before any adapter implementation/promotion. All remaining C03 criteria stay open.')
write(base / 'RELEVO_ACTIVO.json', state)
print('584 source validated; product587 and adapter qualification remain pending.')
