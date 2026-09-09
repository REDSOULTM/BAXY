"""Pin359 and record the pending360 replay before launching it separately."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-selector-history359'
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
pins = {}
for name in ['src/baxy_mind/llm.py', 'tests/test_turn_policy.py']:
    with (root / name).open('rb') as stream:
        pins[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    previous = path.read_text(encoding='utf-8')
    (out / ('PREVIOUS_' + name)).write_text(previous, encoding='utf-8')
    text = previous.replace('checkpoint357/358', 'checkpoint359/360')
    text = text.replace('producto357 terminó; selector358 en curso, handle89363. Pruebas356 cerradas.',
        'producto357 y selector358 terminados. Fuente359 validada, producto360 preparado.')
    start = text.index('Selector358 en curso, handle89363: recoger.')
    end = text.index('## Resto íntegro pendiente')
    text = text[:start] + '''358 terminó: selección6/8→7/8 conservando historial acotado completo; variante
sintética ambas identidades aún escogeWindows, fallo pendiente. REVIEW358 escrito.
GPU3175,56MiB/RAM3315,59MiB aislado, registro intacto. No efectos ni voz/UI.
359 fuente última: retira sólo [-6:] del selector nativo. El sanitizador conserva
12mensajes/6000chars y roles user/assistant; no tocar modelo/prompts/catálogo.
Baseline2fail1pass; dueñas turn_policy+compose+transport1091pass0skip5,32s;
Fast verde build1,72s0warnings/errors. RESULT/PINS escritos. Handles cerrados.

Siguiente: ejecutar scratchpad/c03-product360.py, ya preparado. Mismos siete
pedidos/modelo357, perfil nuevo; sólo359 diferente. Registrar handle. No editar
fuente mientras corre; comprobar todos los mensajes, especialmente quien soy,
y journal. 100frescos/UI/voz/runtime/resto de rutas siguen pendientes.
La variante sintética de ambas identidades358 sigue abierta aunque producto360
pasara el literal completo del dueño. Preservar esa evidencia; no estrechar C03.
Herencia R1–R4 de Carter_v2, experimentos316/317/65 y docs de modelo/formato ya
consultados. No repetir eliminación de historia ni cambios de roles rechazados.

''' + text[end:]
    path.write_text(text, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='359 removes only redundant native selector history cut;1091pass/Fast1.72s.358 improves6/8to7/8, both-identity variant still fails.',
    continuation='Run prepared product360 and inspect every message/journal; full C03 active, not just seven-case panel.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('359 pinned/checkpointed;360 next.')
