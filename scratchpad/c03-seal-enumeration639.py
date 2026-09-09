"""Adjudicate real window counts against stable independent native snapshots."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-enumeration-product639';private=home/'C03-enumeration-product639-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
assert sha(private/'panel.json')==sha(home/'C03-package-product637-private/panel.json')
finals=[r for r in events if r.get('type')=='terminal'];assert len(finals)==12
observations={r['trace']:r['payload'] for r in rows(private/'compose-audit.jsonl') if r.get('payload',{}).get('operation')}
before=read(private/'windows-before.json');after=read(private/'windows-after.json')
assert before['windows']==after['windows']
counts=Counter(r['process'].casefold() for r in before['windows'])
processes={'Steam':'steamwebhelper.exe','Google Chrome':'chrome.exe','Bloc de notas':'notepad.exe','Spotify':'spotify.exe','Paint':'mspaint.exe'}
for i,case in enumerate(panel[:8],1):
    seen=observations[f't{i}']['seen'];assert seen['requestedName']==case['name']
    assert seen['visibleWindowCount']==counts[processes[case['name']]],(case,seen)
assert counts['steamwebhelper.exe']==2 and counts['notepad.exe']==0
failure='English focus question remains classified mixed and answered in Spanish.'
judged=[{**c,'terminal':f,'observation':observations.get(f't{i}'),'verdict':'failed' if c['case_id']=='focus-en' else 'correct','reason':failure if c['case_id']=='focus-en' else 'Matches observed scope/state/count and requested language; no write operation.'} for i,(c,f) in enumerate(zip(panel,finals),1)]
write(private/'adjudication.json',judged)
report=['#639 — 11/12; cantidades verificadas']
for r in judged:report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason'],json.dumps(r['observation'],ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''#638/639 — conteos coinciden con Windows

639 conserva exactamente los12casos637.11/12finales correctos: Steam muestra2ventanas en ambas lecturas ES/EN y Chrome1. Notepad ya no tenía ventanas ANTES de arrancar639 y tampoco después; su respuesta negativa ahora coincide con la observación independiente. No se atribuye la desaparición a un actor ni se confunde el cambio de estado con regresión. Todos los handles de ambas instantáneas son idénticos. Las8lecturas por aplicación conservan identidad y cantidad; sólo el foco inglés mantiene el fallo de idioma mixed→español.

639:3497,559MiB GPU,1894,625MiB RAM,77,313s incluyen NativeAOT;sin infracciones.513dueñas Providers/4opt-in impresas aparte,46integración/0skips;Fast exit0,Release11,89s. La prueba Win32 nueva detectaba la pérdida de una de dos ventanas y ahora pasa, sin activar las ventanas de prueba. No interfaz/voz conjunta ni Full638. La coberturaH0040 aún espera640: otro paquete visible, referencias elípticas/pronominales y preguntas de cantidad; no se cierra con sólo los casos ya favorables.
'''
seal(out,private,{'source':638,'correct':11,'total':12,'named_queries_count_and_scope_correct':8,
    'independent_snapshots_identical':True,'notepad_visible_before':0,'notepad_visible_after':0,
    'steam_visible_count':2,'failed_cases':{'focus-en':failure},'resources':read(out/'resources.json'),
    'ui_or_voice_credit':False,'whole_window_requirement_accepted':False},note,
    ['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl','adjudication.json','RESULT.md','windows-before.json','windows-after.json'])
print({'correct':11,'total':12,'named_scope_and_count_correct':8,'next_generalization':640})
