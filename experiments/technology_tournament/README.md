# Cortes verticales del torneo tecnológico

Este directorio contiene contendientes desechables y equivalentes. No es el
producto BAXY ni una fuente de decisiones por sí sola. Las reglas congeladas
están en `artifacts/technology_tournament/protocol.json` y los casos comunes en
`cases.json`.

Cada implementación debe aceptar el mismo JSONL UTF-8, ofrecer modo de proceso
único y modo persistente, limitar todos los efectos al workspace entregado,
mantener un journal idempotente y devolver el mismo contrato semántico. Los
tests del harness, no el propio contendiente, deciden si un caso pasó.

Los resultados generados viven bajo `artifacts/technology_tournament/raw/` e
incluyen comandos, hashes y muestras individuales. No se edita el protocolo
después de iniciar la medición; cualquier protocolo posterior recibe otro ID.
