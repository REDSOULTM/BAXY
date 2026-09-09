"""Preserve the bounded factual candidate and adjudicate actual repair evidence."""
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-window-state-facts671'
out.mkdir(exist_ok=False)
(out/'CANDIDATE.patch').write_bytes(subprocess.check_output(['git','diff','--','src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py'], cwd=root))
(out/'CANDIDATE_TEST.py').write_bytes((root/'tests/test_c03_window_state_facts.py').read_bytes())
temp = Path(os.environ['TEMP'])
for suffix, name in [('baseline','INITIAL_BASELINE'),('focal','INITIAL_FOCAL'),('scope-before','SCOPE_BEFORE'),('final-baseline','BASELINE'),('focal-refined','FOCAL')]:
    (out/(name+'.log')).write_bytes((temp/f'c03-state-facts671-{suffix}.log').read_bytes())
assert '105 failed, 118 passed' in (out/'BASELINE.log').read_text(encoding='utf-8-sig')
assert '662 passed' in (out/'FOCAL.log').read_text(encoding='utf-8-sig')
note671 = '''# 671 — contradicciones de foco detectadas, reparación aún insuficiente

Se extiende el contrato factual existente para afirmaciones explícitas de foco, ligadas al título/proceso observado. Normal/minimizada/maximizada no determinan foco. Conserva campos desconocidos, nombres que contienen estados, sujetos distintos, preguntas, condicionales, incertidumbre y negación de conjunción ambigua. Es gramática delimitada, no verificación semántica universal ni prueba de respuesta completa.

Cohorte final223: módulo factual publicado en proceso aislado105fallos/118pases; candidata223pases. Focal integrada662pases/0skips,3,90s. También se guardan baseline inicial216casos104fallos/112pases y controles de alcance que encontraron6fallos antes de refinar. Sin fuente mutada para medir baseline. No dueñas amplias/Fast ni adopción aún: el modelo real672 mantiene10/14 respuestas correctas, aunque deja de publicar tres contradicciones claras. Encuesta26/716/0.
'''
seal(out,out,{'adopted':False,'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'factual_source_sha256':sha(root/'src/baxy_mind/window_prose_facts.py'),
    'test_sha256':sha(root/'tests/test_c03_window_state_facts.py'),
    'same_final_cohort':{'total':223,'baseline_failed':105,'baseline_passed':118,'candidate_passed':223},
    'integrated_focal_passed':662,'broad_validation_run':False},note671,[])

out = base / 'astra-compositor-window-states672'
private = home / 'C03-compositor-window-states672-private'
assert not (out/'RESULT.json').exists()
panel = {r['case_id']:r for r in read(private/'panel.json')}
finals = rows(private/'finals.jsonl')
requests = rows(private/'requests.jsonl')
responses = rows(private/'responses.jsonl')
old = {(r['case_id'],r['arm']):r for r in rows(home/'C03-native-window-projection668-private/responses.jsonl')}
assert len(finals)==14 and len(requests)==len(responses)==19
assert all(r['response']['choices'][0]['finish_reason']=='stop' for r in responses)
for r in responses:
    if r['call']==1:
        assert r['response']['choices'][0]['message']['content']==old[r['case_id'],'projection667']['response']['choices'][0]['message']['content']
adjudication=[]
for r in finals:
    failed = r['case_id'].startswith('topmost-')
    reason = ('Empty after three rejected contradictory drafts.' if not r['final'] else
              'Incomplete or ambiguous focus answer; always-on-top alone does not answer both predicates.') if failed else 'All requested observed facts and language preserved; same initial answer668 and one call.'
    adjudication.append({**panel[r['case_id']],**r,'verdict':'failed' if failed else 'correct','reason':reason})
