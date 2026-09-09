from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA'])/'BAXY'
for number in (420,421):
    out = base/f'astra-private-product{number}'
    private = local/f'C03-private-product{number}-private'
    events = [json.loads(line) for line in (private/'capture/events.jsonl').open(encoding='utf-8-sig')]
    finals = [e for e in events if e['type']=='terminal']
    cases = json.loads((out/'PREREG.json').read_text(encoding='utf-8'))['cases']
    journal = [json.loads(line)['payload'] for line in (local/f'C03-private-profile{number}/journal/missions.jsonl').open(encoding='utf-8-sig')]
    safe_operations = [{'operation':r['operation'],'verified':r['response'].get('verified'),'status':r['response'].get('status')} for r in journal if r.get('response')]
    report = (out/'RESULT.md').read_text(encoding='utf-8') if number==420 else '''# 421 — --no-mmap no resuelve el corte de RAM

Mismo4B/casos/controles/fuente418 que420, con --no-mmap en comando efectivo.
GPU3177,5625MiB; RAMárbol4629,90234375MiB;36,172s; corteRAMlibre<768MiB.
Frente4204730,117MiB, sólo100,215MiB menos; no basta ni demuestra un mínimo.
Cuatro finales antes del corte. No adopción de fuente/configuración ni promoción.
No se han ejecutado T5–T8. Exit1/manifiesto intacto. Árbol diagnóstico cerrado.
'''
    report += '\n## Respuestas realmente emitidas\n\n'
    for i, final in enumerate(finals,1):
        report += f"{i}. Entrada: {cases[i-1]}\n   Respuesta: {final['final']}\n"
    report += '\nT1 pide confirmar activación privada;T2 tiene memory.enable y memory.save verificados.\n'
    if number==421:
        report += 'T3 pregunta permiso otra vez sin pedir qué aplicación: no útil. T4 recupera Jordan\ncon sujeto correcto y memory.recall verificado, tras aquella aclaración.3/4 útiles\nemitidos;3/8 de los preregistrados,4 sin ejecutar.418 ejercitado sólo en EN.\n'
    else:
        report += 'Dos respuestas útiles emitidas de los8casos preregistrados; seis no ejecutados.\nCorrección del resumen inicial:420 sí alcanzó dos terminales, no cero.\n'
    report += '\nOperaciones (sin descifrar ni publicar registros privados):\n```json\n'+json.dumps(safe_operations,ensure_ascii=False,indent=2)+'\n```\n'
    (out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
    paths = [out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','RESULT.md']]
    paths += [private/n for n in ['launch.log','capture/events.jsonl']]
    if number==421: paths += [private/n for n in ['effective-server-command.json','server.log','http-posts.jsonl']]
    (out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
    print(json.dumps({'run':number,'finals':len(finals),'operations':safe_operations}))

target = root/'scratchpad/c03-private-product422.py'
assert not target.exists()
source = (root/'scratchpad/c03-private-product421.py').read_text(encoding='utf-8').replace('421','422')
source = source.replace("'load_change':", "'attribution_only': 'Same421 with per-process RSS/private commit and system available memory every guard tick. This repeat diagnoses allocation ownership, not a new quality comparison or acceptance. No thresholds/source/loading change.',\n    'load_change':")
source = source.replace('    violations = []','    violations = []\n    memory_samples = []')
needle = '        while not stop.wait(0.25):\n'
assert source.count(needle)==1
source = source.replace(needle,needle+'''            rows = []
            try:
                owned = psutil.Process(process.pid)
                for child in [owned, *owned.children(recursive=True)]:
                    try:
                        info = child.memory_info()
                        rows.append({'pid':child.pid, 'parent':child.ppid(), 'name':child.name(),
                            'rss_mib':info.rss/2**20, 'private_mib':getattr(info,'private',0)/2**20})
                    except (psutil.NoSuchProcess,psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
            memory_samples.append({'elapsed':round(time.monotonic()-started,3),
                'available_mib':psutil.virtual_memory().available/2**20, 'processes':rows})
''')
source = source.replace('        gpu.stop()','        (private/\'memory-samples.json\').write_text(json.dumps(memory_samples,indent=2)+\'\\n\',encoding=\'utf-8\')\n        gpu.stop()')
compile(source,str(target),'exec')
target.write_text(source,encoding='utf-8',newline='\n')
hook = root/'scratchpad/c03-owner422-hook'
hook.mkdir(exist_ok=False)
observer = (root/'scratchpad/c03-owner421-hook/sitecustomize.py').read_text(encoding='utf-8').replace('421','422')
(hook/'sitecustomize.py').write_text(observer,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    text=p.read_text(encoding='utf-8').replace('420 corte RAM;421 preparado','421 corte RAM;422 atribución preparada')
    text=text.replace('No conclusión semántica de esos cortes.', '420 emitió2/8finales útiles;4213/8útiles,1noútil y4sin ejecutar.418 ejercitado EN.')
    start=text.index('421 preparado con')
    end=text.index('\n\nDescartes:',start)
    text=text[:start]+'''421 --no-mmap mismo4B vuelve a cortar:GPU3177,56/RAM4629,90MiB,36,172s.
Sólo100,215MiB menos que420; no adoptado. T1enable/T2save/T4recall útiles y
verificados, T3 pregunta permiso sin pedir aplicación(no útil). T5–8sin ejecutar.
422 preparado: mismo421 con muestreo por PID deRSS/privada y RAM libre cada250ms.
Sólo atribución de consumo; no nueva hipótesis de calidad ni aceptación.
''' + text[end:]
    text=text.replace('scratchpad/c03-private-product421.py','scratchpad/c03-private-product422.py')
    p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json'
relay=json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='421 --no-mmap still exceeds free-RAM margin;3 useful finals incl EN private recall after clarification. No adoption.',continuation='Run422 attribution-only same421 with per-process memory samples; identify actual allocation owner before another remedy.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
