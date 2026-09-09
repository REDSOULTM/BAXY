"""Keep template failures separate from native model and instruction-layer quality."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-ministral622';private=home/'C03-ministral622-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl');assert len(responses)==40 and len(panel)==52
judged=[]
for r in responses:
    case=panel[r['case_id'],r['arm']];choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop'
    raw=json.loads(choice['message']['content'])
    count='zero' if raw['request_type'] in {'stable_conversation','social_conversation'} else raw['effect_count']
    judged.append({**r,'text':case['text'],'expected_type':case['expected_type'],'expected_count':case['expected_count'],
                   'normalized_correct':raw['request_type']==case['expected_type'] and count==case['expected_count']})
write(private/'adjudication.json',judged)
report=['# Ministral622: cuarenta clasificaciones y una avería de formato']
for r in judged:
    report+=['## '+r['case_id']+' · '+r['arm'],r['text'],r['response']['choices'][0]['message']['content'],
             'Esperado: '+r['expected_type']+'/'+r['expected_count']+'; correcto normalizado='+str(r['normalized_correct'])]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores=Counter(r['arm'] for r in judged if r['normalized_correct'])
note622='''# Ministral622: clasificación insuficiente y formato incompatible

Ministral3-3B-Instruct2512 Q4 heredado, hash verificado9ed150d4; backendb10809, perfilT0,05/p0,95/k0/min0/repetición neutra. La ficha oficial recomiendaT<0,1; no se presenta el resto del perfil como óptimo. Se consultaron la ficha GGUF y el informe técnico2601.08584, además de los rechazos previos de coste y aritmética. Los52 casos previstos no se completaron:40 respuestas de clasificación, luegoHTTP500 en la primera prosa y11sin intentar.

Guardia original14/20 y subtipo11/20 normalizados. Se conservan errores de completitud, cardinalidad y lecturas actuales; el subtipo no se adopta. El HTTP500 se debe a la plantilla Jinja: el historial como datos ocupa un mensaje user y la petición otro user consecutivo. Es un error de serialización anterior al decode, no una respuesta incorrecta del modelo.

623 conserva todos los textos y roles al unir sólo user consecutivos; no borra historial ni inventa una respuesta intermedia. Esta avería y las40 clasificaciones quedan separadas. Ningún cambio de fuente/registro/cobertura:25/717/0.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'planned_calls':52,'completed_calls':40,
                 'failed_http_calls':1,'unattempted_calls':11,'normalized_correct_by_arm':dict(scores),
                 'failure':'Jinja rejects consecutive user roles before first prose decode',
                 'resources':read(out/'RESOURCES.json'),'source_adopted':False},note622,
     ['panel.json','requests.jsonl','responses.jsonl','server.log','adjudication.json','RESULT.md'])

failures623={
    'H0012':'Unrelated vulgar fictional response; does not identify BAXY.',
    'noisy-en':'Spanish response to English identity question.',
    'vocative-es':'Fictional powerful persona rather than natural grounded greeting.',
    'vocative-en':'Spanish reply to English greeting.',
    'user-name-en':'Spanish greeting/mixed embellishment despite English request.',
    'H0218':'Treats gratitude as a fresh greeting and asks whether the user is leaving.',
    'thanks-es':'Unrequested English spirit decoration in Spanish acknowledgement.',
    'thanks-en':'Spanish acknowledgement to English gratitude.',
}
failures624={
    ('H0012','native'):'Adds an irrelevant football interpretation of a colloquial identity question.',
    ('noisy-en','native'):'Invents Le Chat deployment/tool context and refers to tools the user never mentioned.',
    ('plain-es','native'):'Claims Le Chat interface and tool capability not supplied in this native session.',
    ('thanks-en','native'):'Publishes unresolved template token {today}.',
}
for number,name,failures in [(623,'ministral-roles623',failures623),(624,'ministral-layers624',failures624)]:
    out=base/('astra-'+name);private=home/('C03-'+name+'-private')
    assert not (out/'RESULT.json').exists()
    panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
    responses=rows(private/'responses.jsonl');assert len(responses)==len(panel)==(12 if number==623 else 24)
    judged=[]
    for r in responses:
        case=panel[r['case_id'],r['arm']];choice=r['response']['choices'][0]
        failure=failures.get(r['case_id'] if number==623 else (r['case_id'],r['arm']))
        if number==624 and r['arm']=='identity-only':
            failure='Product identity alone induces fictional embodied/cyberpunk persona, language drift or invented facts; incompatible with the grounded product.'
        if choice['finish_reason']!='stop':
            failure='Token budget exhausted in a repetitive fictional reply; retain as truncation failure.'
        judged.append({**r,'text':case['text'],'verdict':'failed' if failure else 'correct',
                       'reason':failure or 'Meets the task, subject and language criterion; native verbosity is retained and is not a product qualification.'})
    write(private/'adjudication.json',judged)
    report=[f'# Ministral{number}: diagnóstico de capas, sin adopción']
    for r in judged:
        report+=['## '+r['case_id']+' · '+r['arm'],r['text'],r['response']['choices'][0]['message']['content'],r['verdict']+': '+r['reason']]
    (private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    scores={arm:sum(r['verdict']=='correct' for r in judged if r['arm']==arm) for arm in sorted({r['arm'] for r in judged})}
    note=(f'# Ministral{number}: formato resuelto, calidad insuficiente\n\n'
          '623 une los mensajes user consecutivos conservando todo el texto:12/12 HTTP completados y stop, pero sólo4/12 respuestas adecuadas. '
          '624 aísla usuario nativo frente a una frase de identidad:8/12 frente0/12. El brazo nativo ya inventa contexto de herramientas/interfaz y deja una plantilla sin resolver; al añadir la identidad del compañero de PC aparece una persona ficticia con cuerpo y hechos inventados. '
          'Una de24 salidas624 agota512tokens; no se amplía el presupuesto para disimular repetición. Las políticas completas623 reducen la ficción, pero no solucionan los idiomas ni la respuesta a lo pedido.\n\n'
          'No se adopta Ministral, la serialización experimental ni otra variante del prompt de identidad. No se afirma inferioridad universal: es un fallo de estos papeles con el perfil declarado. Se preservan costes, versión y todos los borradores. Fuente606/registro intactos;25/717/0.\n')
    seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'correct_by_arm':scores,'calls':len(responses),
                     'cuts':sum(r['response']['choices'][0]['finish_reason']!='stop' for r in judged),
                     'resources':read(out/'RESOURCES.json'),'source_adopted':False},note,
         ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
    print(number,scores)
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='622–624 sellados: Ministral no cualificado; formato user consecutivos aislado, después fallos nativos/de identidad. Fuente606 y25/717/0 intactos.',
             continuation='Recoger625 sesión3742 TEMP/c03-progress-language625.log: metadatos de política mixed retirados sólo del progreso, mismas fases/controles565. No repetir variante de destinatario565 ni prompts de identidad619. Adjudicar24; guardar/push esta tanda.',
             previousGoalTurnClassification='progress',publishedEvidenceCommit='f0dcd98f87b588665d8397f45bd3bdb8a172e051',pendingOwnerClarification=None)
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text('''# C03 — fuente606, diagnóstico622–625

La tanda anterior fue progreso: evidencia612–621 publicada en f0dcd98f, HEAD=origin comprobado y main intacto. Fuente619 rechazada/restaurada exactamente; Full606 sigue ligado a esa fuente. Encuesta25/717/0,742/rev1248 conservada. Ninguna decisión pendiente del dueño.

622–624 ya terminaron y se sellaron: Ministral original14/20 y subtipo11/20 en guardia; error de serialización user-user reparado sólo para diagnóstico623; prosa4/12.624 usuario nativo8/12, identidad mínima0/12 con1corte. No promoción ni fuente modificada. Rechazos completos, no omitirlos para probar otro prompt.

Activo625 sesión3742, TEMP/c03-progress-language625.log. Veinticuatro respuestas de12casos: ES/EN y mixed por cuatro fases. Sólo se cambia la política mixed larga por la política española existente en avisos de progreso; nombres de fase, pasos, identidad, sampler y payloads restantes intactos. Motivación:605 publica análisis interno del idioma en boot_stage.label.565 ya descartó reformular el destinatario; no repetir. Recoger625 y adjudicar antes de cualquier código. Publicación de622–625 pendiente. UI/voz, cobertura717, error/restauración, recursos conjuntos y Full final siguen abiertos.
''',encoding='utf-8',newline='\n')
with (base/'INVESTIGACION_MODELO_C03.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Ministral622–624\n\nSe reconsultaron2026-09-09 la ficha oficial https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF y el informe https://arxiv.org/abs/2601.08584. PerfilT0,05/p0,95/k0/min0, sin penalización: sóloT<0,1 se atribuye a la recomendación oficial. Guard62214/20 y11/20; luego Jinja500 por user-user.623 conserva los contenidos unidos:4/12prosa.624 localiza ficción al introducir identidad: nativo8/12, identidad0/12,1corte. No promoción ni nueva ronda de prompts. Costes y salidas íntegras en artefactos privados sellados; no se borra el rechazo previo por coste.\n')
