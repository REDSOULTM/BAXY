from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-introduction-context428'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-introduction-context428-private'
rows=[json.loads(l) for l in (out/'replies.jsonl').open(encoding='utf-8')]
report='''# 428 — estado session_context_only: sólo2/4útiles, no adoptar

Baseline426T5 igualado offline y live. Cuatro nombres, misma composición/modelo.
Sustituir hechos de cuentaWindows por status/session_context_only recupera los
dos saludos ES, pero en EN dice «I have completed the session context» o «the
session context has been completed»: no es una respuesta natural/veraz al acto.
Baseline0/4útiles (3vacíos y1lecturaWindows no pedida); variante2/4. No fuente.
10,781s,GPU3173,56MiB/RAM1101,96MiB,sinviolaciones,manifiesto intacto.

El estado success/status representa una tarea completada, no el acto de
presentarse.429 compara ese mismo estado con el evento de conversación ya
existente, sin causa de tarea: TurnVisibleFacts.Event("conversation") y su
intención conversation. No nuevo prompt ni plantilla ni datos de nombre añadidos.
Cambio conceptual único: el recorrido de composición acorde al acto conversacional.
Mantener la propuesta de parser sólo como hipótesis hasta que prosa y límites pasen.
Datos privados originales intactos. Modelos cerrados; C03 sigue abierto.
'''
for r in rows:
    answer=r.get('answer','')
    if r['variant']=='baseline' and answer:answer='[saludo seguido de cuenta Windows no solicitada; literal conservado en registro privado]'
    report+=f"\n- {r['variant']} | {r['request']} | {answer or '[vacío]'}\n"
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','RESULT.md','resources.json','replies.jsonl','command.json']]+[private/'posts.jsonl']
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
source=(root/'scratchpad/c03-introduction-context428.py').read_text(encoding='utf-8').replace('428','429')
# Preserve captured426 data only as inherited input; compare the prior status
# route with the existing conversation route, no longer Windows facts.
start=source.index('def facts(case, variant):');end=source.index('\n\nfor key in',start)
source=source[:start]+'''def facts(case, variant):
    situation = {'kind':'status','polarity':'success','cause':'session_context_only'} if variant=='baseline' else {
        'kind':'conversation','polarity':'success'}
    return {'situation':json.dumps(situation,ensure_ascii=False)}
''' +source[end:]
# Actual428 baseline post becomes the equality reference for the first case.
needle="\ndef sha(path):"
insertion='''
prior_posts=[json.loads(l) for l in (private.parent/'C03-introduction-context428-private/posts.jsonl').open(encoding='utf-8')]
for case in cases:
    if case['id']=='actual426-t5':
        case['reference']=next(p['payload'] for p in prior_posts if p['id']==case['id'] and p['variant']=='session-context')
    else:
        case.pop('reference',None)
'''
source=source.replace(needle,insertion+needle)
source=source.replace("answer = client.compose_user_message(case['request'], 'status', facts(case, variant))", "answer = client.compose_user_message(case['request'], 'status' if variant=='baseline' else 'conversation', facts(case, variant))")
source=source.replace('wrong426 Windows-account facts vs existing session_context_only status','existing428 session_context_only status vs existing conversation event/intent')
source=source.replace('Actual baseline must equal captured426 payload offline and live. Only situation changes;', 'Actual baseline must equal captured428 status payload offline and live. One conceptual change: existing conversation event and intent replaces task-status event and intent;')
source=source.replace("['baseline', 'session-context']","['baseline', 'conversation']")
source=source.replace('before implementation. No product effects', 'before implementation.428status only2/4useful, no adoption; this tests correct conversational route. No product effects')
target=root/'scratchpad/c03-introduction-conversation429.py';assert not target.exists();compile(source,str(target),'exec');target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8').replace('428preparado','4282/4noadoptado;429preparado').replace('scratchpad/c03-introduction-context428.py','scratchpad/c03-introduction-conversation429.py')
    text+='''
428statussession_context_only:0/4→2/4;EN«completedthesessioncontext»malo.
No fuente.429compara estado428 exacto vs evento/intent conversation yaexistente,
sin cause de tarea, cuatro mismos nombres. No nuevoprompt/plantilla/cache.
''';p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='428 status route only2/4 useful, EN technical completed-session prose; not adopted.',continuation='Run429 existing conversation event/intent against428 exact status; same4names. No source until meaningful result and parser boundary tests.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('428 recorded;429 prepared')
