"""Seal all native projection results, including the new compound-state failures."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-native-window-projection668'
private = home / 'C03-native-window-projection668-private'
assert not (out / 'RESULT.json').exists()
panel = {(r['case_id'], r['arm']): r for r in read(private / 'panel.json')}
responses = rows(private / 'responses.jsonl')
previous = {r['case_id']: r for r in rows(home / 'C03-native-schema-prose662-private/responses.jsonl') if r['arm'] == 'current'}
assert len(panel) == len(responses) == 28
assert read(out / 'RESOURCES.json')['complete']
assert read(out / 'PREREG.json')['source_sha256'] == sha(root / 'src/baxy_mind/llm.py')
adjudication = []
for response in responses:
    case = panel[response['case_id'], response['arm']]
    choice = response['response']['choices'][0]
    assert choice['finish_reason'] == 'stop'
    reason = 'Preserves observed subject, state/count and requested language; individually reviewed.'
    failed = False
    if case['case_id'] in previous and case['arm'] == 'published660':
        assert choice['message']['content'] == previous[case['case_id']]['response']['choices'][0]['message']['content']
    if case['case_id'] == 'observed661' and case['arm'] == 'published660':
        failed = True
        reason = 'Spanish state-label leakage reproduced exactly.'
    if case['case_id'].startswith('topmost-'):
        failed = True
        if case['case_id'] == 'topmost-en-true' and case['arm'] == 'published660':
            reason = 'Truthful always-on-top negative but omits whether Atlas is active; incomplete two-part answer.'
        elif case['case_id'].endswith('true'):
            reason = 'Incorrectly denies active/current interaction although its observation is true; always-on-top is independently false.'
        else:
            reason = 'Incorrectly asserts active/current interaction although its observation is false; always-on-top is independently true.'
        if case['case_id'] == 'topmost-es-true' and case['arm'] == 'projection667':
            reason += ' Also copies internal alwaysOnTop label into Spanish prose.'
    adjudication.append({**case, 'response': response, 'verdict': 'failed' if failed else 'correct', 'reason': reason})
scores = Counter(r['arm'] for r in adjudication if r['verdict'] == 'correct')
assert dict(scores) == {'projection667': 10, 'published660': 9}
write(private / 'adjudication.json', adjudication)
report = ['# 668 — exact originals improved; compound states remain incorrect']
for r in adjudication:
    report += ['## ' + r['case_id'] + ' / ' + r['arm'], r['text'], r['response']['response']['choices'][0]['message']['content'], r['verdict'] + ': ' + r['reason'], r['facts']['situation'], json.dumps(r['payload'], ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
note = '''# 668 — mejora la fuga original; estados compuestos siguen abiertos

Veintiocho borradores completos,14 casos por brazo. Los diez controles publicados reproducen662:9/10. La proyección precisa667 produce10/10 en esos mismos casos; la petición real pasa a «La ventana activa es "ChatGPT". Está maximizada.». Todas las peticiones candidatas originales coinciden con el compositor real, cambiando únicamente la etiqueta booleana.

Cuatro fixtures nuevos ES/EN separan actividad y configuración siempre encima; ambos brazos0/4. Confunden estados opuestos. En inglés activo=true, el baseline omite contestar actividad y667 la niega incorrectamente; también aparece alwaysOnTop como jerga en un control español. No se ocultan estos fallos ni se adopta la candidata por el10/10 anterior. Los nuevos fixtures son diagnósticos declarados, no observaciones de ese campo en el proveedor ni resultados del producto.

GPU3497,559MiB y RAM719,086MiB del servidor,18,282s, sin infracciones. Registro intacto. No UI/voz ni mínimo conjunto. Candidata667 sigue WIP; producto669 permitirá localizar el comportamiento en la ruta real. Encuesta26/716/0; C03 sigue activo. El defecto compuesto necesita conservar cada predicado por separado; no basta eliminar la palabra foreground.
'''
seal(out, private, {'scores': dict(scores), 'total_per_arm': 14, 'original_per_arm': 10,
                   'new_compound_cases_correct_per_arm': 0, 'all_eos': True, 'source_adopted': False,
                   'resources': read(out / 'RESOURCES.json'), 'ui_or_voice_credit': False},
     note, ['panel.json', 'requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md'])
print({'scores': dict(scores), 'source_adopted': False})
