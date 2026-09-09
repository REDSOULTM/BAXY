"""Preserve first-difference636/637 before changing window multiplicity."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-package-product637';private=home/'C03-package-product637-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
assert sha(private/'panel.json')==sha(home/'C03-window-product634-private/panel.json')
finals=[r for r in events if r.get('type')=='terminal'];assert len(finals)==12
observations={r['trace']:r['payload'] for r in rows(private/'compose-audit.jsonl') if r.get('payload',{}).get('operation')}
assert observations['t3']['seen']['hasVisibleWindow'] is True
assert observations['t3']['seen']['visibleWindowCount']==1
failures={'window-order-en':'Still says one Steam window;635 proves the single-window-per-process inventory undercounts.','focus-en':'English question still classified mixed and answered in Spanish.'}
judged=[{**c,'terminal':f,'observation':observations.get(f't{i}'),'verdict':'failed' if c['case_id'] in failures else 'correct','reason':failures.get(c['case_id'],'Meets response scope and language. Existential a window does not assert a total count; explicit one window is adjudicated as a count.')} for i,(c,f) in enumerate(zip(panel,finals),1)]
write(private/'adjudication.json',judged)
report=['#637: identidad corregida, multiplicidad e idioma pendientes']
for r in judged:report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason'],json.dumps(r['observation'],ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''#636/637 — primera diferencia de identidad confirmada

Notepad cambia de cero ventanas a visible=true y la respuesta ya reconoce que está abierto. Mismo panel12 y mismo perfil que634, sin hooks, sólo lecturas.637:10/12 correctos con el criterio de cardinalidad corregido por635; bajo ese criterio634tenía9/12, no10/12. Se conserva su adjudicación original y se explicita aquí la revisión. Persisten one window de Steam e idioma español ante pregunta inglesa. El número1de Notepad sigue siendo incompleto; sólo la existencia mejoró. No cobertura H0040 todavía.

636 C# pasa512pruebas Providers,0skips agregados y4opt-in impresas aparte;Fast exit0/Release14,15s.637:3497,559MiB GPU,1826,879MiB RAM,82,782s incluyen NativeAOT. No UI/voz conjunta. Candidato636 necesario pero no se adopta como inventario terminado;638debe enumerar todos los handles visibles y mantener la selección/foco exactos.
'''
seal(out,private,{'source':636,'correct':10,'total':12,'baseline634_readjudicated_correct':9,'baseline634_original_correct':10,'notepad_presence_fixed':True,'count_correct':False,'failed_cases':failures,'resources':read(out/'resources.json'),'ui_or_voice_credit':False},note,['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl','adjudication.json','RESULT.md'])
out=base/'astra-package-source636';prereg=read(out/'PREREG.json')
assert all(sha(root/p)==v for p,v in prereg['sources'].items())
(out/'FAST.log').write_bytes((Path(os.environ['TEMP'])/'c03-package636-fast.log').read_bytes())
write(out/'RESULT.json',{'adopted':False,'providers_passed':512,'aggregate_skipped':0,'printed_opt_in_omissions':4,'fast_exit':0,'release_seconds':14.15,'product637_notepad_presence_fixed':True,'next_candidate':638,'source_unchanged_during_product':True})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as f:f.write('/artifacts/comprobaciones/C03/astra-package-source636/** -text\n')
print({'notepad_presence_fixed':True,'correct':10,'total':12,'next':638})
