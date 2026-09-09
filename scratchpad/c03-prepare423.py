from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product422-private'
out=base/'astra-private-product422'
events=[json.loads(line) for line in (private/'capture/events.jsonl').open(encoding='utf-8-sig')]
finals=[e for e in events if e['type']=='terminal']
cases=json.loads((out/'PREREG.json').read_text())['cases']
report='''# 422 — atribución de RAM; mismos fallos de conducta

Mismos8casos/fuente418/modelo4B/--no-mmap/límites421; sólo telemetría por PID.
Exit1/corteRAMlibre<768MiB;GPU3177,5625MiB/RAMárbol5303,9921875MiB/52,719s.
Manifiesto intacto.110 muestras, mínimo disponible752,355MiB. No voz física/UI.
El pico por proceso se da en distintos momentos; no sumar picos individuales.
Servidor llama máximo3676,008MiB RSS/7125,102MiB privada comprometida. El auxiliar
Python máximo877,984MiB RSS, mente349,398MiB y App229,367MiB. RSS es suma de
working sets, puede contar páginas compartidas; privada comprometida no es RAM
física residente. El heredado RamSampler usa esa suma RSS, no memoria privada.
El código router.py:466 es el único Popen Python auxiliar: router_worker con E5;
se confirma proceso exacto con commandline en423. Piper también apareció hasta
101,672MiB. Wake desactivado no significa que no haya síntesis en el conductor.

Siete terminales/admisiones;T8 sin llegar.3/7útiles(1,2,4),T3/T6aclaración
incorrecta,T5silencio composition_failed,T7sujeto incorrecto.418 logra recall
tras aclaración EN; no arregla la prosa ES. No se certifica ningún caso humano.
'''
for i,final in enumerate(finals,1):
    report+=f"\n{i}. Entrada: {cases[i-1]}\n   Final ({final['kind']}): {final['final']}\n"
report+='''
## Siguiente hipótesis acotada
La ayuda del b9980 exacto permite cache-ram y declara8192MiB por defecto.
El servidor crece con cada turno; probar423 sólo --cache-ram0 para distinguir
caché opcional de prompts en RAM de pesos/buffers activos. No reduce contexto,
slots, pesos ni precisión. Se conserva --no-mmap de422 para aislar una variable.
Logs nativos a verbosity4 y commandline por PID se añaden como observación.
Herencia: dossier Carter/Ollama03_Optimizacion...:12–14 hablaba KVq8/contexto
(ya usados aquí); otro backend/modelo, no justifica recortar calidad/contexto.
INVESTIGACION_MODELO_C03 no registra prueba cache-ram. Ayuda exacta b9980 manda.
Primarias consultadas2026-09-08: https://github.com/ggml-org/llama.cpp/pull/16391
documenta cache en RAM para evitar recomputar prefijos y flag0 para desactivar;
https://github.com/ggml-org/llama.cpp/pull/15293 separa checkpoints del contexto.
No cambiar ambos mecanismos juntos ni asumir que esta caché causa todo el pico.
'''
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','RESULT.md']]
paths += [private/n for n in ['capture/events.jsonl','memory-samples.json','memory-attribution.json','effective-server-command.json','server.log']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
# 421 began processing T5 before its conductor terminal was emitted; preserve correction.
p=base/'astra-private-product421/RESULT.md'
text=p.read_text(encoding='utf-8').replace('No se han ejecutado T5–T8.', 'T5 alcanzó la mente y una lectura system.identity incorrecta, sin final;T6–T8 no llegaron.')
text=text.replace('4 sin ejecutar.', 'T5 sin final yT6–T8sin ejecutar.')
text += '\nCorrección: HTTP nativo421 incluye «Me llamo Álvaro.» y su composición con\ncuenta Windows, aunque capture terminó en T4. No equiparar finales a ejecución.\n'
p.write_text(text,encoding='utf-8',newline='\n')
pins_path=p.parent/'PINS.json';pins=json.loads(pins_path.read_text());pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();pins_path.write_text(json.dumps(pins,indent=2)+'\n',newline='\n')

target=root/'scratchpad/c03-private-product423.py'
assert not target.exists()
source=(root/'scratchpad/c03-private-product422.py').read_text(encoding='utf-8').replace('422','423')
source=source.replace("'attribution_only':", "'cache_change': 'Only --cache-ram0 relative422; exact b9980 default8192MiB host prompt cache. Same context slots KV precision weights and no-mmap. Native verbosity4 and process commandline are observation only. Quality/latency measured, not assumed.',\n    'attribution_only':")
source=source.replace('This repeat diagnoses allocation ownership, not a new quality comparison or acceptance. No thresholds/source/loading change.', 'Measures cache limit change and allocation ownership; no fresh acceptance. No thresholds/source/weights change.')
source=source.replace("'rss_mib':info.rss/2**20", "'command':child.cmdline(), 'rss_mib':info.rss/2**20")
compile(source,str(target),'exec')
target.write_text(source,encoding='utf-8',newline='\n')
hook=root/'scratchpad/c03-owner423-hook';hook.mkdir(exist_ok=False)
observer=(root/'scratchpad/c03-owner422-hook/sitecustomize.py').read_text(encoding='utf-8').replace('422','423')
observer=observer.replace("'--no-mmap', '--log-file'", "'--no-mmap', '--cache-ram', '0', '--verbosity', '4', '--log-file'")
(hook/'sitecustomize.py').write_text(observer,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8')
    text=text.replace('421 corte RAM;422 atribución preparada','422 atribuido;423 caché RAM preparada')
    text=text.replace('T5–8sin ejecutar.', 'T5 llegó a lectura Windows errónea sin final;T6–8no llegaron.')
    text=text.replace('422 preparado: mismo421 con muestreo por PID deRSS/privada y RAM libre cada250ms.\nSólo atribución de consumo; no nueva hipótesis de calidad ni aceptación.', '''422 corte52,719s/RAM5303,99MiB/GPU3177,56.110muestras; llama pico3676MiB RSS,
auxiliarPython878MiB,mente349MiB.3/7finalesútiles;T5silencio,T6falsarefusal,
T7«Mi nombre es Jordan»sujetoincorrecto.423preparado: sólo --cache-ram0 frente422,
misma carga/modelo/contexto/slots/guards, logsverbosity4 y commandline por PID.
Hipótesis: caché opcional RAM8192MiB por defecto en b9980; contrastar con consumo.
RESULT/PINS422; no nueva fuente ni adopción. No Full.''')
    text=text.replace('scratchpad/c03-private-product422.py','scratchpad/c03-private-product423.py')
    p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='422 attributed RAM mostly llama-server then router worker; same memory/clarification failures persist.',continuation='Run423 only cache-ram0 compared422; detailed native logs and PID commands. Same weights/context/slots/guards. Full C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('422 recorded;421 incomplete-T5 corrected;423 prepared')
