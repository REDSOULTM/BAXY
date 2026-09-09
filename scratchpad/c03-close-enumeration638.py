"""Publish the verified provider repair, keeping reference and read gaps open."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-window-reference-product640';private=home/'C03-window-reference-product640-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
panel=read(private/'panel.json');events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal'];assert len(finals)==len(panel)==20
compose=rows(private/'compose-audit.jsonl')
observations={r['trace']:r['payload'] for r in compose if r.get('payload',{}).get('operation')}
assert observations['t13']['seen']['visibleWindowCount']==observations['t14']['seen']['visibleWindowCount']==1
assert observations['t19']['seen']['visibleWindowCount']==2
assert 't20' not in observations
audit94=[r for r in rows(private/'turn-audit.jsonl') if str(r.get('request_id'))=='94']
assert any(r.get('final',{}).get('kind')=='conversation' and r['final']['effect_operations']==[] for r in audit94)
failures={
 'focus-en':'English input classified mixed and answered in Spanish.',
 'reference-new-name-en':'And Spotify? unnecessarily asks what the user means instead of retaining the preceding window-status question.',
 'reference-pronoun-en':'Is it open now? loses the Spotify reference and produces an interpretation failure.',
 'reference-new-name-es':'Y Steam? produces another interpretation failure instead of a scoped read.',
 'reference-pronoun-es':'The Steam application reference is lost; unnecessary clarification also leaks exactly into Spanish.',
 'count-en':'The number matches the immediately preceding verified Spanish answer, but request94 is conversation/knowledge with no new typed observation. This does not demonstrate a current read; do not label the matching number fabricated or grant read coverage.',
}
judged=[{**c,'terminal':f,'observation':observations.get(f't{i}'),'verdict':'failed_or_unverified' if c['case_id'] in failures else 'correct','reason':failures.get(c['case_id'],'Preserves scope, observation and language.')}
    for i,(c,f) in enumerate(zip(panel,finals),1)]
write(private/'adjudication.json',judged)
report=['#640 — 14/20 acreditados; referencias e inglés pendientes']
for r in judged:report+=['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason'],json.dumps(r['observation'],ensure_ascii=False)]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Fuente638 adoptada — identidad empaquetada y conteo real

636 enlaza procesos empaquetados mediante el AUMID de Windows y distingue errores de consulta de ausencia.637 confirma Notepad abierto.638 conserva todos los handles visibles con área positiva y enfoca el handle seleccionado sin sustituirlo por la ventana más grande. Se retira LargestTopLevelWindow; no otra capa, modelo ni respuesta fija. Sólo C# y pruebas de su provider.

Validación638:513pass Providers,0omisiones agregadas y4opt-in impresas aparte;46pass integración/0omisiones;51focales, incluida una prueba Win32 que fallaba al perder una de dos ventanas. Fast exit0/Release11,89s. Full630 sigue como línea base anterior, no Full638 ni cierreC03.639:11/12 finales; los conteos coinciden con instantáneas Win32 idénticas antes/después. El estado Notepad había cambiado a cerrado antes de esa tanda; se registra el cambio sin atribuirlo a un actor.

640 amplía a20casos y acredita14. WhatsApp abierto se verifica correctamente por identidad empaquetada en ambos idiomas. La cantidad española de Steam se lee y responde2. Persisten cuatro fallos de seguimiento: And Spotify?, Is it open now?, Y Steam? y Esa aplicación… pierden el contexto; el último además incluye exactly. El foco inglés sigue clasificado mixed. La cantidad inglesa coincide con la lectura española anterior, pero request94 elige conversation/knowledge sin una nueva observación tipada: no se acusa una cifra inventada, pero tampoco se acredita una consulta actual. H0040 sigue abierto;25cubiertos/717abiertos/0NA.

Recursos640:3497,559MiB GPU/2412,738MiB RAM;85,828s, sin infracciones. No UI/voz conjunta.639:3497,559/1894,625MiB;77,313s incluyen NativeAOT. La variación de RAM depende de la sesión/carga; no se presenta como mínimo global. Fuente638 se adopta por las lecturas verificadas y pruebas dueñas; los defectos de contexto/idioma se conservan como pendientes de C03.
'''
seal(out,private,{'source':638,'correct':14,'total':20,'failed_or_unverified_cases':failures,
    'packaged_positive_es_en_correct':2,'spanish_count_read_correct':True,'english_count_new_read_verified':False,
    'resources':read(out/'resources.json'),'ui_or_voice_credit':False,'whole_window_requirement_accepted':False},
    note,['panel.json','capture/events.jsonl','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl','adjudication.json','RESULT.md','windows-before.json','windows-after.json'])
out=base/'astra-enumeration-source638';prereg=read(out/'PREREG.json');assert not (out/'RESULT.json').exists()
assert all(sha(root/p)==v for p,v in prereg['sources'].items())
for original,target in [('c03-enumeration638-fast.log','FAST.log'),('c03-enumeration638-integration.log','INTEGRATION.log')]:
    (out/target).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':True,'providers_passed':513,
    'providers_aggregate_skipped':0,'providers_printed_opt_in_omissions':4,'integration_passed':46,
    'integration_skipped':0,'targeted_passed':51,'native_test_red_before':True,'fast_exit':0,
    'release_seconds':11.89,'source_unchanged_during_product':True,'product639_correct':11,'product639_total':12,
    'product640_correct':14,'product640_total':20,'python_unchanged':True,'goal_complete':False,
    'survey':{'covered':25,'open':717,'not_applicable':0}})
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as f:f.write('/artifacts/comprobaciones/C03/astra-enumeration-source638/** -text\n')
state=read(base/'RELEVO_ACTIVO.json');state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='638 adoptada:513Providers/46integración/51focales+Fast.63911/12;64014/20, referencias/idioma/lectura inglesa pendientes.25/717/0.',
    continuation='Publicar635–640. Después conservar consultas explícitas de cantidad (How many windows of Steam are open? devuelve knowledge94) y localizar primera pérdida de referencias15–18 en640. Foco inglés: read_request trata has como exclusivamenteES. No parchear prosa fija. No procesos activos; UI/voz/recuperación yFullfinal pendientes.',
    publishedSourceCommit='pending_publication_of_validated_source638',previousGoalTurnClassification='progress')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text('# Handoff C03 — fuente638 validada, publicación pendiente\n\n'+note+'\nSiguiente: publicar635–640 y actualizar matriz. Luego inspeccionar turn-audit640 y shell-trace de t15–t20 antes de editar Python. El foco inglés se reproduce con read_request(Which window has focus?)=mixed,evidence(1,2); has está sólo en _ES_WORDS. Revisar también auxiliares españoles, mezcla y contexto para no arreglar una frase rompiendo otra.\n',encoding='utf-8',newline='\n')
print({'adopted_source':638,'product640_correct':14,'total':20,'survey_unchanged':True})
