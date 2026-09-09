from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-coordinate-queries545'
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
note = '''

## Tramo545 — preguntas coordinadas, validación dueña verde

Se amplía el lector existente para conservar todas las lecturas de preguntas coordinadas en español e inglés, incluidas «decime la hora y cuánta batería tengo» y «How much battery is left, and what time is it?». Conserva los scopes combinados CPU/RAM y sistema/RAM, negación, otro dispositivo, texto citado y catálogo incompleto. Sin respuestas visibles fijas ni backend nuevo.

Test-first:6 fallos/103 pass; focal final109 pass. Dueñas finales:3699 pass y121 subtests,0 skips,56,21s. Declaraciones STT:12 pass/1 skip ambiental,1,46s; ese skip no es validación de audio. Fast verde, Release21,23s,0 advertencias/errores. Fuente actual399e73203f5eafca73a8573083703cd2e10756b2c8544e992c8c40cb24b80138/403 archivos; sellos históricos intactos. Producto546 pendiente: no adjudicar todavía H0079. Full final pendiente.

Encuesta6 cubiertos/736 abiertos/0 no aplicables. E5 ONNX544 descargado y verificado, sin adopción; comparación547 preparada y aún no ejecutada. Goal API confirmado active; bloqueo anterior resuelto por autorización536, ninguna decisión pendiente del dueño.
'''
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream: stream.write(note)
handoff=base/'HANDOFF.md'
old=handoff.read_text(encoding='utf-8')
handoff.write_text('# Handoff C03 — 545\n\n'+note.split('## Tramo545 — preguntas coordinadas, validación dueña verde\n\n')[1]+'\nSiguiente: producto546 y comparación547, secuenciales para no contaminar recursos. Antecedentes y fallos abiertos:\n\n'+old,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json'
state=json.loads(path.read_text(encoding='utf-8'))
state.update(goalStatus='active',confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='545: coordinated questions; 3699 pass +121 subtests; Fast green; product546 pending.',goalStatusNote='get_goal confirms active after owner authorization; no owner decision pending.')
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
(out/'PINS.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
attributes=root/'.gitattributes'
with attributes.open('a',encoding='utf-8',newline='\n') as stream:
    for name in ('astra-coordinate-queries545','astra-e5-assets544'):
        stream.write('/artifacts/comprobaciones/C03/'+name+'/** -text\n')
