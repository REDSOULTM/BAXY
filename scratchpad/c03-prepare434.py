from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-name-conversation433'
assert not (out/'RESULT.md').exists()
assert '1397 passed in 6.83s' in (out/'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
(out/'RESULT.md').write_text('''# 433 — presentación personal en el lector social existente

La forma declarativa de nombre de NaturalMemoryRequestParser se reconoce ahora
como un acto social completo en _explicit_social_turn_decision. No captura un
nombre para persistirlo ni lo convierte en la identidad del asistente; el modelo
recibe el texto original para conversar. No cambia el catálogo ni añade llamadas.

Después del primer nombre afirmado, los verbos del lector de efectos y las
palabras interrogativas compartidas impiden consumir órdenes o preguntas sin
puntuación. La puntuación interior, guardar, negación, terceros, citas, hipótesis
y consultas sobre Windows conservan su recorrido. La aclaración pendiente se
respeta. Lectura conservadora: no certifica todas las formas posibles de nombres.

- Baseline:13 fallos/104pass/0skips,3,73s; once presentaciones no reconocidas y
  dos recorridos que intentan recuperar candidatos de operaciones.
- Focal:117pass/0skips,0,92s.
- Owners (turn_policy,request_reading,compose_contract,llm_transport):
  1397pass/0skips,6,83s.
- Fast entero verde; build4,23s,0 advertencias/errores.

La composición429 sólo acreditó su propio recorrido de mensaje, no el dispatch
Python actual.434 verificará este cambio en el producto con los ocho turnos432,
sin cambiar otra fuente. Sin Full ni aceptación humana fresca consumida.
''',encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','RESULT.md','baseline.log','focused.log','owners.log','fast.log']]
paths += [root/n for n in ['src/baxy_mind/__main__.py','src/baxy_mind/effect_intent.py','src/baxy_mind/request_reading.py','src/baxy_mind/llm.py','tests/test_turn_policy.py']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
source=(root/'scratchpad/c03-private-product432.py').read_text(encoding='utf-8').replace('432','434')
start=source.index("    'production_verification':")
end=source.index("    'profile_inheritance':",start)
source=source[:start]+'''    'production_verification': 'Source433 whole self-introduction uses existing social-conversation path; source431 generic app clarification and425 cache-ram0/GPU no-mmap retained. Hook observes unchanged HTTP and only adds logging. No source changes while running.',
    'method': 'Same eight synthetic development turns as432 in a new private profile. One source behavior change: self-introduction before PC retrieval. T5 should acknowledge the human name without Windows/memory operations or unrelated clarification; T6 should then reach existing missing-app clarification. T1-T4 and T8 must remain useful; T7 wrong-speaker defect still open and must be judged. Same model/context/precision/sampler/resource guards, no promotion/UI/physical voice/fresh acceptance.',
''' +source[end:]
target=root/'scratchpad/c03-private-product434.py';assert not target.exists();compile(source,str(target),'exec')
target.write_text(source,encoding='utf-8',newline='\n')
hook_dir=root/'scratchpad/c03-owner434-hook';hook_dir.mkdir(exist_ok=False)
hook=(root/'scratchpad/c03-owner432-hook/sitecustomize.py').read_text(encoding='utf-8').replace('432','434')
(hook_dir/'sitecustomize.py').write_text(hook,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8')
    text=text.replace('433 preparado','433 validado;434 preparado')
    text=text.replace('PREREG433. Primero regresiones baseline.',
        '433:baseline13fail/104pass;focal117pass;owners1397pass/0skips6,83s;\n'
        'Fast verde build4,23s/0warnings/errors. RESULT/PINS433. Siguiente:\n'
        '`runtimePython -X utf8 scratchpad/c03-private-product434.py`; mismo432,\n'
        'sólo fuente433. No fuente mientras corre. Recoger resultado individual.')
    p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='433 social self-introduction source validated:117focused/1397owners/0skips, Fast green.',continuation='Run434 same product432 sequence to verify T5 and T6. Memory speaker T7 remains open. No source edits while model runs; full C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('433 recorded;434 prepared')
