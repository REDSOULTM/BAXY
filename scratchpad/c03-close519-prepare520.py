"""Record the one-sentence causal comparison before a minimal source removal."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
campaign=base/'astra-status-hint519';results={}
for mode in ['base','hint']:
    out=base/f'astra-private-product519-{mode}'
    private=Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-private-product519-{mode}-private'
    events=list(map(json.loads,(private/'capture/events.jsonl').open(encoding='utf-8-sig')))
    terminals=[r for r in events if r['type']=='terminal'];assert len(terminals)==11
    for i,r in enumerate(terminals,1):
        r.update(turn=i,useful=i not in ({2,9,11} if mode=='base' else {2,11}))
        r['reason']={2:'Internal result/metadata narration remains.',11:'The response denies having local memory while the verified facts show a disabled existing store with one record; capability and activation are conflated.'}.get(i,'Useful truthful result, decision, clarification or conversation.')
        if i==9:r['reason']='Verified disable reported; additional claim of no detected PC changes is unsupported.' if mode=='base' else 'Verified disabled state without the unsupported PC observation; redundant second sentence is not a new false fact.'
    shapes=list(map(json.loads,(private/'shape-instruction.jsonl').open(encoding='utf-8-sig')))
    for row in shapes:
        assert row['after']==(row['before'].replace(' Completing a request does not imply changing the PC.','') if mode=='hint' else row['before'])
    exit_record=json.loads((out/'EXIT.json').read_text(encoding='utf-8-sig'))
    resources=json.loads((out/'resources.json').read_text(encoding='utf-8-sig'))
    assert exit_record['exitCode']==0 and exit_record['manifest_unchanged'] and not resources['violations']
    results[mode]={'useful':sum(r['useful'] for r in terminals),'total':11,'terminals':terminals,'shape_calls':len(shapes),'shape_changes':sum(r['before']!=r['after'] for r in shapes),'resources':resources,'exit':exit_record,'session':87936 if mode=='base' else 81593,'session_exit':0}
    write(out/'ADJUDICATION.json',results[mode])
    write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
write(campaign/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'arms':results,'decision':'Adopt only removal of the broad second sentence from successful-status shape instructions. Preserve verified-results instruction and all data/guards/profile. The factual claim disappears in T9; no read/confirmation/name regression in this product panel. T2 and T11 remain open, progress separately.','limitations':'One registered-profile source diagnostic, not an optimized global model ranking, acceptance sample or voice/UI validation. Real clocks differ between runs as expected; compare each against its own verified payload. Resource totals do not establish a speed improvement.'})
(campaign/'RESULT.md').write_text('''# Una instrucción genérica induce una observación sin prueba

Base8/11 finales útiles; retirar únicamente la segunda frase de la instrucción de forma deja9/11. T9 conserva «La memoria privada ha sido desactivada. El estado actual indica que está deshabilitada.» y desaparece la frase que afirmaba no haber detectado cambios en el PC. La lectura de hora devuelve la hora propia de cada ejecución; los controles anteriores de nombres y confirmación se conservan.

Los13 registros de forma por brazo acreditan exactamente el tratamiento:0 cambios en base y6 en tratamiento, todos por eliminar Completing a request does not imply changing the PC. No se retiran metadatos, estados, indicadores falsos ni instrucciones de verificación. No se cambian modelo, muestreo, llamadas ni autorización.520 adoptará esa sola eliminación.

T2 sigue narrando metadatos internos y T11 sigue negando tener memoria local aunque describe su estado desactivado. Estos dos fallos quedan abiertos, igual que el progreso. Base: RAM2171,070MiB/GPU3497,559MiB32,438s. Tratamiento: RAM1840,770MiB/GPU3497,559MiB31,500s. Ambas sesiones87936/81593 recogidas exit0; registro intacto y sin violaciones. No se atribuye una mejora de rendimiento a los tiempos globales ni se acredita UI/voz o aceptación fresca.
''',encoding='utf-8')
write(campaign/'PINS.json',{p.name:sha(p) for p in campaign.iterdir() if p.is_file() and p.name!='PINS.json'})
out=base/'astra-status-evidence520';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-evidence520-private';private.mkdir(exist_ok=False)
(private/'llm.py').write_bytes((root/'src/baxy_mind/llm.py').read_bytes())
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cause':'519 paired actual product isolates broad negative hint as the cause of unsupported absence-of-PC-changes narration in verified disable.','change':'Remove only the second sentence from successful-status shape instruction. Do not add a different negative hint, filter data, rewrite visible answers, change sampling or add a generation. Existing global fact-grounding instruction and validators remain.','validation':'519 exact paired causal baseline is retained, no tautological prompt-string test. Run existing seven Python owners covering turn/compose/transport/read/plan, then Fast with existing BAXYQuality default interpreter. No Full during repair. Product regression after validation.','before_sha256':sha(root/'src/baxy_mind/llm.py')})
note='\n519 cerrado: base8/11, quitar sólo segunda frase de instrucción9/11; T9 deja de inventar ausencia de cambios detectados. T2 metadatos/T11 confunde capacidad con activación siguen fallando.13 formas por brazo,0/6 cambios exactos; sesiones87936/81593exit0.520 preregistrado para eliminar esa sola frase en fuente, después siete owners/Fast y producto. Sin procesos activos ni cambio de modelo/config.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as f:f.write(note)
relay_path=base/'RELEVO_ACTIVO.json';relay=json.loads(relay_path.read_text(encoding='utf-8-sig'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='516 validado;519 cerrado con mejora factual8/11→9/11, fallos residuales conservados;520 preparado.',continuation='520 eliminar sólo segunda frase genérica, owners Python y Fast. Reserva518:92solapados/112sincoincidencia parcial. C03 activo.');write(relay_path,relay)
print('519 closed; 520 preregistered; source unchanged yet.')
