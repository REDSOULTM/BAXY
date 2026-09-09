"""Record the partial causal improvement without claiming the panel is green."""
from datetime import datetime, timezone
import hashlib,json,os,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-chat-draft505'
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={}
for mode,session in [('baseline',32599),('generation',48471)]:
 folder=base/('astra-audio-mind505-'+mode)
 rows=[json.loads(s) for s in (folder/'replies.jsonl').read_text(encoding='utf-8-sig').splitlines()]
 assert len(rows)==7 and all(not r['reply'].get('effectOperations') for r in rows)
 rejected={'definition-es','recall-en'} | ({'name-en'} if mode=='baseline' else set())
 for row in rows:
  row['useful']=row['id'] not in rejected
  row['adjudication']=({'definition-es':'Baseline: internal selector wording and unsolicited capability offer. Generation: internal wording gone, but inverted social-mute explanation remains factually wrong.', 'recall-en':'Repeats assistant-authored Morgan over user-authored Jordan; no initial_reply in either mode.', 'name-en':'Baseline assigns the human name to the assistant; generation correctly says Your name is Jordan.'}.get(row['id'],'Useful correct response with appropriate language; RAM explanation longer than requested but factual.'))
 resources=json.loads((folder/'RESOURCES.json').read_text(encoding='utf-8-sig'))
 assert resources['completed'] and resources['manifest_unchanged'] and not resources['violations']
 write(folder/'ADJUDICATION.json',rows)
 result[mode]={'session':session,'exit':0,'useful':sum(r['useful'] for r in rows),'total':7,'resources':resources}
 write(folder/'PINS.json',{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='PINS.json'})
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'comparison':result,'decision':'Adopt removal of native selector prose reuse as a responsibility correction; not a green quality panel. Definition factuality and assistant-over-user recall remain open. No sampler/backend/model change or promotion.'})
(out/'RESULT.md').write_text('''# Borrador del selector frente a conversación

Dos procesos nuevos con los mismos siete casos ya consumidos, catálogo y perfil registrado. Sólo el hook privado suprime initial_reply en el tratamiento. Baseline4/7 útiles; generación5/7. La fuente no se editó durante las dos corridas.

La prosa interna desaparece y el nombre inglés pasa de My name is Jordan a Your name is Jordan. La definición aún añade una inversión incorrecta sobre quién escucha al silenciar; no se aprueba. El recuerdo inglés sigue repitiendo Morgan, escrito por el asistente, por encima de Jordan, escrito por el usuario. Ese caso nunca tenía initial_reply: es otra frontera, no una regresión del tratamiento. Los demás controles se conservan.

22 peticiones HTTP frente a26: se añaden cuatro generaciones con identidad/política/idioma reales de conversación. En la definición, HTTP4 del tratamiento contiene esos tres sistemas y ninguna herramienta, con T0/seed0/max256. La latencia de ese turno pasa3,562→4,641s; nombre inglés1,797→2,063s. No se infiere una mejora de velocidad del total44,422→44,016s, dominado por otros pasos. RAM1768,617→1778,184MiB; GPU3497,559MiB ambos. Manifiesto intacto.

Se adopta retirar el transporte redundante de prosa desde el selector, sin sustituirlo por plantillas visibles ni un filtro de palabras. La generación existente sigue siendo dueña de la respuesta. Herencia: tests/test_turn_policy.py418–481 documentaban el ahorro y las guardas;505 conserva esos controles. Qwen documenta la selección con instrucciones y plantilla propias (https://qwen.readthedocs.io/en/stable/framework/function_call.html); esto no acredita su prosa interna como respuesta de BAXY. El hallazgo causal local es el salto del payload correcto mediante initial_reply. No se atribuye incapacidad general a ningún modelo.

506 retirará la ruta sin mantener parámetros/propagación muertos; pruebas dueñas y Fast antes de volver al producto. C03 sigue íntegramente activo; esta prueba no es UI, audio físico ni aceptación.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
nextout=base/'astra-chat-owner506';nextout.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-chat-owner506-private';private.mkdir(exist_ok=False)
files=['src/baxy_mind/llm.py','src/baxy_mind/__main__.py','tests/test_turn_policy.py']
for name in files:shutil.copy2(root/name,private/Path(name).name)
write(nextout/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source_before':{name:sha(root/name) for name in files},'private':str(private),'method':'Remove the selector conversation_reply propagation and chat initial_reply bypass entirely; preserve existing generation, speculative chat, identity, history, observation/language guards and repairs. Adapt the native and chat owner tests to this responsibility, then run seven owners and Fast. No new prompt/model or fixed response.505 still has two open quality failures.'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name
 s=p.read_text(encoding='utf-8-sig')
 start=s.index('Siguiente505:');end=s.index('\nCambios previos',start)
 s=s[:start]+'''505 cerrado; sesiones32599/48471 recogidas exit0. Sin procesos activos. Mismo panel7 y sólo initial_reply suprimido:4/7→5/7 útiles,22→26HTTP. Corrige voz interna y actor de nombre inglés; definición sigue con hecho falso y recall-en sigueMorgan(de asistente) sobreJordan(de usuario), este último sin initial_reply antes/después. RAM1768,617→1778,184/GPU3497,559MiB. No aceptación ni promoción. RESULT/ADJ/PINS completos.

Siguiente506, PREREG y copias privadas preparados: retirar conversación del selector/propagación en decide_turn/__main__ y parámetro/atajo initial_reply en chat; sustituye la ruta existente, no añade capas ni prompts. Actualizar tests dueños de esa responsabilidad manteniendo guardas/escoping de historial. Ejecutar baseline de tests antes de fuente, siete owners yFast. No editar fuente durante prueba/build/runtime. Después medir actualmind y abordar definición/recall aún abiertos.
''' + s[end:]
 p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='505 cerrado,4/7→5/7; sin procesos. Fuente503 aún vigente.',continuation='506 retirar el bypass de conversación y validarlo; definición y recuerdo siguen abiertos. C03 activo.')
write(base/'RELEVO_ACTIVO.json',r)
print('505 closed honestly;506 prepared with before hashes/copies, no source edited.')
