# 418 — la ruta privada precede a una aclaración pública obsoleta

MindShellEndToEndTests nuevos reproducen cuatro solicitudes ES/EN de recall/status
tras «Haz eso»: antes sumaban dos decisiones públicas y no llegaban al journal
privado. El baseline conserva además un fallo de fixture al leer el journal con
FileShare incorrecto; no se presenta como cuatro fallos puros de producto.
El primer postcambio sólo falló por ese lector y por exigir un outbox existente
cuando no había ninguna operación. Se corrigieron los fixtures, sin relajar
la conducta: lectura compartida y ausencia explícita del outbox en cancelación.
Seis pruebas finales pasan (26 s, cero skips), sin cambios adicionales de producto.

MainWindowViewModel consume el resultado tipado de memoria antes de reutilizar
la aclaración pública. NoRoute y AskToSave conservan el flujo mental: un nombre
dicho en conversación no autoriza escritura. Las solicitudes reconocidas siguen
por MemoryTurnSession y mantienen confirmación exacta, cifrado y causas reales.
También se prueba solicitud de nombre faltante→cancelación sin operación.
No nueva lista de frases, caché de nombres, router ni compositor.

Herencia: MemoryTurnSession.TryResolveSaveInput ya cede ante una ruta privada
independiente; MindClarificationPolicy diferencia petición completa y fragmento.
La biblioteca gemma4-agent/.../02_router/research/7_nlu.md:24–34 propone contratos
de slots, pero su límite arbitrario de turnos no se adopta. La documentación
[Rasa Forms](https://legacy-docs-oss.rasa.com/docs/rasa/forms/) distingue entradas
que completan un slot de interrupciones que cambian el objetivo (consulta
2026-09-08). Se reutiliza aquí el contrato privado ya reconocido; no se importa
el framework ni se añade un clasificador. La adopción se decide con tests locales
y producto, no con métricas ajenas.

Regresión de owners en curso; Fast y producto419 todavía pendientes. No Full
durante reparación. Última fuente completamente validada antes de418:416.
