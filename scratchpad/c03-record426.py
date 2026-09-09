from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product426-private';out=base/'astra-private-product426'
command=json.loads((private/'effective-server-command.json').read_text())
assert command.count('--no-mmap')==1 and command[command.index('--cache-ram')+1]=='0'
report='''# 426 — ahorro confirmado con el código del producto

El hook sólo observa HTTP y comando y añade log/verbosity4. Cache-ram0 y
no-mmap aparecen una sola vez desde LlmRuntime de producción425.
8admisiones200/8terminales idénticos a423 y424:4útiles, mismos4fallos conocidos.
RAMárbol3106,6953125MiB(3,034GiB); GPU3177,5625MiB(3,103GiB);55,422s.
Sin violaciones,exit0,manifiesto intacto. Fuente425 validada owners/Fast antes
de esta corrida. Modelo3.54B diagnóstico,no promoción2507registrado.
No certifica UI real, audio físico/ASR/wake conjunto ni mínimo global de memoria.

La presentación T5 se envió como «Me llamo Álvaro.» con historia completa;
la llamada nativa AUTO devuelve baxy_system__identity({}) y acaba en silencio
al componer sobre cuentaWindows. No hay guardia semántica de efectos para ese
texto en la captura. La primera transformación incorrecta precede al proveedor
y a la prosa. T7 «Mi nombre esJordan» es otro fallo, de sujeto al componer recall.
Introducción y pares privados en introduction-pairs.json. No mezclar sus causas.

427comparará el payload AUTO exacto con el clasificador de acto existente sin
catálogo, sobre13controles preregistrados. Sólo diagnóstico; no se añade otro
prompt ni se adopta una cascada. Heredar guardia existente y sus rechazos sobre
acciones reconocidas; contrastar antes de cambiar conducta. Árbol426cerrado.
'''
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','RESULT.md']]+[private/n for n in ['effective-server-command.json','memory-samples.json','capture/events.jsonl','server.log','http-posts.jsonl','introduction-pairs.json']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
resource_doc='''# Memoria de BAXY — mediciones del 8 de septiembre de 2026

La última prueba del producto usó un pico de **3,03 GiB de RAM y 3,10 GiB de
VRAM**. Completó ocho turnos de desarrollo con el ajuste ya incorporado al código.
Es una mejora medida; todavía no es el mínimo global ni la certificación del
conjunto con micrófono, reconocimiento de voz y activación por voz.

| Prueba | Configuración | RAM máxima del árbol | VRAM máxima | Resultado |
|---|---|---:|---:|---|
| 422 | Sin mapeo; caché RAM por defecto | 5,18 GiB | 3,10 GiB | Corte por poca RAM libre; siete terminales |
| 423 | Sin mapeo; caché RAM desactivada | 3,10 GiB | 3,10 GiB | Ocho terminales |
| 424 | Mapeo original; caché RAM desactivada | 5,09 GiB | 3,10 GiB | Ocho terminales idénticos a 423 |
| 426 | Ambas medidas desde el código del producto | 3,03 GiB | 3,10 GiB | Ocho terminales idénticos a 423 |

Se conserva el mismo modelo diagnóstico Qwen3.5-4B Q4_K_M, contexto de 4096
tokens por cada uno de tres slots, precisión KV q8_0 y parámetros de generación.
El ahorro procede de no guardar copias opcionales de prefijos en RAM y evitar
mantener residentes páginas del archivo del modelo cuando se utiliza GPU.
El perfil CPU conserva el mapeo; no se midió un beneficio al retirarlo sin GPU.

Los ocho casos son de desarrollo. Cuatro respuestas fueron útiles; los fallos
de aclaración, presentación personal y sujeto de memoria siguen abiertos. La
reducción de RAM no se presenta como una mejora de calidad ya conseguida.

La RAM reportada suma los conjuntos de trabajo de los procesos del diagnóstico;
puede contar páginas compartidas. La memoria privada comprometida es otra
medida: incluye memoria que no necesariamente está residente en RAM. El margen
de RAM libre del PC también depende de las otras aplicaciones abiertas.

**4 GB de VRAM es el techo, no un consumo obligatorio.** BAXY seguirá necesitando
RAM para Windows, su aplicación y las partes que ejecuta la CPU, aunque se puedan
alojar más tensores del modelo en la GPU. No se ha demostrado que todos sus
modelos activos quepan juntos en 4 GB, ni cuál es la VRAM mínima que conserva la
calidad exigida. Esas comprobaciones quedan dentro del cierre C03.

Fuentes reproducibles: RESULT y PINS en astra-private-product422/423/424/426;
adopción y pruebas en astra-host-memory425. El backend exacto es llama.cpp b9980.
Su [documentación de caché en RAM](https://github.com/ggml-org/llama.cpp/pull/16391)
explica el mecanismo; las cifras anteriores son mediciones locales.
'''
(base/'RECURSOS_2026-09-08.md').write_text(resource_doc,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8').replace('producto426 preparado','producto426 confirmado;427 preparado')
    text=text.replace('426debe comprobar producto.', '426confirma producto y ahorro.')
    text=text.replace('426preparado: mismo423 con fuente425;hook sóloobserva, noinyectaflagsdecarga.', '426completa8con fuente425:RAM3106,70MiB/GPU3177,56MiB55,422s,sincorte.\n8finalesidénticos423;4útiles. Hooknoinyectaflags. RESULT/PINS426.')
    text=text.replace('Ejecutar: runtimePython -X utf8 scratchpad/c03-private-product426.py.', 'Ejecutar: runtimePython -X utf8 scratchpad/c03-introduction427.py.\n13controles: replayAUTO426T5 contra guardia deactoexistente sincatálogo;\nnoadopción ni nuevoprompt. Firsterror: primariaAUTOeligeWindowsparaMe llamoÁlvaro.')
    p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='426 production source425 uses3106.70MiB RAM/3177.56MiB GPU;8samefinals4useful. No threshold violations.',continuation='Run prepared427 captured-native AUTO vs existing catalog-free semantic shape on13controls; investigate personal introduction before any new source. Full C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('426 recorded; resources report updated;427 next')
