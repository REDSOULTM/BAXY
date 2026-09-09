from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-private-product419'
resources = json.loads((out / 'resources.json').read_text())
assert resources['violations'] == ['system_free_ram_bound']
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-private-product419-private'
events = [json.loads(x) for x in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
assert not any(x.get('type') == 'terminal' for x in events)
report = '''# 419 — detenido por RAM libre antes de los turnos

El guardia conservador de RAM libre (<768 MiB) terminó exclusivamente el árbol
del diagnóstico durante el arranque, tras publicar Core y cargar el modelo.
Cero turnos/terminales: no hay resultado semántico de los ocho casos. Se conserva
el intento fallido, sin dar la corrección418 por validada en producto todavía.
GPU propia máxima 3167,5625 MiB; RAM muestreada del árbol 3543,671875 MiB; 61,157 s.
Este pico del árbol no describe toda la RAM del sistema ni acredita voz conjunta.
No se alcanzó el límite VRAM de3800 MiB. Exit1, manifiesto intacto.

Tras la terminación sólo quedaron cuatro trabajadores de compilación del
publicado AOT, hijos de88616 (99740,67884,90316,103672); no modelo ni producto.
Se cerraron con build-server shutdown de ambos SDK. RAM libre resultante
5485224 KiB. La encuesta no se tocó. El import de los samplers sólo reutiliza
tooling existente; no hay evidencia de que él explique el consumo.

420 repetirá exactamente los mismos ocho casos y fuente418, ya con Core
publicado y servidores inactivos cerrados; nuevo perfil, mismos límites,
modelo/configuración/observer. Es restauración del entorno tras un corte
anterior a cualquier caso, no selección de una corrida favorable. Si el límite
reaparece sin compilación, estudiar distribución RAM del runtime; no rebajar
el margen ni atribuir el fallo a comprensión. No nueva fuente420.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8', newline='\n')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'PROCESS.json', 'EXIT.json', 'resources.json']]
paths += [private / n for n in ['launch.log', 'capture/events.jsonl']]
(out / 'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n', newline='\n')
source = (root / 'scratchpad/c03-private-product419.py').read_text(encoding='utf-8')
for old, new in [('astra-private-product419', 'astra-private-product420'), ('C03-private-product419-private', 'C03-private-product420-private'), ('C03-private-profile419', 'C03-private-profile420'), ('c03-owner419-hook', 'c03-owner420-hook')]:
    source = source.replace(old, new)
source = source.replace("'method':'Eight synthetic development turns", "'method':'Repeat after419 resource-bound startup abort with zero cases; no source/model/limit change. AOT Core is already published and idle build servers were shut down. Eight synthetic development turns")
target = root / 'scratchpad/c03-private-product420.py'
assert not target.exists()
compile(source, str(target), 'exec')
target.write_text(source, encoding='utf-8', newline='\n')
hook = root / 'scratchpad/c03-owner420-hook'
hook.mkdir(exist_ok=False)
text = (root / 'scratchpad/c03-owner419-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-private-product419-private', 'C03-private-product420-private')
(hook / 'sitecustomize.py').write_text(text, encoding='utf-8', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    p = base / name
    text = p.read_text(encoding='utf-8').replace('418 validado; producto419 preparado', '418 validado;419 cortado por RAM;420 preparado')
    start = text.index('Producto419 está preparado')
    end = text.index('\n\nPendiente:', start)
    text = text[:start] + '''Producto419 se detuvo por RAM libre<768 MiB durante arranque, cero turnos,
GPU3167,56 MiB/RAMárbol3543,67 MiB/61,157s. No resultado semántico. RESULT/PINS419.
Modelo/producto cerrados; cuatro workers AOT restantes cerrados por ambos SDK.
RAM libre después5485224 KiB. Encuesta intacta.420 preparado, aún no ejecutado:
runtime Python -X utf8 scratchpad/c03-private-product420.py. Misma fuente418,
ocho casos419 y mismos límites; Core ya publicado, sin nueva compilación esperada.
Si vuelve a cortarse sin build, investigar RAM del runtime; no bajar el margen.
No nueva fuente420. La hipótesis de actor/first-person impuesto a memory.recall
se refutó leyendo RequiredBaxyActions: los hechos estructurados devuelven [].
Provenance349 ya añadió source=explicit user y no corrigió sujeto; no repetirlo.
NaturalMemoryRequestParser conserva brazos literales junto a patrones genéricos;
verificar alcance/reachability antes de atribuirles un fallo o retirarlos.
''' + text[end:]
    p.write_text(text, encoding='utf-8', newline='\n')
p = base / 'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='418 validated;419 aborted for free RAM before any turn; models and idle build workers closed.', continuation='Run prepared420 identical cases/source/limits after cleanup with Core already published. If RAM cutoff recurs without build, inspect runtime RAM rather than repeat/relax. Full C03 active.')
p.write_text(json.dumps(relay, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('419 recorded,420 prepared')
