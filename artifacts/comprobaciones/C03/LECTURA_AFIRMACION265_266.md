# C03 — afirmación y petición independiente, tramos 265–266

Estado: reparación del lector validada por sus pruebas; C03 continúa. No se ha
probado esta fuente nueva en una ejecución del modelo ni en la UI.

## Causa comprobada

Se reutilizaron tres entradas literales del dueño ya consumidas en UI260/263,
con el catálogo Core262 congelado. Son desarrollo, no reserva. No se ejecutó
ninguna operación ni se envió una petición al modelo para este diagnóstico.

| Entrada literal | Lectura anterior | Lectura después de 266 |
|---|---|---|
| `abre steam` | Una `app.open`, identidad Steam | Igual |
| `Tengo en mente que abras steam` | Sin intención explícita ni identidad extraída | Igual; continúa pendiente |
| `Si, abre steam` | Dos efectos mínimos: `si` sin resolver y `abre steam` como `app.open` | Una `app.open`, identidad Steam, sin veto compuesto |

La hipótesis de que `_catalog_unavailable_turn_decision` causaba el tercer rechazo
queda descartada: devuelve `None` en las tres entradas. La primera transformación
incorrecta comprobada es la cardinalidad de `unresolved_compound_contract`.
El guardia real `apply_operation_domain_grounding_veto` conserva después de 266
la operación con su evidencia `steam`; esto no equivale a ejecución del Core.

Evidencia: `astra-boundaries265/PREREG.json`, `RESULT.json` y
`astra-acknowledgement266/REPLAY_FINAL.json`. El catálogo con nombres del equipo
permanece privado; su huella está en la preregistración.

## Herencia, contraste y cambio

Se reutiliza la normalización compartida de `effect_intent`, el vocabulario de
cabezas de acción de su lector de cláusulas y `_negative_action_forms`. Esta
última ya distingue las formas de prohibición españolas de sus imperativos
afirmativos. No se cambia el selector nativo ni su prompt.

La investigación heredada de `INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md`
distingue selección semántica de formato y documenta vetos que degradaban una
selección correcta. Aquí el fallo ocurre antes de inferencia: cambiar el modelo
no repararía esa cardinalidad. La [RAE, entrada «sí»](https://www.rae.es/dpd/s%C3%AD),
consultada el 2026-09-07, distingue la respuesta afirmativa de una petición nueva.
Esta fuente lingüística orienta la hipótesis; las garantías provienen de la
reproducción y las pruebas locales.

La normalización retira una afirmación inicial separada por puntuación sólo si
la sigue una cabeza de petición ya reconocida o una prohibición reconocida.
Una afirmación sola, una condición o el contenido literal de una orden de
escritura conservan su lectura. El resolvedor de identidad de aplicaciones pasa
por esa misma normalización, como ya lo hacía el lector de efectos. No hay una
excepción por Steam, una operación nueva ni una respuesta visible fija.

La primera variante retiraba también la afirmación de `Sí, sí, te oigo`, lo que
rompía una prueba social existente. Se descartó esa aplicación indiscriminada.
Una variante intermedia no reconocía `abras` detrás de `no`; se sustituyó esa
duplicación por `_negative_action_forms`. Los logs de ambas variantes se
conservan. La fuente final reutiliza la gramática existente de prohibiciones.

## Validación

- Mismas 41 pruebas de frontera contra el módulo congelado anterior: **21 fallos,
  20 aprobadas**, `baseline-matched.log`. La carga aislada del módulo no sustituyó
  ningún fichero de la aplicación abierta.
- Fuente final: `python -m pytest tests/test_effect_intent.py
  tests/test_compound_missions.py tests/test_turn_policy.py -q --tb=short`:
  **2.597 aprobadas, 0 skips, 54,36 s**, `owner-suites-final.log`.
- `ruff check src/baxy_mind/effect_intent.py tests/test_effect_intent.py`: verde.
- `REPLAY_FINAL.json`: mismos tres literales, mismo catálogo, módulo anterior y
  actual; conserva el caso simple y corrige la frontera de la afirmación.

Los controles añadidos son regresión construida, explícitamente separados de la
reserva humana. La prueba inicial tuvo un error de colección por el nombre
reservado `request`; se corrigió. También se corrigió una expectativa del test:
el lector ya delegaba la cláusula mixta `no abras Steam y abre Orion`, por lo que
se comprueba conservar su contrato completo. El replay de la línea base usa
exactamente los tests finales. No hay skips, umbrales relajados ni tests borrados
para ocultar un fallo. Todos los logs se mantienen.

No se repitió Full. Fast integrado queda pendiente sobre esta fuente; su build
no se lanzó contra los binarios de la instancia que el dueño está usando. El
último Fast verde anterior es 262 y no se presenta como validación de 266.

## Continuación y procesos

La instancia 264 pertenece a las pruebas manuales del dueño: PID 84328,
createTime 1788820609.3516054, launcher 100540. Sigue viva, sin watchdog ni cierre
automático. No cerrar, reiniciar, inyectar pruebas ni analizar ahora sus mensajes
nuevos: el dueño pidió guardarlos para corregir después. Trazas privadas en
`%LOCALAPPDATA%/BAXY/C03-owner264-private/`. No se cambió el volumen.

Los procesos de pruebas 71908 y 68055 terminaron; el segundo pasó completo.
No hay otra corrida de medición pendiente.

Siguiente 267: continuar con HTTP263, sin leer las pruebas nuevas de 264. La
frase larga pierde `app.open` en shortlist28; el compositor fallback toma
`facts.context` y lo publica como `previousResponse` en `llm.py`, pese a no haber
una operación nueva. Revisar conjuntamente la selección que pierde la petición
y la condición que admite la prosa final. La consulta de capacidades de UI263
también sigue pendiente, con truncamiento nativo y agotamiento de composición.

El alcance completo permanece: ocho rutas útiles, reserva humana fresca
congelada y adjudicada 100/100, averías y recuperación, UI/voz física/recursos,
runtime promovido y reproducible, instalación, continuidad C04–C09, Full verde y
publicación fuera de main. Ninguno queda sustituido por estas pruebas del lector.
