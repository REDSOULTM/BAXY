"""Seal completed evidence158–170 without modifying earlier seals."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
def row(path):
    return {'path':str(path.relative_to(root)),'sha256':sha(path),'bytes':path.stat().st_size}
paths=set()
private={}
def verify_private(item):
    p=Path(item['privatePath'])
    assert sha(p)==item['sha256'],p
    private[str(p)]=item['sha256']
for item in json.loads((base/'TRAMO143_157_PINS.json').read_text(encoding='utf-8'))['files']:
    assert sha(root/item['path'])==item['sha256'],item['path']
snapshot=base/'astra-source164-snapshot'
index=json.loads((snapshot/'INDEX.json').read_text(encoding='utf-8'))
fast=Path(os.environ['TEMP'])/'c03-source164-fast.log'
with (snapshot/fast.name).open('xb') as f:
    f.write(fast.read_bytes())
index.append({'source':str(fast),'copy':str((snapshot/fast.name).relative_to(root)),'sha256':sha(fast)})
(snapshot/'INDEX.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
paths.add(snapshot/'INDEX.json')
for item in index:
    p=root/item['copy']
    assert sha(p)==item['sha256']
    paths.add(p)
for number in [158,166]:
    folder=base/f'astra-audio{number}'
    for name in ['PREREG.json','AUDIO_SETUP.json','AUDIO_READY.json','AUDIO_RESULT.json','PROCESS.json','RESOURCES.json','launch.log','shell-trace.jsonl','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','STOP_APP','STOP_AUDIO']:
        p=folder/name
        if p.is_file():
            paths.add(p)
    for number_case,slug in [(1,'es'),(2,'en'),(3,'mixed')]:
        for extension in ['json','png']:
            p=folder/f'{number_case:02d}-clock-{slug}.{extension}'
            if p.is_file():
                paths.add(p)
    audio=json.loads((folder/'AUDIO_RESULT.json').read_text(encoding='utf-8'))
    assert audio['restoredExactly'] and audio['threadsStopped']
    for stream in audio['streams'].values():
        verify_private(stream)
process158=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio158-private/process158.json'
private[str(process158)]=sha(process158)
for number in [159,160]:
    folder=base/f'astra-start{number}'
    for name in ['PREREG.json','RESULTS.json','TRACE_INDEX.json']:
        paths.add(folder/name)
    verify_private(json.loads((folder/'TRACE_INDEX.json').read_text(encoding='utf-8')))
for number in [161,162,165,168,169]:
    folder=base/f'astra-sidecar{number}'
    for name in ['PREREG.json','RESULTS.json','FAILURE.json','CLEANUP.json','INDEX.json','RUNTIME_CONFIG.json','AUDIO_READY.json','AUDIO_SETUP.json','AUDIO_RESULT.json','STOP_AUDIO']:
        p=folder/name
        if p.is_file():
            paths.add(p)
    for item in json.loads((folder/'INDEX.json').read_text(encoding='utf-8')):
        verify_private(item)
    if number in [168,169]:
        audio=json.loads((folder/'AUDIO_RESULT.json').read_text(encoding='utf-8'))
        assert audio['restoredExactly'] and audio['threadsStopped']
        for stream in audio['streams'].values():
            verify_private(stream)
preload=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar162-private/preload.json'
private[str(preload)]=sha(preload)
for name in ['barge169.json','barge169.npz']:
    p=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar169-private'/name
    private[str(p)]=sha(p)
for folder,names in [('astra-stdin163',['PREREG.json','RESULTS.json']),('astra-analysis167',['PREREG.json','RESULT_INDEX.json']),('astra-analysis170',['PREREG.json','RESULTS.json'])]:
    paths.update(base/folder/name for name in names)
verify_private(json.loads((base/'astra-analysis167/RESULT_INDEX.json').read_text(encoding='utf-8')))
scripts=['c03-prepare158.py','c03-process158.py','c03-start159.py','c03-start160.py','c03-prepare162.py','c03-stdin163.py','c03-prepare165.py','c03-prepare166.py','c03-analyze167.py','c03-prepare168.py','c03-prepare169.py','c03-analyze170.py','c03-pin171.py']
for number in [158,166]:
    scripts.extend(f'c03-{kind}-audio{number}.py' for kind in ['capture','launch'])
for number in [161,162,165,168,169]:
    scripts.extend(f'c03-sidecar{number}{suffix}.py' for suffix in ['', '-entry'])
scripts.extend(['c03-capture168.py','c03-capture169.py'])
paths.update(root/'scratchpad'/name for name in scripts)
paths.update(base/name for name in ['ASTRA-TRAMO-158_161.md','ASTRA-TRAMO-162_165.md','ASTRA-TRAMO-166_168.md'])
report='''# C03 — resultado169–170 y siguiente diagnóstico

Fuente164 permanece intacta y validada. No procesos propios activos.
169 repite el sidecar168 con una observación nueva: al primer barge_in, después
de cancelar y reenviar el evento original, copia una vez los arrays del frame
y el ring. No hace trabajo adicional por frame antes de la decisión.
Driver96694/captura92547 exit0. Cierre57,719s; captura77,03s, restauración exacta
de volumen0/mutedtrue y todos los hilos terminados.

El primer corte ocurre durante el saludo: speaking1,485s, sin error TTS.
Después hay otros eventos wake y una transcripción «Yeah.»; no se ejecutan
operaciones por esas transcripciones en este conductor. El wake heredado usa
un manifiesto sin calibración aprobada: estos eventos no acreditan uso humano.
Las salidas posteriores al snapshot no son controles independientes intactos.

170 analiza los arrays exactos del primer corte. VAD0,8479277; energía limpia
0,00687914; suelo de ruido0,00108865; tercer frame de interrupción. La historia
usada por el guard coincide bit a bit con el ring. Correlación máxima0,3497310,
retardo903muestras (56,44ms): está dentro de la ventana de250ms. Buscar en todo
el ring de4s no obtiene mejor coincidencia. No hay prueba de historia omitida
o desfase fuera de la ventana en ESTE frame. Tampoco se prueba sólo con esto
ausencia de voz cercana. No bajar el umbral0,55 para aprobar este ejemplo.

Siguiente: contrastar por qué AEC y la discriminación de doble habla no separan
la salida propia en este inicio. Partir de astra-analysis170/RESULTS.json y sus
inputs privados fijados. La rama de hipótesis de ampliar ventana/reordenar
historia carece de apoyo en este frame; no repetir los barridos de fases151.
No editar DSP hasta establecer un mecanismo y un contraste que conserve una
interrupción real. C03 sigue abierto: audio, reserva100, promoción, continuidad,
Full final y publicación. Véase HANDOFF.md para el estado compacto vigente.
'''
(base/'ASTRA-TRAMO-169_170.md').write_text(report,encoding='utf-8')
paths.add(base/'ASTRA-TRAMO-169_170.md')
seal={'state':'EN_CURSO','source':164,'utc':datetime.now(timezone.utc).isoformat(),'prior143_157Verified':True,'privateFiles':[{'privatePath':p,'sha256':s} for p,s in sorted(private.items())],'files':[row(p) for p in sorted(paths)]}
with (base/'TRAMO158_170_PINS.json').open('x',encoding='utf-8') as f:
    json.dump(seal,f,indent=2)
assert all(sha(root/item['path'])==item['sha256'] for item in seal['files'])
print(json.dumps({'publicPins':len(paths),'privatePins':len(private),'prior143_157Verified':True}))
