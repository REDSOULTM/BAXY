"""Bind the progress language repair after the native metadata comparison."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-progress-language625';private=home/'C03-progress-language625-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl');assert len(panel)==len(responses)==24
judged=[]
for r in responses:
    case=panel[r['case_id'],r['arm']];choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop'
    judged.append({**r,'criterion':case['criterion'],
                   'language_metanarration':(r['case_id'],r['arm'])==('mixed:understanding','original'),
                   'remaining_third_person':r['case_id'] in {'es:understanding','mixed:understanding'},
                   'note':'Phase and supplied step count preserved. This partial repair does not certify final naturalness of the progress route.'})
for r in judged:
    if r['case_id'].startswith('mixed:') or r['arm']!='original': continue
    control=next(other for other in judged if other['case_id']==r['case_id'] and other['arm']=='language-only')
    assert r['response']['choices'][0]['message']['content']==control['response']['choices'][0]['message']['content']
write(private/'adjudication.json',judged)
report=['# Progreso625: se retira metanarración de idioma; naturalidad aún parcial']
for r in judged:
    report+=['## '+r['case_id']+' · '+r['arm'],r['response']['choices'][0]['message']['content'],
             'Metanarración de idioma='+str(r['language_metanarration'])+'; tercera persona pendiente='+str(r['remaining_third_person'])]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Progreso625: reparación parcial de metadatos de idioma

24 respuestas, cuatro fases en ES/EN/mixed por dos brazos. Sustituir sólo la política mixed larga por el contrato español existente elimina la narración de análisis de idiomas en understanding. Las ocho parejas ES/EN son controles idénticos, incluidas sus salidas; las cuatro fases mixtas conservan actividad y pasos. No se incorporan el pedido original ni resultados futuros.

No se afirma que todo el panel de prosa esté resuelto: understanding aún habla de «la solicitud del usuario» y quedan formulaciones de progreso por mejorar. Se califica únicamente retirar metadatos conversacionales irrelevantes del narrador de progreso, sin nueva regresión observada.626 lo integra con pruebas de reintento, fases/pasos, petición explícita en inglés y conservación de la política mixed fuera de progreso. La encuesta permanece25/717/0 y no hay crédito de UI/voz.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'responses':24,'all_finish_stop':True,
                 'unchanged_es_en_pairs':8,'mixed_phases':4,'language_metanarration_original':1,'language_metanarration_candidate':0,
                 'whole_progress_route_accepted':False,'resources':read(out/'RESOURCES.json')},
     note,['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
llm_sha=sha(root/'src/baxy_mind/llm.py')
old_llm='d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425'
pin=root/'tests/test_price_v8_veto_damage_by_cause.py';data=pin.read_bytes()
assert data.count(old_llm.encode())==1;pin.write_bytes(data.replace(old_llm.encode(),llm_sha.encode()))
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for relative in sorted(files): digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree_sha=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    pin=root/'experiments/stt_quality'/name;data=pin.read_bytes()
    old=b'37cfd94ffc5a02acdd401a33e9ffac1a6d850d2e10cb0b40490c7dc162f39c84'
    assert data.count(old)==1;pin.write_bytes(data.replace(old,tree_sha.encode()))
out=base/'astra-progress-source626';out.mkdir(exist_ok=False)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
    'method':'Only mixed-language progress selects the existing Spanish output policy. RequestReading continues to honor explicit English; other conversational prose retains the complete mixed policy. No phase, addressee, model, sampling, catalog, visible response or retry limit changed. Current source pins resealed; consumed STT/V8 evidence untouched.',
    'native_evidence':'625 removes language metanarration with phases/step counts intact; other progress naturalness defects retained.',
    'source_llm_sha256':llm_sha,'python_tree_sha256':tree_sha,'python_files':len(files),
    'criteria':'Owner tests and Fast green, product627 on registered source with35 finals and actual progress events. No new final or phase regressions. Not C03 completion or UI/voice qualification.',
    'survey':{'covered':25,'open':717,'not_applicable':0}})
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='625 retira metanarración mixed;626 candidato en llm.py/tests/pins. Test focal200pass; dueñas/Fast/producto627 pendientes.25/717/0.',
             continuation='Recoger dueñas626 y Fast; NO lanzar producto mientras compila. Después627 Qwen registrado35finales y boot_stage de progreso. Adjudicar y publicar fuente sólo si validación y regresión pasan. UI/voz/717requisitos y naturalidad pendiente no se dan por cerrados.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nFuente626 candidata modifica sólo selección de idioma para progreso mixed; nueve pruebas nuevas y adaptación del contrato de progreso mixed existente. Focal200pass. Pines actuales V8/STT actualizados, no campañas históricas. Falta dueñas ampliadas/Fast/producto627, en ese orden antes de publicar.622–625 ya sellados; fuente606 sigue siendo la publicada hasta adoptar626.\n',encoding='utf-8',newline='\n')
print({'llm_sha256':llm_sha,'tree_sha256':tree_sha,'files':len(files)})
