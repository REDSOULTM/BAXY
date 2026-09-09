"""Seal the paired style probe and bind current source pins for its regression."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-style618'
private=home/'C03-style618-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl')
assert len(panel)==len(responses)==24
adjudication=[]
for r in responses:
    case=panel[r['case_id'],r['arm']];choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop' and not choice['message'].get('reasoning_content')
    failed=(r['case_id'],r['arm'])==('H0218','original')
    adjudication.append({**r,'text':case['text'],'criterion':case['criterion'],
                         'verdict':'failed' if failed else 'correct',
                         'reason':'Addresses user as tuteo.' if failed else 'Natural answer preserves identity, subject and language.'})
write(private/'adjudication.json',adjudication)
report=['# Estilo618: 11/12 original;12/12 explícito']
for r in adjudication:
    report += ['## '+r['case_id']+' · '+r['arm'],r['text'],r['response']['choices'][0]['message']['content'],r['verdict']+': '+r['reason']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Estilo618: instrucción explícita calificada para integración

Cambiar «Eres un él. Tuteas.» por «Habla de ti en masculino y dirígete al usuario de tú.» corrige el apelativo tuteo en H0218. Ocho controles de identidad/sujeto y tres variantes de gratitud ES/EN/mixta se mantienen:11/12→12/12,24stop sin razonamiento. No se añade una respuesta fija ni un filtro de palabras. La variante mixta conserva política española, permitida por identidad.

La primera preparación del script falló antes de guardar panel o iniciar inferencia: suponía JSON para el usuario social, que es texto directo. Se inspeccionó payload76 y corrigió el constructor; no se descartó ninguna generación ni se reusó una corrida. Fuente619 cambia sólo SYSTEM_PROMPT de conversación; la instrucción de compositor es otra ruta sin cambio. Debe pasar dueñas, Fast y regresiones de producto con Gemma620 y Qwen registrado621 antes de adoptarse. No arregla H0032 ni acredita nueva cobertura25/717/0.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'per_arm':12,'correct_by_arm':{'original':11,'explicit-style':12},
                 'resources':read(out/'RESOURCES.json'),'source_adoption_pending':True},
     note,['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])

llm_sha=sha(root/'src/baxy_mind/llm.py')
old_llm='d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425'
pin=root/'tests/test_price_v8_veto_damage_by_cause.py'
data=pin.read_bytes();assert data.count(old_llm.encode())==1
pin.write_bytes(data.replace(old_llm.encode(),llm_sha.encode()))
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for relative in sorted(files):
    digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree_sha=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    pin=root/'experiments/stt_quality'/name;data=pin.read_bytes()
    old=b'37cfd94ffc5a02acdd401a33e9ffac1a6d850d2e10cb0b40490c7dc162f39c84'
    assert data.count(old)==1;pin.write_bytes(data.replace(old,tree_sha.encode()))
out=base/'astra-style-source619';out.mkdir(exist_ok=False)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Single general conversation style clarification qualified618. No runtime, model, classifier, composer, output filters or response literals changed. Update only current V8/STT expected-source pins, consumed evidence untouched.',
                        'source_llm_sha256':llm_sha,'python_tree_sha256':tree_sha,'python_files':len(files),
                        'acceptance':'Owner pytest turn_policy, price_v8 and STT evaluator suites, Fast gate, actual product620 Gemma same profile614 and621 registered Qwen. Preserve every prior failure; no source adoption if new product regressions.',
                        'survey':{'covered':25,'open':717,'not_applicable':0}})
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='618 mejora11/12→12/12; fuente619 candidata cambia instrucción de trato, sin adopción aún. Dueñas/Fast/producto pendientes;25/717/0.',
             continuation='Validar619 dueñas+Fast; producto620 Gemma perfil614 y621 Qwen registrado. Sellar resultados y publicar fuente sólo si no regresiones. Subtipo social615–617 descartado; H0032 sigue abierto en Gemma.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nFuente candidata619 en llm.py y tres pins vigentes. Falta dueñas/Fast y producto620/621. No repetir Full por este cambio sólo Python; Full606 histórico verde, Full final pendiente. Publicar evidencia612–618 y fuente619 si se valida.\n',encoding='utf-8',newline='\n')
print({'llm_sha256':llm_sha,'tree_sha256':tree_sha,'files':len(files)})
