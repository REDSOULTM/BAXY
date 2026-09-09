"""Record362 and the pending integrated replay363."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-native-context362'
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
pins = {}
for name in ['src/baxy_mind/llm.py', 'tests/test_turn_policy.py']:
    with (root / name).open('rb') as stream:
        pins[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    (out / ('PREVIOUS_' + name)).write_text(text, encoding='utf-8')
    text = text.replace('checkpoint360/361', 'checkpoint362/363')
    text = text.replace('producto360 terminó con regresión. Diagnóstico361 en curso, handle34499.',
        '360 y361 cerrados; fuente362 pasa dueñas/Fast. Producto363 preparado.')
    text = text.replace('journal sólo enable/save, no escritura de archivo.', 'journal sólo memory.status/enable/save, no escritura de archivo.')
    start = text.index('361 en curso handle34499:')
    end = text.index('## Resto íntegro pendiente')
    text = text[:start] + '''361 completó9/11→11/11 selecciones correctas con roles nativos y mismo texto,
modelosampling/sistema/catálogo. Las divergencias reales36013y31 se reprodujeron
y desaparecen en la alternativa. La variante sintética ambas-identidades ahora
pasa en baseline también: variabilidad declarada; seed no garantiza igualdad.
GPU3175,56MiB/RAM4599,84MiB18,34s aislado. REVIEW361 completo; registro intacto.

362 fuente última: selector nativo systempropio + historial user/assistant ya
saneado/acotado + petición actual user literal. Reemplaza JSON del contexto,
sin prompt/catálogo/modelo/límite nuevo. Baseline4fail; dueñas Python1091pass0skip
5,32s, Fast verde build1,40s0warnings/errors. RESULT/PINS362 escritos. Sin Full.
No declarar362 integrado hasta producto;359 solo había regresado y se conserva
la evidencia. 3162507conotrocontexto no respalda este cambio;361Qwen3.5sí.

Siguiente: ejecutar scratchpad/c03-product363.py (preparado). Mismos siete pedidos,
perfil nuevo, Qwen3.5 diagnóstico360, sólo362 diferente. Registrar handle, recoger
cada respuesta y journal; no editar fuente mientras corre. BAXY manual cerrado.
El sondeo secundario de catálogo sigue existiendo: no se modificó sin otra prueba.

''' + text[end:]
    path.write_text(text, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='362 native dialogue replaces quoted context after361 improves9/11to11/11;1091pass/Fast1.40s.360 regression preserved; no integrated acceptance yet.',
    continuation='Run prepared product363; same seven/model360, source362 only. All prior handles closed; full C03 remains active.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('362 recorded and pinned;363 next.')
