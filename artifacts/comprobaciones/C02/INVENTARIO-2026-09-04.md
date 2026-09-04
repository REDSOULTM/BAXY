# Inventario C02 revalidado 2026-09-04

Hechos históricos: [INVENTARIO.md](INVENTARIO.md) (mapa 01 + 09.5.9). No se relanzó 09.5.
HEAD de esta medición: `f9391c1`. Fuente C03 posterior a `7d28421` no borra el mapa.

## G01.01–G01.04, G01.06–G01.07

Sin delta de fuentes. Cinco intentos, hereda/rechaza y soluciones de comprensión
siguen en `documentacion/herencia/00_MAPA.md`. JRVS fuera de linaje.

## G01.02 — qué funciona hoy (ejecutado)

Runtime vivo 2026-09-04: [RUNTIME-2026-09-04.md](RUNTIME-2026-09-04.md). Hashes
de python/GGUF/llama/STT/wake/TTS coinciden con el manifiesto. Cero ruta al hermano.
Dueños: [OWNERS-2026-09-04.md](OWNERS-2026-09-04.md).

## G01.05 — cuatro herencias

Sin cambio de estado respecto de INVENTARIO.md: accesibilidad (diseño heredado,
código Python no); UIA→OCR→visión a medias (`CaptureVisionAdapter` + 3 ps1 UIA);
catálogo 16 tools (la medición dice que consolidar empeoró); prosa/cuantización
(Q2 rechazado; Qwen3-4B-Q4_K_M vivo).

## G01.08 — adaptadores

Los 21 ficheros de `D_ADAPTADORES_POR_APP.md` existen en este HEAD. C02 no los
sustituye (Goal 07).

## G01.09 — descomposición

`MissionEngine`: un constructor público (registry, journal, options opcional).
`MindPlanSession` y `MemoryTurnSession` siguen extraídos. El ViewModel no define
`HandlePendingMindPlanAsync` ni `HandlePendingMemoryConfirmationAsync`.
C03 añadió política de voz al ViewModel; no reintrodujo el plan/memoria.
Pruebas del comportamiento extraído: 26 Integration + 17 Kernel, verdes.

## X03 / 09.5

`documentacion/herencia/09_5_9_DECIDIR_HERENCIA.md` vigente. Transplant `total=0`.
No se omiten fuentes nuevas sin justificar.
