# Goal 09.5.9 — Decisión de herencia

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json`](../../artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json).
Asignación 1:1 de las 9.268 tarjetas 09.5.2–09.5.4:
[`artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json`](../../artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json).
Campaña:
[`artifacts/goal095/campaigns/transplant.json`](../../artifacts/goal095/campaigns/transplant.json).

09.5.10 ejecutó la campaña `transplant` (cola vacía). Siguiente prompt humano:
[`../sprints/09.5.11A_REVALIDAR_01_03C.md`](../sprints/09.5.11A_REVALIDAR_01_03C.md).

Inventario desde tarjetas 09.5.2–09.5.4 y síntesis 09.5.5–09.5.8. No se leyeron
cuerpos de `biblioteca/` ni se recorrieron árboles fuente.

## Terminales (sólo estos cinco)

`reusar_exacto` · `adaptar` · `conservar_actual` · `medir_antes` · `rechazar`.
Cero `review` / `pendiente`. Las etiquetas 09.5.5 `conservar`/`medir`/`reemplazar_candidato`
y 09.5.8 `reusar`/`medir` no quedan como terminales vivos.

## Campaña `transplant`

**Vacía.** `pending=0` `claimed=0` `complete=0` `total=0`.

09.5.5–09.5.8 no hallaron pieza histórica que gane al vivo en conducta, pruebas,
recursos y arquitectura a la vez. Unload-on-idle y arranque frío son mediciones
de **producto** del Goal 10.2 sobre el keep-warm/process_lifecycle vigentes, no
un `vram_manager`/Ollama/`ui_field` que transplantar. Los GGUF/datasets/checkpoints
dispersos de Probando Gemma 4 no se nombran (hashes **not invented**). Cada lote
habría tenido que retirar el mecanismo vivo en el mismo cambio; no hay tal lote.

## Qué se conserva (vivo)

Decisor Qwen3-4B-Q4_K_M, e5-small, llama.cpp b9980 sidecar, catálogo tipado 169+1,
puerta léxica, verificador de identidad, pila Goal 09 (wake/STT/TTS/VAD),
providers Windows, MissionEngine, ConfirmationAuthority, journal HMAC, FieldUi
ADR-0008, Setup NativeAOT, process_lifecycle.

09.5.8 `medir` en carga/descarga y arranque se mapea a `conservar_actual`: la
pieza histórica es incomparable y no es candidata.

## Rechazos protegidos (no reentran a `transplant`)

| Id | Por qué |
|---|---|
| `functiongemma-270m-ft` | No conversa; catálogo cocido en pesos; abstención 0/3 primer split |
| `qwen-vl` | R-023 inventó juegos; visual-diff = falso éxito |
| `ollama-runtime` | Servicio Windows / cloud / sesgo tools=; ADR-0005 sidecar |
| `auto_approve` | Rompe confirmación ligada a `invocationId` |
| `soak-24h-as-requirement` | No es listón de 10.2 ni de Identidad |
| `gemma-native-audio` | llama-server no rutea `input_audio`; Parakeet es el oído |

## Cobertura

- 100/100 responsabilidades 09.5.5–09.5.8 asignadas una vez.
- 9.268/9.268 tarjetas 09.5.2–09.5.4 asignadas una vez (citadas → fila de síntesis;
  resto → residual docs / código extranjero / predecesor BAXY / evidencia).
- Campañas 09.5.2–09.5.4 siguen 25/25, 477/477, 132/132, `pending=0` `claimed=0`.

Pesos, runtime, catálogo, FieldUi `dist` y Setup vivos: **no se tocaron**.
Cero estado del arte añadido.
