from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-application-clarification431'
assert not (out / 'RESULT.md').exists()
assert '2714 passed in 48.67s' in (out / 'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
(out / 'RESULT.md').write_text('''# 431 — aclaración de aplicación genérica incorporada

Se amplió la rama de aplicación incompleta que ya existía en
`effect_intent.resolve_explicit_clarification_intent`. El objeto genérico completo
usa ClarificationIntent(application), la pregunta redactada por el modelo y la
continuación del producto. No cambia el catálogo, el control de appId, el modelo,
los permisos ni el prompt. No añade otra etapa de inferencia.

La gramática reutiliza los verbos de apertura y el tratamiento de prefijos;
consume la petición completa. Conserva nombres concretos, negación, preguntas,
hipótesis, otro dispositivo y órdenes añadidas fuera de esta rama. No autoriza
una apertura ni escoge una aplicación por el usuario.

Baseline:15 fallos/20 pass/0 skips; doce peticiones no obtienen ClarificationIntent,
tres recorridos entran indebidamente en composición en vez de aclaración.
Primera edición:32 pass/3 fallos por cierre «por favor»; se completó la gramática
del cierre sin cambiar etiquetas ni retirar controles.

- Focal final:35 pass/0 skips,1,20s.
- Owners (test_effect_intent, test_turn_policy, test_current_catalog_review,
  test_catalog_operation_aliases):2714 pass/0 skips,48,67s.
- `scripts/test_source_quality.ps1`: Fast entero verde; build3,86s,
  0 advertencias y 0 errores.

La conducta de producto aún requiere432: repetir los ocho turnos426 con el
mismo perfil diagnóstico en memoria privada nueva. La aceptación humana fresca
no se consume. Full queda para el candidato final de C03.
''', encoding='utf-8', newline='\n')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'baseline.log', 'focused.log',
    'focused-final.log', 'owners.log', 'fast.log']]
paths += [root / n for n in ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/llm.py',
    'src/baxy_mind/__main__.py', 'tests/test_effect_intent.py', 'tests/test_turn_policy.py']]
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in paths}, indent=2) + '\n', newline='\n')
source = (root / 'scratchpad/c03-private-product426.py').read_text(encoding='utf-8')
source = source.replace('426', '432')
start = source.index("    'production_verification':")
end = source.index("    'profile_inheritance':", start)
source = source[:start] + '''    'production_verification': 'Source431 explicit generic-app clarification; source425 cache-ram0 and GPU no-mmap. Hook observes HTTP and adds server verbosity/log only. Same eight product426 development turns; no source changes during run.',
    'method': 'Replay product426 in a new isolated private profile. One behavior change: generic app requests reach the existing explicit missing-application question before retrieval/domain veto. Same model/context/weights/precision/sampler/resource limits. Verify T3/T6 ask which application; T4/T7 still supersede pending public clarification with typed private recall. Record remaining name-introduction and speaker failures honestly. Not fresh acceptance, UI or physical voice.',
''' + source[end:]
source = source.replace("    'manifest_sha256':sha(manifest),", "    'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py']},\n    'manifest_sha256':sha(manifest),")
target = root / 'scratchpad/c03-private-product432.py'
assert not target.exists()
compile(source, str(target), 'exec')
target.write_text(source, encoding='utf-8', newline='\n')
hook_dir = root / 'scratchpad/c03-owner432-hook'
hook_dir.mkdir(exist_ok=False)
hook = (root / 'scratchpad/c03-owner426-hook/sitecustomize.py').read_text(encoding='utf-8').replace('426', '432')
(hook_dir / 'sitecustomize.py').write_text(hook, encoding='utf-8', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    text = text.replace('431 preparado, fuente vigente 425', '431 validado; producto432 preparado')
    text = text.replace('431 reutilizará', '431 ya reutiliza')
    text = text.replace('Primero regresiones negativas y positivas, baseline, luego fuente y owners/Fast.',
        'Baseline15fail/20pass; focal35pass; owners2714pass/0skips48,67s; Fast verde\n'
        'build3,86s/0warnings/errors. RESULT/PINS431. Siguiente: ejecutar\n'
        '`runtimePython -X utf8 scratchpad/c03-private-product432.py`; mismo426 con\n'
        'fuente431. No fuente durante corrida; recoger terminales/payloads/recursos.')
    path.write_text(text, encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='431 app clarification source validated:35focused/2714owners/0skips, Fast green.',
    continuation='Run432 same eight product426 turns with source431. No source edits while running. Full C03 active; self-introduction and memory speaker remain open.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('431 recorded; 432 prepared')
