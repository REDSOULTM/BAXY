# El cuello de botella de C03 está medido: 504 de 742 literales no llegan al reconocedor

Esto no es una hipótesis. Son dos números de la misma tanda y un tercero del repositorio entero.

## Los tres números

**En SYSTEM1028, el camino de decisión predice el resultado mejor que cualquier otra variable.**
De los 31 casos, los que resolvió el reconocedor determinista (`decision_path: explicit_effects`)
cumplieron **9 de 14**; los que cayeron al modelo (`decision_path: model`) cumplieron **3 de 15**.
Correlación por `request_id` entre `turn-audit.jsonl` y el panel sellado, no por orden supuesto.

**El reconocedor cubre hoy 238 de los 742 literales de la encuesta; 504 caen al modelo.**
Medido con `scratchpad/c03-recogniser-baseline.py`, que ejecuta `resolve_explicit_effects` —una
función pura— sobre cada literal del registro con las 170 operaciones que declara el catálogo tipado.
Sin GPU, sin producto, sin tanda: segundos.

**Consecuencia.** Cada literal que pasa del camino del modelo al determinista multiplica por tres su
probabilidad de responder bien. Ahí está el rendimiento, y no en ejecutar más paneles anchos sobre el
estado actual.

## Por qué el modelo falla cuando le llega el turno

No es que razone mal: es que a menudo **no recibe la operación correcta**. En H0146 «cuánto espacio
queda en C» la lista de candidatos que se le ofreció tenía 28 operaciones y **`system.status` no
estaba entre ellas**. Con eso, concluir que la petición está fuera de catálogo es la conclusión
correcta a partir de un material equivocado, y el compositor es fiel a esa conclusión:
`situation = {"kind":"failure","cause":"out_of_catalog"}`, publicado como «No puedo dar información
sobre el espacio disponible en la partición C». Mientras tanto, en la misma tanda, H0442 y dos
variantes leyeron el disco sin problema por el camino determinista.

## Qué le falta al reconocedor, caso por caso, medido con sondas puras

| Literal | `_system_status_domain` | scopes | `resolve_explicit_effects` | Lo que falta |
|---|---|---|---|---|
| H0146 «cuánto espacio queda en C» | False | — | None | el patrón de disco no reconoce «espacio … en C» con letra de unidad |
| H0532 «tirame cuánta memoria tengo» | True | memory | None | la cabeza «tirame» no está entre las de observación |
| H0076 «… Usa Python.» | False | memory, os | None | la instrucción final desarma el dominio |
| dev-05 «¿El equipo está enchufado y cargando…?» | False | — | None | estado de carga sin el sustantivo «batería» |
| dev-08 «Read the current GPU utilization…» | True | gpu | None | la cabeza inglesa «read» no está aceptada |
| H0422 / dev-11 identidad | False | — | None | `system.identity` no tiene reconocedor en esta ruta |

Los que sí funcionan comparten forma: H0442, H0539, H0655, H0508, H0037, H0114, dev-01, dev-02,
dev-04, dev-07. La diferencia entre unos y otros es léxica, no conceptual.

## La mitad temporal: causa localizada y reparación **no** adoptada

`_direct_current_time_request` (`effect_intent.py:525`) es un `re.fullmatch` **por diseño**: reconoce
«una petición entera del reloj local». Por eso devuelve False en las cuatro peticiones compuestas de
fecha más medida, y el reloj nunca entra en la resolución. Además, en el camino de composición
multidominio (`:8309` en adelante) **no existe ningún patrón de dominio para `system.time`**, así que
el par no puede formarse aunque se autorice: añadir sólo
`frozenset(("system.status", "system.time"))` al conjunto de pares permitidos es **inerte**, medido,
cero literales cambiados.

Probé la reparación completa —patrón de dominio para el reloj presente y local, con el mismo criterio
de modificadores que `_direct_current_time_request`, más el par autorizado— y el resultado fue:

```
delta -1, changed_literals 2
H0106: ['system.status'] -> ['system.time', 'system.status']   (lo buscado)
H0589: ['system.status'] -> None                                (regresión)
```

H0106 gana exactamente lo que le faltaba, y **ningún otro de los 742 literales se movió**, así que el
patrón está bien acotado y no arrastra fechas de evento ni tiempo de CPU. Pero H0589 pierde su
resolución y caería al camino del modelo, que es el del 20 %. Cambiar una respuesta mala por otra
mala no es una mejora, así que **no se adopta**: `effect_intent.py` está revertido a su base exacta
`3bb83dc8f0c8736c86d402d0faf656915044a9089b8b27b9b9a430b36365cade` y el diff contra la línea base es
cero.

Lo que falta para adoptarla es una sola cosa concreta: por qué H0589, con «fecha y hora actual» más
disco, deja de resolver cuando aparecen dos dominios, cuando el par está autorizado. La resolución
actual de esos cuatro casos no viene de la composición multidominio sino del resolutor estricto que
retorna en `effect_intent.py:13811`; ahí hay que mirar, con `sys.settrace` acotado al módulo, que es
como se localizó esto.

## El instrumento

`scratchpad/c03-recogniser-baseline.py`, con su línea base en
`%LOCALAPPDATA%/BAXY/C03-recogniser-baseline.json` (238 resueltos, 504 no).

```
python scratchpad/c03-recogniser-baseline.py write   <salida.json>
python scratchpad/c03-recogniser-baseline.py compare <baseline.json>
```

`compare` enumera cada literal cuyas operaciones resueltas cambiaron. Un movimiento fuera del
conjunto que la reparación declaraba es una regresión y se ve **antes** de gastar una tanda en
descubrirla. Es el bucle que faltaba: hasta ahora cada hipótesis costaba una tanda de GPU y una
adjudicación; ahora cuesta segundos, y la tanda se reserva para confirmar en el producto lo que la
sonda ya dejó verde.

Lo que este instrumento **no** dice: que la respuesta sea veraz. Resolver la operación correcta es
condición necesaria y no suficiente; en 1028 cinco casos llegaron al reconocedor y aun así fallaron,
por etiquetar mal la memoria disponible, por inventar la fecha que faltaba y por agotar reintentos.
La cobertura se sigue acreditando sólo con literal ejecutado, respuesta útil y fiel, y dos variantes
pertinentes en pie.
