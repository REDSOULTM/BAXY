"""Adjudicate the complete native comparison before changing the writer."""
from pathlib import Path
from statistics import mean

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-native-window-scope650'
private = home/'C03-native-window-scope650-private'
assert not (out/'RESULT.json').exists()
panel = {(r['case_id'], r['arm']): r for r in read(private/'panel.json')}
responses = rows(private/'responses.jsonl')
assert len(panel) == len(responses) == 16
assert read(out/'RESOURCES.json')['complete']
assert not read(out/'RESOURCES.json')['violations']
adjudication = []
for response in responses:
    key = response['case_id'], response['arm']
    case = panel[key]
    choice = response['response']['choices'][0]
    assert choice['finish_reason'] == 'stop'
    failed = key == ('observed647', 'current')
    adjudication.append({**case, 'draft': choice['message']['content'],
        'finish_reason': choice['finish_reason'], 'seconds': response['seconds'],
        'verdict': 'failed' if failed else 'correct',
        'reason': ('Adds unobserved process liveness; reproduces the exact published647 first draft.' if failed
                   else 'Preserves installation/visible-window facts, requested count and language without asserting process liveness.')})
original = next(r for r in rows(home/'C03-context-product647-private/compose-audit.jsonl')
                if r['trace'] == 't15' and r['stage'] == 'first')
assert adjudication[0]['draft'] == original['draft']
scores = {arm: sum(r['verdict'] == 'correct' for r in adjudication if r['arm'] == arm)
          for arm in ['current', 'observation_scope']}
assert scores == {'current': 7, 'observation_scope': 8}
write(private/'adjudication.json', adjudication)
report = ['# Comparación 650: alcance factual en el primer borrador']
for r in adjudication:
    report += ['## '+r['case_id']+' — '+r['arm'], r['text'],
               f"Hechos: installed={r['installed']}; visibleWindowCount={r['visible_window_count']}.",
               r['draft'], r['verdict']+': '+r['reason']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# 650: una instrucción de alcance corrige el primer borrador observado

El brazo actual reproduce literalmente «Spotify is installed and running, but no window is currently visible». La situación y su payload visible son iguales a los registrados en 647/t15. Al añadir únicamente una instrucción de sistema que distingue instalación/ventanas de procesos, responde «Spotify is installed but no visible windows are currently open».

Resultado completo: 7/8 borradores correctos con el escritor actual, 8/8 con la instrucción. Los otros siete casos son fixtures declarados, con nombres, cantidades e idiomas distintos; no son estados reales de esas aplicaciones ni un replay completo del producto. Los 16 terminan por EOS. No se cambian modelo, perfil, backend ni los hechos entre brazos. La revisión es manual y conserva todos los textos; no usa el validador defectuoso de 649.

Pico GPU 3497,559 MiB, RAM 719,625 MiB y 11,109 s del servidor y descendientes, sin infracciones. No acredita UI/voz conjunta ni un mínimo global. La instrucción pasa a candidata para integración y prueba de producto; todavía no se adopta fuente. El contrato factual 649 sigue incompleto: corregir la generación no demuestra que rechace cualquier afirmación sin respaldo. Encuesta: 25 cubiertos, 717 abiertos, 0 no aplicables.
'''
seal(out, private, {'utc': datetime.now(timezone.utc).isoformat(), 'scores': scores,
    'per_arm': 8, 'all_finish_stop': True, 'actual647_first_draft_reproduced': True,
    'mean_seconds': {arm: mean(r['seconds'] for r in adjudication if r['arm'] == arm) for arm in scores},
    'source_adopted': False, 'resources': read(out/'RESOURCES.json'), 'ui_or_voice_credit': False,
    'survey': {'covered': 25, 'open': 717, 'not_applicable': 0}}, note,
    ['panel.json', 'requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md', 'server.log'])
state = read(base/'RELEVO_ACTIVO.json')
state.pop('activeCampaign', None)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='650 sellada: primer borrador 7/8→8/8 con alcance; reproduce647. Fuente651 publicada/Fullverde.25/717/0.',
    continuation='Integrar como652 la misma instrucción de alcance, comparar payloads contra650 y ejecutar producto653. No fuente adoptada aún; contrato649 e idiomahas pendientes.')
write(base/'RELEVO_ACTIVO.json', state)
print({'native650_scores': scores, 'source_adopted': False})
