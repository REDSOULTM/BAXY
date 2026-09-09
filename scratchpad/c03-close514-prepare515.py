"""Close real private memory evidence; isolate irrelevant metadata at the writer."""
from datetime import datetime,timezone
import ast,hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-private-product514';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product514-private'
events=[json.loads(s) for s in (private/'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals=[r for r in events if r['type']=='terminal'];assert len(terminals)==8
activities=[r['event']['entry'] for r in events if r['type']=='event' and r['event'].get('type')=='activity']
for i,r in enumerate(terminals,1):
 r['turn']=i;r['useful']=i!=2
 r['reason']='Verified enable/save effects, but final prose repeats internal corrected/system-state metadata; not an acceptable public explanation.' if i==2 else 'Useful truthful confirmation, clarification, memory recall or conversational name. T1 names pending local memory and asks confirm/cancel; remembering the just-declared name is not a claim of durable save.'
progress=[r['event'] for r in events if r['type']=='event' and r['event'].get('type')=='boot_stage' and r['event'].get('label')]
exit_record=json.loads((out/'EXIT.json').read_text(encoding='utf-8-sig'));resources=json.loads((out/'resources.json').read_text(encoding='utf-8-sig'))
assert exit_record['exitCode']==0 and exit_record['manifest_unchanged'] and not resources['violations']
store=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-profile514/memory-store'
write(out/'ADJUDICATION.json',{'terminals':terminals,'activities':activities,'progress':progress})
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':39353,'exit':0,'useful_finals':7,'total_finals':8,'independent_progress_failure':'Label addresses the request as belonging to the user and says results have not been obtained; actual progress payload only proves work in progress, not absence of underlying results. Inspect the progress instruction separately, not as a failed name recall.','resources':resources,'manifest_unchanged':True,'isolated_store_files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in store.iterdir() if p.is_file()},'limits':'Actual C# shell/viewmodel/core and isolated persistence through hidden conductor. Stored Jordan/current conversationalÁlvaro are distinguished. No visible UI, physical voice or restart acceptance. Do not invent a retention disclosure requirement in the middle of this panel: T1 fulfils its preregistered decision/target criterion.'})
(out/'RESULT.md').write_text('''# Producto real: memoria y confirmación en perfil aislado

7/8 finales útiles. La confirmación nombra la memoria privada local pendiente y ofrececonfirm/cancel; no demuestra un guardado prematuro al reconocer el nombre recién declarado. Trasconfirmar se habilita la memoria y se guarda el dato sintético; las lecturasES/EN devuelvenJordan y la conversación conservaÁlvaro. El perfil del dueño no se utiliza. Hay ficheros cifrados del almacén aislado, preservados y con huellas; no se afirma todavía una prueba de reinicio.

El segundo turno falla en presentación: Memory saved successfully. No corrections made. System state updated to "memory updated". HTTP4 recibe saved=true junto a corrected=false/sensitive=false/replayed=false y el estado redundante memory updated. HTTP3 también narra configuración. El próximo diagnóstico515 conservará los hechos y guardas originales, pero quitará sólo metadatos redundantes de la vista enviada al modelo para esos éxitos privados. Se añade un control real de deshabilitación para garantizar que enabled=false nunca desaparezca.

Progreso se revisa aparte: HTTP12 recibe state=reviewing the person's request, mientras su sistema afirma que los resultados aún no están disponibles. El label público habla de la solicitud del usuario y repite esa ausencia. La falta de resultados en el payload no acredita su ausencia en el producto. Es otra frontera; no se modifica junto con515.

Sesión39353exit0;28,093s;RAM1803,270MiB/GPU3497,559MiB,sinviolaciones y registrointacto. Es la carga alcanzada por el conductor, sinUIvisible/vozfísica; no mínimo universal ni aceptaciónC03. La explicación más amplia de retención enT1 puede estudiarse si hace falta, pero no se convierte retrospectivamente en fallo del modelo cuando el dato no se incluyó y la decisión pendiente sí era clara.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
campaign=base/'astra-memory-view515';campaign.mkdir(exist_ok=False)
original=(root/'scratchpad/c03-private-product514.py').read_text(encoding='utf-8-sig')
start=original.index('cases = [');end=original.index('\n\ncommands',start)
cases=ast.literal_eval(original[start+len('cases = '):end].strip())+['Desactiva la memoria privada.']
write(campaign/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'method':'Two new isolated product profiles, baseline then filtered writer view, same source512/current registered Qwen2507Q4/b9980/profile. Same eight514 inputs plus a real disable control. Only treatment changes the model-facing situation line for completed private enable/disable/save/sensitive.save/correct: omit redundant state when seen exists, and omit corrected/sensitive/replayed only when exactlyfalse. Keep enabled=false and all true flags. Raw facts, caller payload, validators, operation, outcome, user request and all other messages remain intact. No visible reply editing. Actual isolated synthetic persistence, no owner data, UI or physical voice.','causal_scope':'Inspect original and effective targeted payloads and all downstream responses. Later dialogue may legitimately differ after changed narration; do not claim every downstream payload is identical. No sampler/backend/model promotion, no name-specific treatment.','controls':'Private recall, clarification, current-name vs stored-name, explicit confirmation and disabling memory must remain truthful. A new input is synthetic development, not reserve. A successful control does not prove all sensitive/correction/replay paths; true-flag and protected-value checks remain required before source adoption.','limits':'GPU3800MiB stop/freeRAM768MiB/240s per scenario; stop only owned process tree. Source unchanged during both runs.'})
for mode in ['base','view']:
 tag='515-'+mode;script=original.replace('514',tag)
 start=script.index('cases = [');end=script.index('\n\ncommands',start)
 script=script[:start]+'cases = '+repr(cases)+script[end:]
 start=script.index("    'production_verification':");end=script.index("    'profile_inheritance':",start)
 script=script[:start]+"    'production_verification': "+repr('515 '+mode+': source512 actual product, registered runtime, same9cases; see astra-memory-view515/PREREG.json. Only treatment mutates the writer view, never replies or source.')+",\n    'method': 'Compare actual memory narration and preserve private/core/confirmation behavior; no profile tuning or model ranking.',\n"+script[end:]
 target=root/('scratchpad/c03-private-product'+tag+'.py');assert not target.exists();target.write_text(script,encoding='utf-8')
 hook=root/('scratchpad/c03-owner'+tag+'-hook');hook.mkdir(exist_ok=False)
 source=(root/'scratchpad/c03-owner514-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('514',tag)
 source+='''
_writer_view_post = LlmRuntime._post
def _observed_writer_view(self, payload, *args, **kwargs):
    import copy
    before = copy.deepcopy(payload)
    changes = []
    if 'MODE' == 'view':
        messages = payload.get('messages', [])
        allowed = {'memory.enable','memory.disable','memory.save','memory.sensitive.save','memory.correct'}
        for index, message in enumerate(messages):
            if message.get('role') != 'user' or not isinstance(message.get('content'), str):
                continue
            lines = message['content'].splitlines()
            for line_index, line in enumerate(lines):
                if not line.startswith('situation: '):
                    continue
                view = json.loads(line.removeprefix('situation: '))
                if (view.get('kind') != 'status' or view.get('outcome') != 'completed'
                        or view.get('operation') not in allowed or not isinstance(view.get('seen'),dict)):
                    continue
                prior_view = copy.deepcopy(view)
                view.pop('state',None)
                for key in ['corrected','sensitive','replayed']:
                    if view['seen'].get(key) is False:
                        view['seen'].pop(key)
                if view == prior_view:
                    continue
                lines[line_index] = 'situation: ' + json.dumps(view,ensure_ascii=False)
                payload = copy.deepcopy(payload)
                payload['messages'][index]['content'] = '\\n'.join(lines)
                changes.append({'original_view':prior_view,'effective_view':view})
    with (private/'writer-view.jsonl').open('a',encoding='utf-8') as output:
        output.write(json.dumps({'mode':'MODE','changes':changes,'before':before,'after':payload},ensure_ascii=False)+'\\n')
    return _writer_view_post(self,payload,*args,**kwargs)
LlmRuntime._post = _observed_writer_view
'''.replace('MODE',mode)
 (hook/'sitecustomize.py').write_text(source,encoding='utf-8')
write(campaign/'PINS.json',{p.name:sha(p) for p in campaign.iterdir() if p.is_file() and p.name!='PINS.json'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n514cerrado39353exit0:7/8finalesútiles;guardado/lecturasprivadasJordan yconversaciónÁlvaro correctos. T2narra metadatosinternos. T1sí cumple decisión/target; no exigirretrospectivamenteallíretención noincluida. ProgresoHTTP12 otra frontera:afirmaausenciaderesultadosapartirdesupayloadsinresultados. RAM1803,270/GPU3497,559MiB28,093s.515PREREG/hooksscriptsbase/viewlistos,9casoscadaperfillimpio(+desactivar); sólo vista deéxitosprivadosquitaestado redundanteyfalse corrected/sensitive/replayed; conservaenabledfalse/trueflags. No fuente nueva. Ejecutarbaseyrecogerantesdeview; no dosGPUjuntas. Sinprocesosactivos.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='514cerrado7/8finales;fuente512validada;sinprocesos.',continuation='515baseyviewsecuenciales para metadatos del redactor;progreso pendiente aparte.C03activo.');write(base/'RELEVO_ACTIVO.json',r)
print('514closed7/8 plus progress issue;515 paired private product scripts prepared.')
