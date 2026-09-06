# Transferencia C03 a Opus 5 High — 2026-09-05

Diagnóstico del WIP, HEAD `5f572ee`. No modifica producto, runtime, tests de
Grok, matriz ni checkpoint. Goal listo en
[C03_OPUS5_HIGH](../../../documentacion/sprints/Sprints%20comprobación/C03_OPUS5_HIGH.md).
Los números de línea corresponden al [snapshot](source-snapshot.json).

## Avance real y alcance pendiente

Granite 4.2 3B Q4_K_M está registrado: el meta de `disc-68/events.jsonl`
identifica GGUF e0406663… y override nulo. Se conservan reparación utc+offset,
recuperación con los mismos hechos, separación de varias rutas y corrección de
la traducción española que antes exigía hola. No procede empezar de cero.

Estado vivo: `05_ESTADO_Y_CONTINUACION.md`, disc-68, sin Full ni 100/100.
`cien-35/paired.txt` informa 93 publicados/7 agotamientos; v18 ya se usó para
corregir. `disc-68/paired.txt` informa 15/1. Ninguna cifra es exactitud semántica.

Ejemplos publicados en disc-68:

| Turno | Pedido | Respuesta | Defecto |
|---|---|---|---|
| 003 | qué no haces, una frase | No abras programas. | Orden al usuario; no responde sus límites. |
| 006 | Dime la hora y el volumen. | …el estado demute es falso. | Redacción defectuosa pese al terminal. |
| 007 | post a letter to Eris | Please post a letter to Eris. | Devuelve la tarea al usuario. |
| 009 | Good afternoon | composition_failed | Falta respuesta. |
| 011 | Hi again | What specific action would you like… | Aclaración de tarea ante un saludo. |
| 015 | define DNS in one sentence | DNS es un sistema… | Idioma incorrecto. |

Cien-35 además conserva fallos de seguimiento (004, 014, 035, 044, 054, 074,
084, 094), metadiscurso (018, 051), contenido ajeno (037, 086) y respuestas de
capacidad incorrectas (022, 072). No se adjudica una tasa total aquí; basta para
demostrar que «resolver los siete agotamientos» no completa C03.

## Causas verificadas por código y reproducción pura

**Idioma contradictorio.** `llm.py:325–428` cuenta palabras de dos listas; empate
significa español. Good afternoon/Good morning/define DNS no contienen tokens
ingleses de esa lista. `_compose_situation_payload:3006` pone hola y
`_compose_user_content:3088` elimina el pedido original para saludos. En cambio,
`UserMessagePolicy.cs:730–750` reconoce Good afternoon como inglés y
`:449–450` rechaza un saludo español. El compositor recibe instrucciones que
su siguiente validador desaprueba. Reproducido en [pure-probes.json](pure-probes.json),
sin inferencia, red ni efectos sobre Windows. No identifica el borrador exacto
de disc-68, porque esa traza no lo conserva; sí demuestra el desacuerdo causal.

**Una heurística borra peticiones.** `_looks_like_greeting_ask:3229–3280` acepta
cualquier inicio hey/hi/hello menor de 28 caracteres. «hey, close Paint» y
«hey, what can you do» entran en esa rama y pierden el texto original del
usuario en el payload. El clasificador C# no usa el mismo contrato.

**Presentación que añade hechos.** `_compose_situation_payload:2932–3050`
descarta kind/polarity y crea effect=closed/window=true a partir del verbo close
con polarity=success, sin exigir observación. Red con observación pero sin
online/connected se convierte en online=false. Son contraejemplos de función
reproducidos, no prueba de que esos estados concretos hayan causado un efecto
físico en cien-35. La frontera debe conservar desconocido/negación/verificación.

**Acumulación y prosa fija.** Frente al HEAD publicado, UserMessagePolicy creció
de 1.446 a 2.419 líneas y llm.py de 8.100 a 9.035; no se atribuye todo a una sola
noche. El tamaño solo no demuestra un defecto. Sí lo hacen los prompts literales
`GRANITE_OOC_*:272–286`, `greeting=hola/hi` y los reescritores de
`:8721–8836`, incluido `close_clip` que inserta «ventana está cerrada».
El compositor aplica siete transformaciones antes de evaluar/capturar el texto.
Corregir código que fabrica frases exige conservar la garantía de hechos, no
eliminar validadores indiscriminadamente.

**Coste por reintentos mal dirigidos.** `compose_user_message:8161–9035` puede
realizar tres intentos de generación en su ruta normal. ModelMessageComposer
`:102–156` repite compose con los mismos hechos si C# rechaza: hasta seis intentos
en esa ruta, antes de considerar otras llamadas. Un idioma contradictorio puede
hacer inútiles esos intentos. No se midió aquí el consumo total de la cuenta Grok.

**Continuidad a investigar, no causa única afirmada.** MainWindowViewModel
`:1807–1816` entrega historia a DecideTurnAsync, pero `:2154–2195` puede degradar
una conversación a un evento sin contenido; compose recibe el último pedido y
hechos, no automáticamente el tema anterior. Los seguimientos publicados fallan.
Hace falta trazar qué ruta tomó cada uno antes de cambiar memoria o el modelo.

## Por qué el verde local no cerró la misión

`tests/test_goal06_voice.py -q`: **11 passed en 0,23 s**, con el Python 3.12 del
runtime. El test en líneas 1572–1577 acepta Good afternoon escrito a mano: no
comprueba que el payload que llega a Granite esté en inglés. Se necesita una
regresión de frontera, no más listas de ejemplos aceptados por un filtro.

El [diagnóstico existente de compose](../../../src/baxy_mind/llm.py:1527) sólo
guarda causa, bytes/hash y restricciones; no ID de turno, borrador bruto o
finish_reason. Tras los reescritores se pierde información causal. Instrumentar
con entradas sintéticas y correlación evita otras decenas de corridas ciegas.

R07: `tramo-c-r07-reject-5/events.jsonl` registra PID 23880 y perfil reject;
restore-5 registra PID 19720 y otro perfil. No prueba recuperación en una misma
sesión. `tramo-c-ui-4.txt` sólo recoge dos arranques con título BAXY; no prueba
que se enviara un mensaje ni cómo se presentó. El estado «Tramo C verde» debe
reconciliarse con esos límites, conservando las pruebas útiles existentes.

## Transferencia y coste

Primero idioma/intención/payload, luego conservación de hechos y continuidad;
después integración y aceptación fresca. Conserva Granite y el WIP útil. El
goal permite sustituir las piezas defectuosas dentro de C03, sin reconstrucción
general, sin subagentes y sin más pruebas de cien mientras falle el diagnóstico.
La auditoría anterior mejoró el protocolo, pero las reglas de parada no evitaron
el bucle: esta transferencia aporta reproducciones concretas y ownership.

La [guía oficial de Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
recomienda alcance explícito, limitar delegación y calibrar extensión; advierte
que instrucciones redundantes de comprobación pueden aumentar el coste. Se
mantienen High/thinking y los gates obligatorios del producto, sin rituales de
revisión duplicados. El [anuncio oficial](https://www.anthropic.com/news/claude-opus-5)
confirma el modelo solicitado. No se promete que cambiar de desarrollador baste.

Validación de esta entrega: diagnóstico puro reproducido, owner Python 11/11 y
enlaces/hashes de archivos comprobados. No se ejecutó otra campaña de producto
ni Full del WIP: su cierre y sus pruebas de aceptación son el encargo de Opus.
El Full verde de la auditoría anterior corresponde a otra base, no se hereda como
certificación de este código. Esta entrega es un diagnóstico y goal, no C03 cerrado.
