"""Preserve candidate and policy diagnostics without granting product coverage."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-context-candidates643'; private = home/'C03-context-candidates643-private'
assert not (out/'PINS.json').exists()
retrieval = read(private/'retrieval.json')
corrected = []
for r in retrieval:
    operation = 'filesystem.list' if r['case_id'] == 'shift-files-en' else r['operation']
    corrected.append({'case_id': r['case_id'], 'operation': operation,
        **{key+'_rank': r[key].index(operation)+1 if operation in r[key] else None for key in ['current', 'context']}})
write(out/'ADJUDICATION.json', {'corrected_ranks': corrected,
    'control_annotation_correction': 'Raw shift-files-en accidentally named nonexistent file.list. Existing candidate arrays show canonical filesystem.list at7 current and10 contextual. Preserve original output; this is an annotation correction, not a retrieval change.',
    'no_global_history_concatenation_adopted': True})
note643 = '''# 643 — el contexto completo no sustituye al mensaje actual

Recuperación léxica real del catálogo autenticado: window.application.status pasa de ausente a los puestos 5 y 9 para los dos seguimientos ingleses. Para «¿Y Steam?» sigue ausente tras respuestas previas fallidas. La referencia española ya tenía la operación en el puesto 1 y la concatenación la baja al 22. En controles de cambio de tema, network.status pasa del puesto 22 a ausente; reloj y volumen siguen presentes. El control de ficheros tenía un error de anotación (`file.list`); la operación real `filesystem.list` ocupa los puestos 7 y 10, preservados en ADJUDICATION.json sin alterar las listas originales.

No se adopta concatenación general de historia. Es evidencia de recuperación, sin inferencia, dispatch ni cobertura de conducta. La literatura de recuperación conversacional orienta a seleccionar contexto relevante; no demuestra este algoritmo: https://aclanthology.org/2022.emnlp-main.311/ y https://aclanthology.org/2024.findings-acl.792/. Herencia: biblioteca/gemma4-agent/documentacion/07_latencia/research/4_contexto.md; product360 ya rechazó volver a presentar órdenes antiguas como actuales.
'''
(out/'RESULT.md').write_text(note643, encoding='utf-8', newline='\n')
write(out/'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root/'.gitattributes').open('a', encoding='utf-8', newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-context-candidates643/** -text\n')
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write('\n\n'+note643)
summaries = {}
for campaign in [644, 645]:
    out = base/f'astra-native-context{campaign}'; private = home/f'C03-native-context{campaign}-private'
    assert not (out/'RESULT.json').exists()
    panel = {(r['case_id'], r['arm']): r for r in read(private/'panel.json')}
    results = rows(private/'responses.jsonl'); assert len(results) == len(panel) == 20
    resources = read(out/'RESOURCES.json')
    assert resources['complete'] and not resources['violations'] and resources['manifest_unchanged']
    arms = ['current', 'diagnostic_candidate'] if campaign == 644 else ['candidate_only', 'context_contract']
    for case_id in {r['case_id'] for r in panel.values()}:
        a = panel[case_id, arms[0]]['payload']; b = panel[case_id, arms[1]]['payload']
        key = 'tools' if campaign == 644 else 'messages'
        assert {k: v for k, v in a.items() if k != key} == {k: v for k, v in b.items() if k != key}
        if campaign == 645: assert a['messages'][1:] == b['messages'][1:]
    judged = []
    for r in results:
        case = panel[r['case_id'], r['arm']]; choice = r['response']['choices'][0]
        calls = choice['message'].get('tool_calls') or []
        actual = [call['function']['name'].removeprefix('baxy_').replace('__', '.') for call in calls]
        judged.append({**r, 'text': case['text'], 'history': case['history'], 'expected': case['expected'],
            'actual': actual, 'correct_selection': actual == case['expected'] and choice['finish_reason'] != 'length'})
    scores = {arm: sum(r['correct_selection'] for r in judged if r['arm'] == arm) for arm in arms}
    write(private/'adjudication.json', judged)
    report = [f'# Selección nativa {campaign} — {scores}']
    for r in judged:
        report += ['## '+r['case_id']+' / '+r['arm'], r['text'], json.dumps(r['history'], ensure_ascii=False),
            json.dumps(r['response']['choices'][0], ensure_ascii=False),
            f"Esperado: {r['expected']}; obtenido: {r['actual']}; correcto: {r['correct_selection']}"]
    (private/'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
    note = f'''# {campaign} — selección nativa aislada

Resultado: {scores}, diez casos por brazo. Cuatro historias de cuatro mensajes tomadas de 642 y seis controles independientes con historia coherente. No es repetición exacta de toda la historia del producto. Los conjuntos de candidatos diagnósticos incluyen deliberadamente window.application.status; eso no es una política de recuperación implementada ni acredita generalización. Se conserva el texto nativo completo en el informe privado.

{'644 modifica sólo la disponibilidad de la candidata: corrige tres selecciones inglesas; los seguimientos españoles y la prohibición siguen fallando. La prohibición produce una lectura en ambos brazos del selector aislado, no demuestra una regresión del producto, cuya guardia previa no ejecutó efectos en642.' if campaign == 644 else '645 mantiene idénticas candidatas y modifica sólo una regla del sistema sobre referencia contextual y lectura nueva del estado actual. Su resultado no permite saltarse la recuperación, los argumentos, las guardias ni el compositor. No se adopta fuente o perfil con esta prueba sola.'}

Recursos del servidor aislado: GPU {resources['gpu_peak_mib']:.3f} MiB, RAM {resources['ram_peak_mib']:.3f} MiB, {resources['seconds']:.3f} s, sin infracciones. Registro intacto; sin dispatch, interfaz, voz ni cobertura de encuesta. C03 continúa activo: 25 cubiertos, 717 abiertos, 0 no aplicables.
'''
    seal(out, private, {'source_modified': False, 'scores': scores, 'per_arm': 10,
        'one_difference_verified': True, 'resources': resources,
        'diagnostic_candidate_only': True, 'product_or_coverage_credit': False}, note,
        ['panel.json', 'requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md'])
    summaries[str(campaign)] = scores
print(summaries)
