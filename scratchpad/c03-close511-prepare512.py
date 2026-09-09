"""Freeze the successful diagnostic before implementing its bounded ownership."""
from datetime import datetime,timezone
import collections,hashlib,json,os,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-audio-mind511';campaign=base/'astra-chat-history-greedy511'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio-mind511-private'
effective=[json.loads(s) for s in (private/'effective-chat-profile.jsonl').open(encoding='utf-8-sig')]
old=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio-mind510-private'
control={r['case']:r for r in map(json.loads,(old/'effective-chat-profile.jsonl').open(encoding='utf-8-sig')) if r['profile']['quote_history']}
assert len(effective)==22 and len({r['case'] for r in effective})==22
for r in effective:
 before=control[r['case'].replace('greedy_quoted','quoted_history')]['after'];after=r['after']
 assert {k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}=={'temperature'}
 assert before['temperature']==.7 and after['temperature']==0
rows=[json.loads(s) for s in (out/'replies.jsonl').open(encoding='utf-8-sig')]
assert len(rows)==22
for r in rows:
 assert not r['reply']['effectOperations'] and r['reply'].get('reply')
 r['useful']=True
 r['reason']='Useful faithful conversation, correct speaker and human correction; assistant-reference names Morgan only as previous assistant words. Definitions cover valid senses without claiming observed effects. No internal aside/visible metadata or truncation.'
res=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert res['completed'] and res['manifest_unchanged'] and not res['violations']
responses=[json.loads(s)['response'] for s in (private/'http-posts.jsonl').open(encoding='utf-8-sig') if json.loads(s)['stage']=='response']
assert all(c.get('finish_reason')=='stop' for r in responses for c in r.get('choices',[]))
write(out/'ADJUDICATION.json',rows)
write(campaign/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':48490,'exit':0,'useful':22,'total':22,'same_payload_except_temperature_pairs':22,'http_responses':len(responses),'finish_reason':'all stop','max_completion_tokens':max(r.get('usage',{}).get('completion_tokens',0) for r in responses),'resources':res,'decision':'Implement quoted evidence for direct knowledge presentation, including its existing repair path, with exact provenance rule. Keep original history for semantic reading, audits, topic scoping and other presentation shapes. Production turn already usesT0; validate its actual registered pipeline rather than silently promoting private sampler fields. No model/runtime promotion.'})
(campaign/'RESULT.md').write_text('''# Historial citado: perfil comprobado

22/22 respuestas útiles,11casos porsemilla0/17. RecuperaJordan humano frente aMorgan del asistente, respetaCasey corregido yOlivia, y conservaMorgan como respuesta cuando se pregunta qué dijoBAXY. No aparece el aparte de autocorrección de510. Se comprobaron22pares de payloads: sólo cambia temperatura0,7→0; mismo contenido, roles citados, reglas, otros parámetros y límite de salida.73respuestasHTTPstop;máximo85tokens de salida.

RAM1766,328MiB/GPU3497,559MiB;63,984s;manifiesto intacto;sesión48490exit0. Prueba privada de mente, sin efectos/UI/voz ni aceptación.512 incorporará la representación a la presentación de conocimiento y su reparación, conservando historial original para lectores y auditorías y otras formas de conversación. La ruta de turno ya usaT0; el protocolo real debe validar el registro actual sin promover campos privados de sampling.

Errata de herencia510: previous_dialogue_for_references_only es una clave de datos usada por el contador semántico (llm.py7171 en fuente506), no una función llamada _dialogue_for_references_only. La hipótesis y los payloads ejecutados no dependen de ese nombre.
''',encoding='utf-8')
for folder in [out,campaign]:write(folder/'PINS.json',{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='PINS.json'})
nextout=base/'astra-knowledge-history512';nextout.mkdir(exist_ok=False)
private512=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-knowledge-history512-private';private512.mkdir(exist_ok=False)
files=['src/baxy_mind/llm.py','tests/test_turn_policy.py']
for f in files:shutil.copy2(root/f,private512/Path(f).name)
write(nextout/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source_before':{f:sha(root/f) for f in files},'private':str(private512),'method':'Reuse existing chat presentation/repair; direct knowledge only, quote its already scoped prior messages as JSON data preserving all literals/roles/order, current user request unchanged. Add the exact511 provenance rule to the knowledge system, and preserve the same data/authority during repair. Do not alter semantic readers, stored history, audits, other presentation shapes, model or runtime. No extra decoder or name-specific extraction. Update owner tests to require literal roundtrip and topic/shape isolation; focal baseline, owners andFast then real protocol.','criteria':'Every user/assistant word survives where relevant; no metadata is published or grants effect authority. Repair cannot restore wrong role-based self-conditioning or excluded topics. Source matches511 knowledge payload and current registeredT0 is verified in actual mind before claiming quality.'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n511 cerrado48490exit0:22/22útiles,22parespayloads sóloT cambia,73stop/máximo85tokens. RAM1766,328/GPU3497,559MiB63,984s.512PREREG/copiasprivadas listos, sin fuente editada aún: conocimiento directo cita historial yaacotado yreparaciónlo conserva; otrasformas/lectores/auditoría mantienendialogooriginal. T0yaesla rutaactual; no promociónprivada. Baseline focalantesdefuente,owners+Fast,protocolo después. Sin procesos activos.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='511 cerrado22/22;fuente506aúnvigente;sinprocesosactivos.',continuation='512implementarhistorialcitadosóloconocimientoyreparación,conservandoownership;C03activo.');write(base/'RELEVO_ACTIVO.json',r)
print('511 closed22/22;512 preregistered/backed up, no source edits yet.')
