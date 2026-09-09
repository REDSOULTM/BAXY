# C03 — el diálogo anterior no es una observación del PC

Tramo 267, 2026-09-07. Fuente implementada y comprobada en la frontera de
serialización. La respuesta nativa y el comportamiento público siguen pendientes.

## Evidencia que originó el cambio

Se inspeccionaron sólo las trazas anteriores de UI263. No se leyeron las nuevas
pruebas del dueño en la instancia 264.

La entrada literal `Tengo en mente que abras steam` llegó al selector con una
shortlist de 28 operaciones que omitía `app.open`. HTTP5 y HTTP7 respondieron
`Steam ya está abierto.` sin llamadas de herramientas. Después, la mente negó
poder abrir Steam, el shell rechazó esa respuesta y llamó al compositor.

HTTP9 contenía literalmente estos datos:

```json
{"kind":"conversation","previousResponse":"Steam ya está abierto."}
```

El mensaje de sistema decía que `situation` era la evidencia disponible del PC.
El compositor respondió `Ya he abierto Steam.`, con `finish_reason=stop`, y la
frase se publicó. No hubo una operación nueva ni una observación nueva en ese
turno. Esto se conserva en `PRUEBAS_UI263.md` y en el registro privado HTTP263.

La ruta exacta es `facts.context` → `previous_answer` →
`visible_situation.previousResponse` en `llm.py`. El origen de diálogo se perdía
al introducirlo en el mismo objeto que contenía la evidencia comprobada.

## Decisión y contraste

Se conserva el contexto como datos JSON y se mueve a
`previous_dialogue_for_references_only`, fuera de `situation`. Ese nombre ya se
usaba en el selector nativo. La serialización compartida lo mantiene tanto en
el primer intento como en los reintentos, sin introducir un turno `assistant`
que el modelo pudiera continuar. El texto sigue escapado y acotado a 320
caracteres; no se elimina el antecedente de preguntas elípticas.

Se hereda la decisión de los paneles 4/5: no reproducir una respuesta antigua
como otro turno del asistente, porque desplazaba el tema de la petición actual.
También se conserva el contrato que separaba hechos de instrucciones del
reintento. Cambia únicamente la procedencia del dato de conversación.

La [documentación oficial de Qwen sobre herramientas](https://qwen.readthedocs.io/en/latest/framework/function_call.html),
consultada el 2026-09-07, distingue la elección propuesta por el modelo de la
ejecución que realiza la aplicación y de los resultados que ésta devuelve.
Esa separación respalda no convertir prosa del asistente en un resultado del
PC. Es un principio de protocolo, no un benchmark de esta cuantización. La
configuración específica de Qwen3.5 sigue siendo la documentada en
`INVESTIGACION_MODELO_C03.md`; no se cambia template, sampler ni sistema.

## Comprobación y límites

- Cinco controles de procedencia fallan antes del cambio: `baseline.log`.
- `pytest tests/test_compose_contract.py -q --tb=short`: **30 pass, 0 skips**.
- `pytest tests/test_compose_contract.py tests/test_llm_transport.py
  tests/test_turn_policy.py -q --tb=short`: **999 pass, 0 skips, 6,00 s**.
- Ruff de `llm.py` y `test_compose_contract.py`: verde.
- `PAYLOAD_COMPARISON.json` compara HTTP9 real con el mensaje que ensambla la
  fuente actual, interceptado antes de enviarlo. Sistema, parámetros, roles,
  petición e instrucciones posteriores son idénticos. `situation` queda como
  `{"kind":"conversation"}`; la misma frase anterior se conserva fuera de él.
- Las pruebas verifican el primer intento, segundo y tercero, contexto de
  observaciones antiguas, preguntas elípticas y una cita con salto de línea que
  no debe fabricar otra línea de evidencia. Las respuestas del transporte de
  pruebas son fixtures, no resultados de inferencia.

**La frase errónea original todavía pasa el validador Python.** En C#,
`ClaimsUnverifiedSuccess` reconoce principalmente aperturas como `listo` o
`done`, y no reconoció la afirmación de HTTP9. Esto queda como fallo de la
frontera pública por resolver; no se ha añadido una lista de frases para ocultar
el caso. Separar los datos elimina una contaminación demostrada, pero no prueba
que el modelo ya responda bien ni que un candidato falso quede bloqueado.

No se lanzó otro modelo ni se utilizó el servidor de la instancia del dueño.
La comparación nativa de los dos paquetes y la regresión del producto quedan
pendientes. No se ejecutó Fast ni Full; el último Fast verde anterior es 262.
No se presenta ninguna prueba de fuente como prueba de UI, voz o aceptación.

## Continuación

Conservar abierta la instancia 264, sin cierre automático, sin reinicio y sin
mensajes del agente. Sus entradas nuevas se guardan para corregir después,
conforme a la instrucción del dueño. El trabajo siguiente usa HTTP263:
resolver la omisión de `app.open` en la shortlist, el rechazo de capacidades y
la aceptación de afirmaciones sin respaldo. Los paquetes antes/después de 267
quedan preparados para la comparación nativa cuando no interfiera con el uso.

C03 permanece íntegro: ocho rutas útiles, reserva humana fresca 100/100,
averías/recuperación, producto compartido con UI y voz física, recursos y
runtime registrados, instalación, continuidad C04–C09, Full verde y publicación
fuera de main. La reparación de este mensaje no sustituye esos requisitos.
