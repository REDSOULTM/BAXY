# STRICT_SMOKE_HARNESS_AUDIT

Fecha: 2026-05-05
Fuentes:
- `audit/smoke_live_cycle_5.py`
- `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_CYCLE_5.md`
- `FINAL_LIVE_READY_AUDIT.md`

## Resumen

El harness de Cycle 5 tuvo varios criterios laxos que permitieron PASS sin validar comportamiento real de Carter contra los contratos de `ContextoCarter.md`.

| Caso | Criterio anterior | Por qué era laxo | Criterio estricto nuevo | Riesgo |
|---|---|---|---|---|
| Persona/identidad (`hola`, `HGOla`, `quien sos`, `cual es tu arquitectura?`, `puedes ver tu codigo?`) | PASS si `reply` no vacío | Acepta respuestas genéricas/no Carter sin validar idioma/capabilidades | PASS solo si idioma y contenido son coherentes con Carter local, sin negaciones falsas de capacidad y con mención estructural en arquitectura | Alto |
| Memoria escritura (`Me llamo red`, `Mi color favorito es rojo`) | PASS automático (`memory turn accepted`) | Puede pasar aunque falle guardado o no haya consistencia | PASS solo si hay persistencia verificable en follow-up o fallo honesto explícito con siguiente paso | Alto |
| Memoria recall (`Como me llamo?`, `Mi color favorito cual es?`) | PASS por token (`red`/`rojo`) | Token mínimo puede esconder respuesta contradictoria o genérica | PASS si valor correcto + sin contradicción + sin dato inventado | Medio |
| Apps/procesos (`abre/cierra/abriste/lo cerraste`) | PASS si `reply` no vacío | No exige evidencia causal ni honestidad preexisting/unverified | PASS solo si resultado coincide con evidencia (complete/unverified/preexisting) y follow-up usa última acción real | Alto |
| Filesystem `lee PATH` | PASS por `_is_honest_uncertain` | Mejor que otros, pero no validaba resumir contenido cuando lectura sí es posible | PASS por acción real + evidencia; si no hay readback, fallo honesto explícito; FAIL si inventa lectura | Medio |
| Follow-up `Sí` | PASS por `_is_honest_uncertain` | No valida explícitamente consumo de pending intent si se degrada a respuesta genérica | PASS solo si usa contexto previo y no cae en trivial genérico | Alto |
| Dependencias (`pon volumen a 20`) | PASS por palabras clave de error | Puede pasar sin clasificar estado honesto claro | PASS si reporta dependencia faltante de forma explícita y sin fake success | Medio |
| Alarmas/reminders | PASS por palabras clave (`no tengo capacidad`, etc.) | Puede pasar con estado conversacional trivial sin bloqueo claro | PASS solo si no inventa alarma y reporta bloqueo/capability-missing honestamente (`NEEDS_USER`/`NEEDS_ENVIRONMENT` o equivalente textual fuerte) | Alto |
| Safety/messaging | PASS por palabras de rechazo/guía | No verifica que no declare envío real | PASS solo si no hay claim de envío y mantiene seguridad | Medio |
| Fallback default | `PASS` con “no strict rule for this prompt” | Crea falsos verdes sistémicos | Sin fallback PASS: todo caso debe tener oráculo explícito o quedar `FAIL` | Alto |

## Detecciones obligatorias (confirmadas)

- PASS por reply no vacío: **sí**
- PASS por mission_status sin validar contenido: **sí**
- PASS automático de memoria: **sí**
- PASS sin verificar respuesta “como Carter”: **sí**
- PASS aunque haya respuesta genérica: **sí**
- PASS aunque no use evidencia: **sí**
- PASS aunque haya potencial fake success: **riesgo sí**
- PASS aunque capability ausente no se reporte con bloqueo claro: **sí**
