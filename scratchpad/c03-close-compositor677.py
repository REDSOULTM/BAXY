"""Seal the complete original17-case result without claiming global completion."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-compositor-focus-coverage677'
private=home/'C03-compositor-focus-coverage677-private'
assert not (out/'RESULT.json').exists()
panel={r['case_id']:r for r in read(private/'panel.json')}
finals=rows(private/'finals.jsonl')
requests=rows(private/'requests.jsonl')
responses=rows(private/'responses.jsonl')
previous=home/'C03-compositor-focus-feedback675-private'
old_requests={(r['case_id'],r['call']):r for r in rows(previous/'requests.jsonl')}
old_responses={(r['case_id'],r['call']):r for r in rows(previous/'responses.jsonl')}
old_finals={r['case_id']:r for r in rows(previous/'finals.jsonl')}
assert len(finals)==len(panel)==17 and len(requests)==len(responses)==24
for r in requests:
    if r['call']==1: assert r['payload']==old_requests[r['case_id'],1]['payload']
for r in responses:
    assert r['response']['choices'][0]['finish_reason']=='stop'
    if r['call']==1: assert r['response']['choices'][0]['message']['content']==old_responses[r['case_id'],1]['response']['choices'][0]['message']['content']
adjudication=[]
for r in finals:
    assert r['final'] and r['calls']==(2 if r['case_id'].startswith('topmost-') else 1)
    if not r['case_id'].startswith('topmost-'): assert r['final']==old_finals[r['case_id']]['final']
    adjudication.append({**panel[r['case_id']],**r,'verdict':'correct',
        'reason':'Individually reviewed: preserves subject/name, observed state/count, language and all requested compound predicates. Explicit contrast resolves the initial yes/no scope.'})
write(private/'adjudication.json',adjudication)
report=['# 677 — 17/17; ten single-call controls and seven repaired compound answers']
for r in adjudication:
    report+=['## '+r['case_id'],r['text'],r['final'],r['verdict']+': '+r['reason'],json.dumps(r['facts'],ensure_ascii=False)]
    report += [json.dumps(x,ensure_ascii=False) for x in responses if x['case_id']==r['case_id']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# 677 — mismos17casos, todos completos y veraces

Mismos17casos675, sin sustituir preguntas ni relajar criterios:15/17→17/17. Las17primeras peticiones y sus borradores coinciden exactamente. Diez controles correctos conservan su respuesta y una llamada. Siete compuestos requieren un reintento; ahora también se reparan la omisión inicial de Brújula7 y el foco inglés ambiguo. Los datos de falta de respuesta no inventan un valor afirmado por el borrador.

Veinticuatro llamadas, todasEOS; GPU3497,559MiB/RAM720,164MiB/16,266s sin infracciones. Registro intacto. No kernel/UI/voz ni mínimo conjunto. Candidata676 aún no adoptada: dueñas/declaraciones y Fast/producto678 completarán su validación. Encuesta26/716/0; C03 sigue abierto con su alcance completo.
'''
seal(out,private,{'correct':17,'total':17,'previous_same_cohort_correct':15,'all_first_requests_and_drafts_identical':True,
    'single_call_controls':10,'two_call_compound_cases':7,'native_calls':24,'source_adopted':False,'resources':read(out/'RESOURCES.json')},note,
    ['panel.json','requests.jsonl','responses.jsonl','finals.jsonl','adjudication.json','RESULT.md'])
state_path=base/'RELEVO_ACTIVO.json'
state=read(state_path)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='676 candidata733 focales;677 compositor17/17. Dueñas2566+121subtests, declaraciones600/1skip ambiental. Fast activo4699.',
    continuation='Recoger Fast4699 sin reiniciar; después producto678 preflight ya compilado. Rama/main/encuesta intactos, source676 no adoptada. CalidadPython por defecto BAXYQuality; runtimePython no tiene ruff.',
    activeValidation={'kind':'Fast','session_id':4699,'log':str(Path(os.environ['TEMP'])/'c03-focus-coverage676-fast.log')})
write(state_path,state)
print({'compositor677':'17/17','first_requests_identical':True})
