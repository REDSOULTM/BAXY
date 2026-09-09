"""Record the earliest compound-state confusion without overstating negation scope."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-native-compound-layers670'
private = home / 'C03-native-compound-layers670-private'
assert not (out / 'RESULT.json').exists()
panel = {(r['case_id'], r['arm']): r for r in read(private / 'panel.json')}
responses = rows(private / 'responses.jsonl')
previous = {r['case_id']: r for r in rows(home / 'C03-native-window-projection668-private/responses.jsonl') if r['arm'] == 'projection667'}
assert len(panel) == len(responses) == 12
assert read(out / 'RESOURCES.json')['complete']
adjudication = []
for response in responses:
    case = panel[response['case_id'], response['arm']]
    choice = response['response']['choices'][0]
    assert choice['finish_reason'] == 'stop'
    if case['arm'] == 'compositor667':
        assert choice['message']['content'] == previous[case['case_id']]['response']['choices'][0]['message']['content']
    correct = case['case_id'] == 'topmost-en-true' and case['arm'] == 'native_facts'
    if correct:
        reason = 'Explains explicitly that Atlas is active/in focus while always-on-top is false. Initial not(A and B) is resolved by its following explicit distinction.'
    elif case['case_id'].endswith('false'):
        reason = 'Asserts active despite current-interaction=false; native explanation incorrectly equates normal/visible with active.'
    elif case['case_id'] == 'topmost-es-true' and case['arm'] == 'native_facts':
        reason = 'Starts with unambiguous denial of both states, then contradicts it by correctly saying active; also wrongly infers not-topmost from normal.'
    elif case['case_id'] == 'topmost-es-true' and case['arm'] == 'compositor667':
        reason = 'Incorrectly denies active with ni and leaks alwaysOnTop label into Spanish.'
    else:
        reason = 'Does not clearly answer the active/current-interaction predicate separately; answers only topmost or leaves negation scope ambiguous. Incomplete, not evidence of an unambiguous denial.'
    adjudication.append({**case, 'response':response, 'verdict':'correct' if correct else 'failed', 'reason':reason})
write(private / 'adjudication.json', adjudication)
report = ['# 670 — native1/4, identity0/4, compositor0/4']
for r in adjudication:
    report += ['## '+r['case_id']+' / '+r['arm'], r['text'], r['response']['response']['choices'][0]['message']['content'], r['verdict']+': '+r['reason'], json.dumps(r['payload'], ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
note = '''# 670 — confusión antes de la política completa

Mismos cuatro fixtures668, campos proyectados y parámetros: nativo mínimo1/4, identidad0/4, compositor0/4. Los cuatro controles completos reproducen668. El nativo ya equipara normal/visible con activa en los dos casos cuyo foco es falso. En español activo=true también se contradice dentro de su propia respuesta. Quitar instrucciones no basta. No se añade otra regla equivalente ni se adopta667 con estos fallos abiertos.

Matiz de adjudicación668: «not active and configured…» admite negación de la conjunción completa. Sin una afirmación posterior de actividad, debe contarse respuesta incompleta/ambigua, no negación inequívoca del foco. Ese caso sigue fallando; el total668 no cambia. El nativo inglés670 sí resuelve explícitamente ambos hechos después de esa apertura, y se cuenta correcto. Esta corrección del motivo preserva los originales668 sellados.

Todos12 EOS, GPU3497,559MiB/RAM722,902MiB,17,234s, sin infracciones ni cambio de registro. Sin UI/voz ni crédito de encuesta. Siguiente: extender el contraste factual existente para estados de ventana con sujeto y negación conservados, y comprobar reparación por la ruta real del compositor. No añadir otro narrador ni respuestas visibles fijas. C03 activo, encuesta26/716/0.
'''
seal(out, private, {'scores':{'native_facts':1,'identity_facts':0,'compositor667':0}, 'total_per_arm':4,
                   'all_eos':True, 'all_compositor_reproduce668':True, 'source_adopted':False,
                   'resources':read(out / 'RESOURCES.json'), 'ui_or_voice_credit':False,
                   'corrects668_reason_not_score':'topmost-en-true projection667: incomplete/ambiguous negation, not unambiguous activity denial'},
     note, ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
print({'native': '1/4', 'identity': '0/4', 'compositor': '0/4'})
