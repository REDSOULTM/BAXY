# C02 — Inventario G01 / X03 con procedencia ejecutable

HEAD de arranque: `384493cfe2aeb91d67e0406a9fc1c5a67e14127a` (C01 recapture).
C01 unpublished: `d6500f8`, `384493c`. C02 no los reescribe.
Goal 01 commit (G02.01): `7092c1a goal 01: el mapa de la herencia, y las dos piezas que estorbaban para leerlo`.

Fuente viva del mapa: `documentacion/herencia/00_MAPA.md` (Goal 01, 2026-08-16) + §11 09.5.12.
Adaptadores: `documentacion/herencia/D_ADAPTADORES_POR_APP.md`.
09.5.9: `documentacion/herencia/09_5_9_DECIDIR_HERENCIA.md` (campaña transplant vacía).

## G01.01 — cinco intentos

| # | Carpeta | Qué se propuso | Por qué se abandonó |
|---|---|---|---|
| 1 | Carter OS AI v1–v3 | Agente local, watchdog VRAM, UIA | Estados falsos por visión ciega |
| 2 | carter_v5 | ≤16 tools, prompt recortado | Acumulación: 3 routers, agent.py 1397 líneas |
| 3 | Probando Gemma 4 | Voz, router, computer-use, accesibilidad | Suma de componentes, no un release |
| 4 | FunctionGemma | 270M fine-tune tool-calls | No conversa; catálogo cocido en pesos |
| 5 | BAXY | .NET contratos/kernel/journal | No se abandonó: base de Definitivo |

JRVS fuera de linaje. Procedencia: `00_MAPA.md` §1; no se re-ejecutó 09.5.

## G01.02 — qué funciona hoy (ejecutado en C02, no heredado de 2026-08-16)

| Pieza | Comprobación 2026-09-03 | Veredicto |
|---|---|---|
| Runtime registrado | `mind-runtime-v1.json` schema `baxy-mind-runtime-v1`; GGUF Qwen3-4B-Q4_K_M `7485fe6f…` en `D:\BAXYRuntime`; Python `0b471133…` en `%LOCALAPPDATA%\BAXYRuntime\python` | Funciona, declarado |
| llama-server b9980 | SHA `38a9d28e…` copiado a `%LOCALAPPDATA%\BAXYRuntime\assets\llama-b9980-cuda12.4` (mismo hash que el hermano). Registro ya no usa `Programacion\BAXY` | Funciona sin hermano |
| STT Parakeet | `stt_dir` `~\.gemma4\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8`, hash `5a70e086…` | Presente |
| Wake | manifiesto `%LOCALAPPDATA%\BAXYRuntime\assets\wake\baxy-wakeword-v1.json` `fefb9517…` | Presente |
| FieldUi sello | `MainWindowShellContractTests` constante `0F6DCDA5…`, 38 ficheros, decisión escrita en `ORIGIN.md` (10.2.5) | Cuadra |
| MissionEngine | un constructor público | Cuadra |
| Compuerta | se mide en Full de esta tanda, no se heredan 3986/8792 ni 3865/8511 | Pendiente de Full |

## G01.03 / G01.04 — hereda / no hereda

Hereda (con lo que faltaba para traerlo, hecho o no):

- Wake `baxy.onnx` → manifiesto propio (ya en BAXYRuntime).
- STT Parakeet → `assets.manifest.json`.
- Diseño 3 modos accesibilidad → reimplementar .NET (C08; no C02).
- OCR `CaptureVisionAdapter` + scripts UIA → ya en este repo; falta `spa.traineddata` (APLAZADOS, C08/07).
- Capa .NET + catálogo tipado.

No hereda (mecanismo):

- Gemma-4-E2B como decisor (thinking 200–400 tokens; Goal 03 eligió Qwen3-4B).
- FunctionGemma 270M caller (inventa nombres; catálogo en pesos).
- Q2_K_XL (no más rápido, degenera).
- agent.py / tres routers / redirects ad hoc.
- Adaptadores por app como destino (lista G01.08; sustituye el 07).
- checkpoints/captures vacíos; 13 GGUF de iteración FunctionGemma.
- Rechazos 09.5.9: functiongemma-270m-ft, qwen-vl, ollama-runtime, auto_approve, soak-24h-as-requirement, gemma-native-audio.

## G01.05 — cuatro herencias obligatorias

| Herencia | Estado | Evidencia |
|---|---|---|
| Accesibilidad | existía completa (Probando Gemma 4, 3 modos medidos 2026-05-26); en el producto actual el diseño se hereda, el código Python no | `00_MAPA.md` §3A; C08 es el owner de voz/FAR |
| UIA → OCR → visión | existe a medias: OCR C# (`CaptureVisionAdapter`) + UIA en 3 ps1; no hay política de cascada ni modelo de visión | `D_ADAPTADORES_POR_APP.md`; Goal 07 |
| Catálogo consolidado 16 tools | existe la medición y dice lo contrario: 75,93 % → 62,96 % | `00_MAPA.md` §6; no se trasplanta |
| Prosa/cuantización Q2 vs Q4 | existía; sondeo 6 prompts rechaza Q2; Qwen3-4B-Q4_K_M es el decisor vivo | `00_MAPA.md` §3D; manifiesto GGUF |

Inventario ≠ integración. Integración C02: runtime declarado, descomposición ViewModel, sellos.

## G01.06 — preguntas vigentes vs caducadas

Vigente: fracaso por acumulación; harness 540 con falsos positivos; consolidar no es gratis; encoder 67 vs 31 equivalente; persona sin FT; modos accesibilidad separados; UIA→OCR→visión vs coordenadas.

Caducado: torneo STT 2026; comparativa LLM E2B/E4B (ya Qwen3); auditoría 10 competidores; perfiles VRAM 4 GB sin GPU física; −68 % tokens.

## G01.07 — cuatro soluciones de comprensión

1. Router semántico Tool2Vec (FunctionGemma) holdout 0,9521.
2. Planner completo (no ejecutable standalone).
3. FunctionGemma 270M (rechazado).
4. Política viva `turn.decide` + e5-small (producción; Goal 03/03C midieron techo).

## G01.08 — adaptadores por app

Lista fichero por fichero vigente en `D_ADAPTADORES_POR_APP.md`. C02 no sustituye: es Goal 07. C02 comprueba que la lista sigue nombrando los ficheros en `src/Baxy.Providers.Windows/External/` y `Applications/`.

## X03 / 09.5

Terminales: `reusar_exacto` / `adaptar` / `conservar_actual` / `medir_antes` / `rechazar`.
Campaña transplant: `total=0`. Cero lotes. Decisiones 09.5.9: conservar_actual 61, rechazar 35.
Fuentes omitidas justificadas: GGUF/datasets/checkpoints dispersos de Probando Gemma 4 (hashes not invented); JRVS; Probando schemas.
No se relanzó 09.5.2–09.5.12.
