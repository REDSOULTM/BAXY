"""Keep the verified disable and isolate the broad no-PC-change narration hint."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, ast

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-private-product517';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product517-private'
events=list(map(json.loads,(private/'capture/events.jsonl').open(encoding='utf-8-sig')))
terminals=[r for r in events if r['type']=='terminal'];assert len(terminals)==9
for i,r in enumerate(terminals,1):
    r.update(turn=i,useful=i not in (2,9))
    r['reason']={2:'Internal metadata narration remains.',9:'Disable is verified, but the added absence of detected system changes is not in the evidence.'}.get(i,'Useful truthful final; original binding and names preserved.')
posts=list(map(json.loads,(private/'http-posts.jsonl').open(encoding='utf-8-sig')))
last=next(r for r in reversed(posts) if r['stage']=='request')['payload']
assert '"enabled": false' in last['messages'][-1]['content']
resources=json.loads((out/'resources.json').read_text(encoding='utf-8-sig'))
exit_record=json.loads((out/'EXIT.json').read_text(encoding='utf-8-sig'))
assert exit_record['exitCode']==0 and exit_record['manifest_unchanged'] and not resources['violations']
write(out/'ADJUDICATION.json',{'terminals':terminals,'disable_payload':last})
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':93796,'exit':0,'useful_finals':7,'total':9,'disable_effect_verified':True,'resources':resources,'manifest_unchanged':True,'source_adopted':'516 private configuration grammar is verified through actual C# memory route; no519 prompt change yet.','remaining':'T2 internal narration; T9 reports unsupported absence of detected PC changes despite actual enabled=false. The raw shape hint says Completing a request does not imply changing the PC; investigate that hint separately. Progress remains separate.'})
(out/'RESULT.md').write_text('''# Producto517: la deshabilitación ya se ejecuta

La petición llega al flujo privado, cambia la configuración y entrega enabled=false verificado al redactor. El estado dejó de rechazarse como fuera de capacidades. Los ocho finales anteriores permanecen iguales, incluida la distinción entre nombre guardado y conversacional.7/9 finales siguen siendo útiles: T2 mantiene metadatos internos, y T9 añade «No se han detectado cambios en el sistema», que los hechos no respaldan.

El payload de T9 conserva correctamente enabled=false; además lleva la instrucción genérica Completing a request does not imply changing the PC. Su interpretación como ausencia observada de cambios es la siguiente hipótesis causal.519 comparará conservar o retirar sólo esa frase, con los datos, modelo, muestreo y guardas originales. No se reutiliza el filtro515 rechazado. Se añaden una lectura de hora y otra de estado de memoria como controles de lectura.

Sesión93796 recogida exit0. RAM1912,047MiB, GPU3497,559MiB,48,828s; sin violaciones y manifiesto intacto. Conductor y memoria sintética aislada, sin interfaz visible ni voz física. Ni el producto entero bajo voz ni la reserva de100 están acreditados.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
campaign=base/'astra-status-hint519';campaign.mkdir(exist_ok=False)
original=(root/'scratchpad/c03-private-product517.py').read_text(encoding='utf-8-sig')
start=original.index('cases = [');end=original.index('\n\ncommands',start)
cases=ast.literal_eval(original[start+len('cases = '):end].strip())+['Dime la hora.','¿Tienes memoria local?']
write(campaign/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'cause':'517 T9 receives verified enabled=false but adds absence of detected PC changes. _compose_shape_instruction appends the broad no-PC-change hint to every successful status, including private mutations. Facts themselves remain correct.','method':'Two new isolated product profiles, baseline then treatment. Same source516/current registered Qwen/b9980. Only treatment removes the exact second sentence from the shape instruction: Completing a request does not imply changing the PC. Keep Report the verified results, all seen flags, operation/state/outcome, sampler, validators and original caller facts. Instrument shape before/after. No status515 view filter or source edit.','criteria':'T9 must report actual disabled state without unobserved detection claims or invented additional effects. T1-T8 retain their original binding and factual behavior; T2 known internal prose remains a failure if present. T10 verified time must not invent a PC change; T11 must report memory capability/state consistent with enabled=false. Judge all final/activity/progress outputs, not just targeted sentence removal. No fixed visible reply, no acceptance reserve.','causal_limits':'Later dialogue may differ after changed narration; compare exact shape outputs and targeted payload facts. One fixed profile source diagnostic, not model ranking. No UI or voice, private synthetic persistence only; own-tree GPU3800MiB/freeRAM768MiB/240s. Source unchanged during both runs.'})
for mode in ['base','hint']:
    tag='519-'+mode;script=original.replace('517',tag)
    start=script.index('cases = [');end=script.index('\n\ncommands',start)
    script=script[:start]+'cases = '+repr(cases)+script[end:]
    start=script.index("    'production_verification':");end=script.index("    'profile_inheritance':",start)
    script=script[:start]+"    'production_verification': "+repr('519 '+mode+': source516 full product, same11 cases; see astra-status-hint519/PREREG.json. Only treatment changes shape hint privately.')+",\n    'method': 'Compare verified effects and reads plus narration; no profile tuning, metadata filtering or model ranking.',\n"+script[end:]
    target=root/('scratchpad/c03-private-product'+tag+'.py');assert not target.exists();target.write_text(script,encoding='utf-8')
    hook=root/('scratchpad/c03-owner'+tag+'-hook');hook.mkdir(exist_ok=False)
    source=(root/'scratchpad/c03-owner517-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('517',tag)
    source+='''
import baxy_mind.llm as llm_module
original_shape = llm_module._compose_shape_instruction
def observed_shape(*args, **kwargs):
    before = original_shape(*args, **kwargs)
    after = before
    if 'MODE' == 'hint':
        after = before.replace(' Completing a request does not imply changing the PC.', '')
    with lock, (private/'shape-instruction.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps({'args':args,'kwargs':kwargs,'before':before,'after':after},ensure_ascii=False)+'\\n')
    return after
llm_module._compose_shape_instruction = observed_shape
'''.replace('MODE',mode)
    (hook/'sitecustomize.py').write_text(source,encoding='utf-8')
note='\n517 cerrado93796exit0: deshabilitación privada real verificada enabled=false;7/9 útiles porque T2 sigue interno y T9 añade ausencia de cambios no observada. RAM1912,047/GPU3497,559MiB48,828s, sin violaciones.519 preparado: mismo producto11casos (+hora/estado memoria), dos perfiles limpios; sólo quitar frase genérica de ausencia de cambios de la instrucción de forma. No filtro515 ni cambios de fuente. Ejecutar base, recoger y luego hint.518 ya cerrado; siguiente número libre520.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as f:f.write(note)
relay_path=base/'RELEVO_ACTIVO.json';relay=json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='516 validado;517 cerrado con efecto disable real y narración aún defectuosa;518 auditoría cerrada.',continuation='519 base y hint secuenciales, recoger procesos antes de editar. Estado/progreso y reserva pendientes; C03 activo íntegro.')
write(relay_path,relay)
print('517 closed; 519 paired product diagnostic prepared, source unchanged.')
