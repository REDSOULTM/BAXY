"""Close validated reader503 and prepare the unchanged full protocol panel."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-unmute-request503'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-unmute-request503-private'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert '3404 passed, 121 subtests passed in 52.86s' in (out / 'owners-final.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
source = root / 'src/baxy_mind/effect_intent.py'
(out / 'SOURCE.patch').write_text(''.join(difflib.unified_diff(
    (private / 'effect_intent-before.py').read_text(encoding='utf-8-sig').splitlines(True),
    source.read_text(encoding='utf-8-sig').splitlines(True),
    fromfile='source501/effect_intent.py', tofile='source503/effect_intent.py')), encoding='utf-8')
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'baseline': {'failed': 13, 'passed': 12, 'seconds': 2.04},
    'focal_final': {'passed': 52, 'seconds': 1.51},
    'regressions_preserved': 'First broad run6failed/3398pass/121subtests. Global desire stripping changed six notes/music/incomplete-request routes. Moving normalization only into effect readers and preserving legacy non-action heads restores them; six-failure rerun passes. Intermediate logs remain.',
    'owners': {'passed': 3404, 'subtests_passed': 121, 'skips': 0, 'seconds': 52.86, 'session': 7688, 'exit': 0},
    'fast': {'passed': True, 'release_seconds': 3.25, 'warnings': 0, 'errors': 0, 'session': 60961, 'exit': 0},
    'source_sha256': sha(source),
    'change': 'Shared unmute family includes desilenciar/dessilenciar and subjunctive forms. Acknowledgement can precede a proved explicit need/desire request. Its body is normalized only within strict/single effect readers; conversation and clarification retain the original frame. Bare unmute accepts courteous pls/plz/porfa. The shared request-prefix regex is compiled once. Final edit after owners only moved comments before Fast.',
    'limits': 'Source/owner validation; exact full mind/arguments504 still required. No model/runtime or visible-response template changes.'
})
(out / 'RESULT.md').write_text('''# Petición de desilenciar tras un asentimiento

El caso literal «perfecto, necesito lo dessilencies pls» se reconoce sin perder la petición y liga state=false. La solución comparte la familia verbal con el binder y conserva negativas, condicionales, citas y audio de otros dispositivos. Los controles también cubren peticiones de abrir aplicaciones y ajustar volumen en español e inglés.

La primera normalización global causó seis regresiones. Se conserva ese fallo; el marco de deseo ahora se transforma únicamente dentro de los lectores de efectos y los demás lectores reciben el original. También se mantiene la lectura heredada de cabezas no cubiertas por el delimitador, como write al crear una nota. No se añade una respuesta fija ni se modifica un prompt.

Baseline13fallos/12pass; controles finales52pass. Siete suites:3404pass y121subtests,0skips,52,86s. Fast verde; Release3,25s,0warnings/errors. Después de las suites sólo se recolocaron comentarios antes de Fast. Falta el protocolo real504, sin efectos, para verificar la integración.
''', encoding='utf-8')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
script = (root / 'scratchpad/c03-audio-mind502.py').read_text(encoding='utf-8-sig').replace('502', '504')
script = script.replace('source501 contextual level/argument repair plus500 shared setting head',
                        'source503 explicit need/acknowledgement and unmute family repair; exact14cases/binding protocol comparison against502/source501')
target = root / 'scratchpad/c03-audio-mind504.py'
assert not target.exists()
target.write_text(script, encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    text = text.replace('Pruebas dueñas503 activas en sesión26227; no runtime de producto ni build activo. No editar fuente hasta recogerla.',
                        'No runtime, prueba ni build activo. 503 cerrado: sesiones7688 y60961 recogidas exit0.')
    text += '\nÚLTIMO:503 validado. 3404pass y121subtests,0skips,52,86s; Fast verde,Release3,25s sin warnings/errors. Se corrigieron seis regresiones manteniendo el marco original para conversación/aclaración y normalizando sólo los lectores de efectos. RESULT/PINS completos. Fuente effect_intent503,__main__501,llm466. Siguiente ejecutar scratchpad/c03-audio-mind504.py, mismos14casos/protocolo502; ningún efecto. Después del audio, investigar la definición: en502 HTTP20 la prosa visible proviene literalmente del tool selector y __main__ la pasa a chat como initial_reply; no atribuirlo al compositor sin aislar esa reutilización. Fuentes llm7212,__main__6106/6492; biblioteca título1_toolcalling localizado. No cambio de prompt/modelo aún.\n'
    path.write_text(text, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente503 validada:3404pass,121subtests,0skips yFast verde. Sin procesos de producto.',
              continuation='Ejecutar504 mismo panel502 con bindings reales; después aislar prosa del selector reutilizada por chat. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('503 closed and pinned;504 ready. No source/runtime mutation required to run it.')
