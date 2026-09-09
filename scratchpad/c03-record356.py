"""Persist356 evidence and the next product replay, without closing C03."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-requested-greeting356'
fast = (out / 'fast.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in fast
result = '''# 356 — el saludo solicitado atraviesa ambas comprobaciones de eco

351/355 generaron Hola Emmanuel para dime hola emmanuel. La App descartaba el
borrador correcto como restates_request. El compositor Python contenía la misma
comparación: descartó Hola Lina como extra_claim incluso al recuperar un borrador
con un nombre ajeno. Se ajusta esa comparación en ambos dueños, sin cambiar modelo,
prompts, respuestas generadas, lectura global de saludos ni las demás guardas.

El resto de una petición tras dime/decime/tell me puede coincidir con el saludo
pedido. Una petición informativa copiada, incluso tras hola, conserva el veto.
No se incorporan nombres particulares ni prosa visible fija.

- Baseline App: 4 fallos, 4 pass, 0 skips; cuatro saludos válidos rechazados.
- Focal App: 8 pass, 0 fallos, 0 skips, 1 s, política y publicación real.
- Focal Python: 9 pass, 0 fallos, 0 skips, 0,43 s, incluido retry.
- Dueñas Python: 1044 pass, 0 fallos, 0 skips, 5,14 s.
- Dueñas App: 225 pass, 0 fallos, 0 skips, 15 s.
- Fast: verde; build18,00s, 0 advertencias y 0 errores. No Full durante reparación.

Comandos: runtime Python -m pytest tests/test_turn_policy.py
tests/test_compose_contract.py -q -x --tb=short; dotnet test
tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter
FullyQualifiedName~C03FactPreservationTests|FullyQualifiedName~Goal06VisibleVoiceTests|FullyQualifiedName~PlannerAppBoundaryTests|FullyQualifiedName~VoiceFeedbackTests;
.\\scripts\\test_source_quality.ps1.

El baseline App inicial con un stub que eludía Python está conservado y explicado
en PREREG.md: baseline-wrong-owner.log no es la referencia correcta de App.
El rechazo Python de Hola Lina, abrí Spotify por unmentioned_name comprueba ese
borrador, no un detector semántico completo de afirmaciones de efectos.

Siguiente: producto357, mismos siete pedidos/modelo/perfil aislado355; comprobar
saludo publicado, cada mensaje y journal. No aceptación humana fresca, UI gráfica,
voz física ni promoción de Qwen3.5. C03 íntegro sigue abierto.
'''
(out / 'RESULT.md').write_text(result, encoding='utf-8')
pins = {}
for name in ['src/Baxy.App/UserMessagePolicy.cs', 'src/baxy_mind/llm.py',
             'tests/Baxy.Integration.Tests/C03FactPreservationTests.cs', 'tests/test_compose_contract.py']:
    with (root / name).open('rb') as stream:
        pins[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    previous = path.read_text(encoding='utf-8')
    (out / ('PREVIOUS_' + name)).write_text(previous, encoding='utf-8')
    updated = previous.replace('checkpoint355', 'checkpoint356')
    updated = updated.replace('producto355 terminó; todos los handles de pruebas cerrados.',
        'fuente356 validada; producto357 preparado y pendiente de ejecutar. Handles de pruebas cerrados.')
    start = updated.index('## Siguiente acción concreta')
    end = updated.index('## Resto íntegro pendiente')
    updated = updated[:start] + '''## Fuente356 y siguiente acción concreta

App y compositor Python corrigen el veto al saludo exacto solicitado después de
dime/decime/tell me. El eco de una petición informativa sigue rechazado. No otro
prompt, modelo ni nombres fijos. Baseline App4fail4pass; focal App8pass y Python9pass;
dueñas App225pass0skip15s, Python1044pass0skip5,14s, Fast verde. RESULT/PINS356 escritos.
No Full. Producto355 sigue siendo la última evidencia integrada:6/7,0silencios.

Ejecutar scratchpad/c03-product357.py (ya preparado). Mismos siete pedidos y
Qwen3.5 diagnóstico de355, perfil nuevo deshabilitado, sólo356 diferente. Registrar
handle y recoger cada mensaje/journal; no editar fuente mientras corre.
Después estudiar selección de system.identity para quien soy en contexto personal:
native selector355 request20 trunca otra vez prior_messages a6, perdiendo la
declaración del usuario. _bounded_history ya conserva hasta el límite vigente.
Hipótesis por medir, no arreglada. Investigación de modelo/formato vigente y
Carter_v2 LLM_CONTEXT_MEMORY_REPORT R1–R4 reutilizables; no más etiquetas de origen.

''' + updated[end:]
    path.write_text(updated, encoding='utf-8')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='356: requested greeting echo checks repaired in App/Python, App225pass/Python1044pass/Fast green; full C03 active.',
    continuation='Run prepared product357, compare to355; then measure native selector history truncation for contextual identity. No Full during repair.')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('356 recorded; product357 next, complete C03 remains active.')
