from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=local/'C03-private-product423-private'
out=base/'astra-private-product423'
read=lambda p:[json.loads(l) for l in p.open(encoding='utf-8-sig')]
events=read(private/'capture/events.jsonl');finals=[e for e in events if e['type']=='terminal']
baseline=[e for e in read(local/'C03-private-product422-private/capture/events.jsonl') if e['type']=='terminal']
assert [e['final'] for e in baseline]==[e['final'] for e in finals[:7]]
resources=json.loads((out/'resources.json').read_text());assert not resources['violations']
samples=json.loads((private/'memory-samples.json').read_text())
peak=max(samples,key=lambda s:sum(p['rss_mib'] for p in s['processes']))
safe_peak={**peak,'processes':[{k:v for k,v in p.items() if k!='command'} for p in peak['processes']]}
router_commands={tuple(p['command']) for s in samples for p in s['processes'] if any('router_worker' in v for v in p['command'])}
assert router_commands
summary={'resources':resources,'minimum_free_ram_mib':min(s['available_mib'] for s in samples),'peak_sample':safe_peak,'router_worker_confirmed':True,'same_first_seven_finals':True}
(out/'ATTRIBUTION.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
report=f'''# 423 — desactivar caché RAM permite completar los ocho turnos

Una diferencia funcional contra422: --cache-ram0; se mantiene --no-mmap.
Logsverbosity4/commandline por PID son observación. Ayuda exacta y log confirman
prompt cache disabled,4096tokens por slot×3,KVq8_0,CPUweights497,31MiB,
GPUweights2603,50MiB/KV204MiB/estado recurrente150,75MiB. Checkpoints siguen
activados; no se cambió capacidad de contexto/pesos/precisión ni memoria privada.

RAMárbol3173,4296875MiB frente5303,9921875MiB422: reducción2130,5625MiB(~40,17%).
GPU3177,5625MiB igual.56s, sin violaciones, mínimo RAMlibre{summary['minimum_free_ram_mib']:.3f}MiB.
Exit0,manifiesto intacto.8admisiones200/8terminales:7respuestas y1composition_failed.
Primeros7finales idénticos a422; T8 nuevo «Te llamas Álvaro.» correcto.
4/8útiles(T1,T2,T4,T8);T3permiso redundante,T5silencio,T6falsarefusal,T7sujeto
equivocado siguen abiertos. Igualdad textual no demuestra regresión general.
Sintéticos de desarrollo;0casos humanos finales. No UI/voz física conjunta.
La commandline confirma auxiliar baxy_mind.router_worker. Datos RSS y privada
no son intercambiables; verATTRIBUTION.json y samples privados. Árbol cerrado.

424 retirará sólo --no-mmap para probar si cache-ram0 basta con la carga original.
Mismos8casos/configuración/source418/guards. Sólo después decidir fuente; evitar
conservar un flag sin mejora demostrada. No promoción del modelo ni nuevo runtime.
'''
cases=json.loads((out/'PREREG.json').read_text())['cases']
for i,e in enumerate(finals,1):report+=f"\n{i}. {cases[i-1]}\n   {e['kind']}: {e['final']}\n"
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','ATTRIBUTION.json','RESULT.md']]+[private/n for n in ['memory-samples.json','capture/events.jsonl','server.log','http-posts.jsonl','effective-server-command.json']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
target=root/'scratchpad/c03-private-product424.py';assert not target.exists()
source=(root/'scratchpad/c03-private-product423.py').read_text(encoding='utf-8').replace('423','424')
source=source.replace("'cache_change':", "'loading_ablation': 'Only remove --no-mmap compared423. Cache-ram0 remains. Return to original mmap default if no resource or behavior regression; no other change.',\n    'cache_change':")
source=source.replace('same 4B model, not a promotion.', 'same 4B model, not a promotion. Historical no-mmap flag is removed by this ablation.')
compile(source,str(target),'exec');target.write_text(source,encoding='utf-8',newline='\n')
hook=root/'scratchpad/c03-owner424-hook';hook.mkdir(exist_ok=False)
observer=(root/'scratchpad/c03-owner423-hook/sitecustomize.py').read_text(encoding='utf-8').replace('423','424').replace("'--no-mmap', ",'')
(hook/'sitecustomize.py').write_text(observer,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8').replace('422 atribuido;423 caché RAM preparada','423RAM3,10GiB;424 sin no-mmap preparado')
    text=text.replace('scratchpad/c03-private-product423.py','scratchpad/c03-private-product424.py')
    text += '''
423cache-ram0 completa8turnos sincorte:RAM3173,43MiB/GPU3177,56MiB56s,
~40%menosRAMque422.7primerosfinalesidénticos;T8actualnombrecorrecto;4/8útiles.
RESULT/PINS/ATTRIBUTION423.424retira sólo --no-mmap para verificar cache-ram0
con carga original; sin fuente mientras corre. Elegir un solo cambio necesario.
'''
    p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='423 cache-ram0 reduces peak RSS40% to3173MiB, completes8turns;4useful, same first7failures/successes.',continuation='Run424 removing only no-mmap; then adopt only necessary loading/cache setting with owner tests and Fast. Source418 unchanged; C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'423':summary['resources'],'minimum_free_ram_mib':summary['minimum_free_ram_mib'],'424':'prepared'}))