write(private/'adjudication.json',adjudication)
report=['# 672 — 10/14; two empty and two incomplete/ambiguous']
for r in adjudication:
    report += ['## '+r['case_id'],r['text'],r['final'] or '(empty)',r['verdict']+': '+r['reason'],json.dumps(r['facts'],ensure_ascii=False)]
    report += [json.dumps(x,ensure_ascii=False) for x in responses if x['case_id']==r['case_id']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note672='''# 672 — la guardia frena contradicciones pero no completa las respuestas

Compositor real con transporte nativo:10/14 correctas. Los14primeros borradores reproducen668. Diez controles correctos conservan una llamada. Tres contradicciones claras se rechazan: un caso pasa a respuesta incompleta y dos agotan tres intentos con salida vacía. El cuarto compuesto inglés conserva negación ambigua e incompletitud. Ningún vacío cuenta como éxito.19llamadas totales, todasEOS.

GPU3497,559MiB/RAM719,164MiB/12,157s, sin infracciones; registro y fuentes intactos. No kernel/UI/voz. Falta información específica en el reintento: State only what seen shows no identifica el campo contradicho.671 no adoptada; probar evidencia externa del campo en el reintento existente. Encuesta26/716/0.
'''
seal(out,private,{'correct':10,'total':14,'empty':2,'incomplete_or_ambiguous':2,'native_calls':19,
    'all_first_drafts_reproduce668':True,'source_adopted':False,'resources':read(out/'RESOURCES.json')},note672,
    ['panel.json','requests.jsonl','responses.jsonl','finals.jsonl','adjudication.json','RESULT.md'])

out=base/'astra-native-focus-feedback673'
private=home/'C03-native-focus-feedback673-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl')
previous={(r['case_id'],r['call']):r for r in rows(home/'C03-compositor-window-states672-private/responses.jsonl')}
assert len(panel)==len(responses)==12
adjudication=[]
for r in responses:
    case=panel[r['case_id'],r['arm']]
    assert r['response']['choices'][0]['finish_reason']=='stop'
    if case['variant']=='original' and case['arm']=='generic672':
        assert r['response']['choices'][0]['message']['content']==previous[case['origin'],2]['response']['choices'][0]['message']['content']
    correct=case['arm']=='verified_field_feedback'
    reason=('Both opposite states explicitly preserved, correct subject/name and language. Individually reviewed.' if correct else
            'Focus is omitted.' if case['origin'].endswith('true') else 'Incorrect positive focus contradicts false observation.')
    adjudication.append({**case,'response':r,'verdict':'correct' if correct else 'failed','reason':reason})
write(private/'adjudication.json',adjudication)
report=['# 673 — verified field6/6; generic0/6']
for r in adjudication:
    report += ['## '+r['case_id']+' / '+r['arm'],r['text'],r['response']['response']['choices'][0]['message']['content'],r['verdict']+': '+r['reason'],json.dumps(r['payload'],ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note673='''# 673 — evidencia del campo permite reparar los seis casos probados

Tres reintentos originales672 y tres variantes de nombre: aviso genérico0/6; misma petición más datos de contradicción verificados6/6. Los controles originales reproducen672. La corrección identifica sujeto, predicado activo, valor observado, valor afirmado y borrador rechazado; no añade otra instrucción de sistema ni una respuesta prefabricada. Todos12 EOS, GPU3497,559MiB/RAM719,574MiB/9,812s, sin infracciones ni cambio de registro.

Contraste bibliográfico acotado: Kamoi et al., TACL2024, https://aclanthology.org/2024.tacl-1.78/ distingue feedback externo fiable de autocrítica sin evidencia; Wadhwa et al., Findings2024, https://aclanthology.org/2024.findings-emnlp.716/ estudia feedback fino con modelos entrenados, no este runtime. Motivan la distinción, no prueban BAXY. Aquí la evidencia viene del campo tipado y la comprobación determinista, no de otro juez LLM.

No promoción desde el experimento aislado. Siguiente674: derivar la misma evidencia desde el contrato factual y llevarla al reintento existente; demostrar paridad, controles negativos, compositor real y producto. El inglés con negación ambigua/incompletitud sigue pendiente. Encuesta26/716/0; C03 activo.
'''
seal(out,private,{'scores':{'generic672':0,'verified_field_feedback':6},'total_per_arm':6,
    'all_original_controls_reproduce672':True,'source_adopted':False,'resources':read(out/'RESOURCES.json')},note673,
    ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
print({'candidate671':'not adopted','compositor672':'10/14','feedback673':'6/6 vs0/6'})
