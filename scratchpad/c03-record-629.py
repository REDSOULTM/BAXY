"""Seal the failed integrated candidate before repairing objective continuity."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-clarification-product629';private=home/'C03-clarification-product629-private'
assert not (out/'RESULT.json').exists()
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal'];assert len(finals)==len(panel)==20
failed={'H0012':'Existing noisy identity interpretation failure.',
 'missing-app':'Existing ungrammatical preposition in clarification.',
 'missing-value':'628 correctly returns clarify on26, then shell resumes prior app objective on27 and loses it.',
 'missing-reference-en':'Existing unsupported refusal instead of missing-reference question.',
 'knowledge-discourse':'Existing ciertos bacterias agreement error.',
 'missing-level-variant-2':'New volume request merged with preceding clarification; composition fails.',
 'missing-level-variant-4':'New volume request merged with preceding clarification; false interpretation failure.',
 'missing-level-variant-6':'New volume request merged with preceding clarification; composition fails.',
 'missing-level-variant-8':'New volume request merged with preceding clarification; composition fails.'}
judged=[{**c,'terminal':f,'verdict':'failed' if c['case_id'] in failed else 'correct',
 'reason':failed.get(c['case_id'],'Meets declared response and language; no effects.')}
 for c,f in zip(panel,finals)]
write(private/'adjudication.json',judged)
report=['# Producto629 — lector reparado, continuidad todavía incorrecta']
for r in judged:report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
progress=[r['event'] for r in events if r.get('type')=='event' and r.get('event',{}).get('type')=='boot_stage' and r['event'].get('label')]
write(private/'progress.json',progress)
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
audits=rows(private/'turn-audit.jsonl')
assert not any(r.get('final',{}).get('effect_operations') for r in audits)
note='''# Producto629: 11/20, candidato628 aún sin adopción

Los12controles608 conservan7correctos/5fallos. Sólo4de8variantes nuevas aclaran correctamente. El cambio628 sí alcanza explicit_clarification: request26 devuelve clarify sin efectos, pero el shell llama otra vez a turn.decide27 al fusionarlo con la aclaración pendiente de aplicación. MindClarificationPolicy.IsSelfContainedRequest siempre devuelve false para clarify; PreserveObjective controla tanto reanudación anterior como conservación del nuevo objetivo. No se debe ponerlo a false indiscriminadamente: perdería la respuesta al siguiente fragmento.

La reparación630 distinguirá una orden nueva identificada por la mente y la conservación de su propio dato pendiente, con un indicador opcional sin autoridad de ejecución. No se añaden patrones de lenguaje al shell. Se conserva628 como candidato necesario, todavía sin adopción.3375pass/1skip+121subtests y Fast verde no prueban finales del producto. GPU3499,559MiB/RAM2461,641MiB;93,906s. Cero efectos en auditoría; no UI/voz. Encuesta25/717/0.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':628,'finals':20,'correct':11,
 'same608_correct':7,'same608_total':12,'variants_correct':4,'variants_total':8,'adopted':False,
 'first_repaired_boundary':'explicit_clarification on request26',
 'next_wrong_boundary':'MainWindowViewModel resumes previous objective because clarify is never self-contained',
 'failed_cases':failed,'resources':read(out/'resources.json'),'ui_or_voice_credit':False},
 note,['panel.json','capture/events.jsonl','turn-audit.jsonl','shell-trace.jsonl','compose-audit.jsonl','adjudication.json','progress.json','RESULT.md'])
out=base/'astra-clarification-source628'
for src,dest in [('c03-clarification628-owners.log','OWNERS.log'),('c03-clarification628-fast.log','FAST.log')]:
 (out/dest).write_bytes((Path(os.environ['TEMP'])/src).read_bytes())
paths=['src/baxy_mind/effect_intent.py','tests/test_effect_intent.py','tests/test_turn_policy.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']
(out/'source628.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
write(out/'RESULT.json',{'adopted':False,'targeted_passed':55,'owners_passed':3375,'owners_skipped':1,'owners_subtests':121,'fast_exit':0,'release_seconds':18.55,'product629_correct':11,'product629_total':20,'next_candidate':630})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-clarification-source628/** -text\n')
print({'source628_adopted':False,'product629_correct':11,'total':20})
