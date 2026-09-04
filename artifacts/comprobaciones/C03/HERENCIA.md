# C03 — herencia Q2/Q4 y causa de «¿Qué hora es?»

Fecha: 2026-09-03. No se atribuye el defecto al modelo ni se añaden
validadores encima del contrato.

## Q2 / Q4 (palabras inventadas)

FunctionGemma midió que Q2 inventaba «fysico»/«lumínar» y rompía la persona;
Q4_K_XL QAT lo corregía (~1,5 GB). Identidad (`00_IDENTIDAD.md` §personalidad)
rechaza subir a Q4 sin medir. El BAXY actual usa Qwen3-4B Q4_K_M. La guarda de
infinitivos inventados ya corre en `compose_user_message`. C03 no cambia la
cuantización: el fallo de la hora no era una palabra inventada.

## Causa del rechazo (contrato, no el modelo)

C02, perfil limpio, journal `system.time` `completed` `verified=true`
`utc=2026-09-03T06:57:52.1829160+00:00` `localUtcOffsetMinutes=-240`. Texto
público: «No pude: no pude encontrarlo.»

1. El Core publica `utc` + `localUtcOffsetMinutes`. El muestreo Goal 06 y
   `compose_visible_defect` exigían `localTime` artificial (`22:10`).
2. El modelo no veía una hora local derivada; copiaba ISO, preguntaba o
   fallaba. La política rechazaba el borrador.
3. `ModelMessageComposer` recuperaba con
   `TurnVisibleFacts.Failure("composition_lost_verified_facts")`: sustituía el
   éxito verificado por un fallo. El prompt de error lista «no pude
   encontrarlo». Esa frase se publicaba.

Reparación: derivar `seen.time` desde `utc`+offset; reintentar los mismos
hechos; no relajar polaridad ni hechos.

## Plantilla `Sigo con {snippet}`

`FirstSignal.FormulateProgress` interpolaba el pedido. Producción: la señal
temprana y el hito pasan por `compose_user_message` / `ModelMessageComposer`
con `cause=acting`. El helper queda para pruebas con
`BypassLlmCompositionForTests`. C07 mide latencia.
