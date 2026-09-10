"""Preserve strict and interpretation-sensitive adjudication of50 fixtures."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'BATTERY_VALUES776'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-battery-values776-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADJUDICATION.json').exists()
result = read(OUT / 'RESULT.json')
assert result['cases_completed'] == result['cases_registered'] == 50
assert result['fatal'] is None and not result['violations']
assert all(result[k] for k in ['source_pins_unchanged', 'sources_unchanged', 'manifest_unchanged', 'driver_unchanged'])
cases = read(PRIVATE / 'cases.json')
replies = [json.loads(line) for line in (PRIVATE / 'replies.jsonl').open(encoding='utf-8')]
posts = [json.loads(line) for line in (PRIVATE / 'posts.jsonl').open(encoding='utf-8')]
assert len(cases) == len(replies) == len(posts) == 50
failed = {'battery776-12', 'battery776-18', 'battery776-22', 'battery776-24'}
verdicts = []
md = ['# Batería776: casos sintéticos con respuestas reales del modelo local',
      'Estos datos son fixtures declarados, no mediciones de hardware ni mensajes humanos de reserva. '
      'Compositor e instrucciones de BAXY activos; no comparación de modelos nativos. '
      '46 respuestas cumplen íntegramente; cuatro quedan sin acreditar por causalidad añadida.']
for case, reply, post in zip(cases, replies, posts):
    assert case['id'] == reply['id'] == post['id']
    assert reply['error'] is None
    raw = post['response']['choices'][0]['message']['content']
    assert raw == reply['answer']
    correct = case['id'] not in failed
    reason = ('Porcentaje, carga, alimentación, presencia o incertidumbre fieles al fixture y a la pregunta.' if correct else
              'Los valores y ambos estados booleanos son correctos, pero porque añade una relación causal no explícita en el fixture. '
              'Se conserva sin acreditar bajo el criterio from supplied fixture only; no se clasifica como porcentaje o estado de carga equivocado.')
    if case['id'] == 'battery776-01':
        reason += ' No tiene batería es coloquialmente ambiguo, pero la continuación está completamente descargada fija el sentido de0% y no ausencia física.'
    if case['id'] == 'battery776-24':
        reason += ' Estás cargando no se cuenta como fallo de actor adicional: la elipsis del dispositivo es plausible y el trato en segunda persona ya está aceptado.'
    if case['id'] == 'battery776-50':
        reason += ' I do not know expresa desconocimiento del asistente, no posesión de hardware, y es válido.'
    verdicts.append({'case_id': case['id'], 'group': case['group'], 'correct': correct,
                     'category': 'verified_fixture_answer' if correct else 'unsupported_causal_relation',
                     'reason': reason, 'first_raw_equals_final': True})
    md += ['## ' + case['id'], '**Entrada:** ' + case['request'],
           '**Datos sintéticos:**\n```json\n' + json.dumps(case['situation']['observed']['battery'], ensure_ascii=False, indent=2) + '\n```',
           '**Respuesta:** ' + reply['answer'], '**Criterio:** ' + case['criterion'],
           '**Adjudicación:** ' + ('PASS. ' if correct else 'FAIL. ') + reason]
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'cases': 50, 'correct': 46, 'not_accredited': 4, 'interpretation_sensitive': 4,
    'all_reported_percentages_and_charge_states_match': True,
    'method': 'Read-only agents reviewed1-25/26-50; root inspected all flagged full replies and facts. '
              'Conservative causal-relation failure retained; root rejected an extra second-person actor failure for24.',
    'causal_limit': 'Each disputed fixture explicitly says charging=true and AC=true. This is not evidence that the model derived a wrong charging value from AC. '
                    'The unverified part is the because relation; no acceptance-threshold relaxation.',
    'raw_posts': 50, 'repairs': 0, 'first_raw_equals_final_in_all_cases': True,
    'actor_repair_quality_demonstrated': False, 'coverage_added': 0,
    'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'verdicts': verdicts, 'private_pins': {n: sha(PRIVATE / n) for n in ['cases.json', 'replies.jsonl', 'posts.jsonl', 'compose-audit.jsonl']}})
(OUT / 'CASOS_SINTETICOS.md').write_bytes(('\n\n'.join(md) + '\n').encode('utf-8'))
(OUT / 'REPORT.md').write_bytes('''# Generalización de batería: valores fieles, cuatro causas añadidas

Las50situaciones sintéticas se ejecutaron con el compositor real, la configuración local registrada y un presupuesto de4s por consulta. El comando del servidor coincide con774 salvo puerto. Todos los primeros borradores se publicaron sin reintento: no hubo errores, respuestas vacías ni cambios de fuente. Esta corrida no mide el modelo aislado, el provider, la interfaz ni la voz.

46respuestas cumplen íntegramente. Las cuatro restantes12/18/22/24 conservan porcentajes y estados verdaderos de carga y alimentación, pero añaden «porque» para ligarlos causalmente. Se mantienen sin acreditar bajo el criterio fijado de responder desde los datos suministrados. No son valores de carga erróneos ni prueba de que el modelo ignore isCharging: el fixture lo declara true. La relación añadida, que el fixture no observa, es la parte discutida. La segunda persona de24 no constituye por sí sola un fallo de actor adicional.

La matriz incluye0/1/9/17/31/49/67/82/99/100%, carga activa/inactiva, alimentación conectada/desconectada, batería ausente y porcentaje desconocido. Los casos43–48 no convierten ausencia en0%;49–50 preservan el desconocimiento. En01, «no tiene batería» queda desambiguado por «está completamente descargada» como0% de carga. Las respuestas y datos sintéticos completos están en CASOS_SINTETICOS.md.

Duración18,735s incluyendo arranque; llamada más lenta0,609s. Pico3495,56MiB VRAM y758,21MiB RAM residente del árbol directo, sin violaciones. No equivale al consumo del producto con UI y voz. Las50llamadas usaron temperature0/max_tokens256/cache_prompt=false/enable_thinking=false; ningún reintento, por lo que775 aún necesita demostrar corrección real del sujeto en la repetición777 del producto. No se concede cobertura:26cubiertos/716abiertos/0NA; C03 activo.
'''.encode('utf-8'))
note = ('776 terminado0/30493 recogida:50fixtures,46pass/4causalidad añadida interpretativamente sensible(12/18/22/24); '
        'todosporcentajes/estados coinciden.50raw=final,0repairs; no acredita reparación actor.3495,56MiB/758,21MiB/18,735s. '
        '777 producto activo20301,17casos idénticos774,candidato775. No editar fuente ni reiniciar.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='product_battery777_running_after_values776',
    activeValidation={'name': 'battery_product777', 'sessionId': 20301,
        'process': read(BASE / 'STATUS_BATCH777/PROCESS.json'), 'mutationsForbiddenDuringRun': True},
    continuation='Collect20301/all guards and adjudicate17 actual replies plus draft/retry of H0665.775 still candidate. '
                 '776 is46/50 with4 causal-relation additions, not wrong charging values; all50raw=final so no real actor repair evidence there.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'correct': 46, 'not_accredited': 4, 'repairs': 0, 'active777': 20301}))
