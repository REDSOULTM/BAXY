from pathlib import Path

base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
p = base / 'CHECKPOINT.md'
s = p.read_text(encoding='utf-8').replace(
    'de producto. Tras retirar, validación final activa8528 y Fast14130: recogerlos.',
    'de producto. Tras retirar, validación final8528terminal0:2609pass,0skip,47,85s.\nFast14130terminal0:verde, build0errores/avisos. Ruff y diffcheck verdes.'
).replace('Sin procesos LLM propios vivos; main intacto, cambios sin commit/push.',
          'Sin procesos propios pendientes; main intacto, cambios sin commit/push.')
p.write_text(s, encoding='utf-8')
with (base/'PRUEBAS_PRESUPUESTO_Y_NEGACION_C03.md').open('a', encoding='utf-8') as f:
    f.write('''
## Validación final de la tanda

Tras retirar la variante de cláusulas:

`python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py tests/test_effect_intent.py tests/test_c03_request_preservation.py -q`
→ 2609 pass, 0 skips, 47,85 s; proceso8528 terminado0.

`scripts/test_source_quality.ps1` → Fast verde, compilación sin errores ni avisos;
proceso14130 terminado0. Ruff y git diff --check pasan. Logs:
scratchpad/c03-knowledge-final-owner.log y c03-knowledge-final-fast.log.
No se ejecutó Full: desarrollo y aceptación todavía pendientes.
''')
(base/'HANDOFF.md').write_text('''# Handoff — C03 — 2026-09-06 — tramo 39

Objetivo: C03 completo conforme a C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md.
Estado EN_CURSO/ACTIVE, sin bloqueo externo. Rama Goal-c03; HEAD
2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Cambios acumulados sin commit/push;
main y cambios ajenos conservados. Sin procesos propios pendientes ni subagentes.
El tramo32del resumen del goal es histórico; manda CHECKPOINT.md vigente39.

## Hecho y evidencia
llm.py: conocimiento256tokens y política de una frase salvo petición de detalle/
formato. Misma variante medida38; no nuevo modelo/sampling ni otros roles.
PRUEBAS_PRESUPUESTO_Y_NEGACION_C03.md:23literales,10sondas+13producto.
astra-knowledge-budget-integrated8:5/8útiles,76,11s,GPU3499,56MiB. Detalle termina,
agua/Steam/audio/hora bien; aire pide aclaración desde primaria, SSID añade falsa
analogía con contraseña, negación social+hora falla. No es reserva ni %delgoal.

## Decisión descartada
No reponer el parche de «cualquier cláusula directa» en resolve_explicit_effects.
El separador ya funciona; unresolved_compound_contract conserva negación global
y cuenta I don't mind como cláusula de acción desconocida. El parche pasó2454
tests existentes pero falló1/6controles nuevos; astra-clause-scope5 sólo2/5útiles
e inventó14horas para «no abras Steam, dime la hora». Retirado, evidencia conservada.
No añadir una excepción textual ni presentar el reconocimiento aislado como arreglo.

## Siguiente acción
Revisar el contrato semántico completo de negación/cláusulas, empezando por
unresolved_compound_contract y su aplicación en __main__.py. Para aire, la primaria
devuelve mode=clarify antes del chat; no arreglarlo cambiando de nuevo prosa.
SSID sigue pendiente. El pool aún requiere autoría/exposición/contexto:560textos
traces,115Carter_v1,16archivos.gemma4; hay posibles pruebas automáticas/audio de fondo.
Detalle privado: LOCALAPPDATA/BAXY/C03-real-user-pool-20260906/session_source_candidates.json.

## Validación y cierre pendiente
python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py
tests/test_effect_intent.py tests/test_c03_request_preservation.py -q
→2609pass,0skip,47,85s. scripts/test_source_quality.ps1→Fastverde,build0errores/avisos.
Ruff/diffcheck pasan. Logs scratchpad/c03-knowledge-final-{owner,fast}.log.
Quedan desarrollo,100frescos/ocho rutas,averías/recuperación,UI/recursos finales,
contratos posteriores afectados,Full finalverde y publicación propia fuera main.

## Runtime
Qwen3-4B-Instruct-2507Q4_K_M base; llama.cppb9980;KVq8,4096×3slots;total≤4096MiB.
Registro LOCALAPPDATA/BAXYRuntime/mind-runtime-v1.json SHA
13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.
Python LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
''', encoding='utf-8')
print('Final validation and handoff recorded. C03 remains active.')
