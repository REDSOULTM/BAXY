# Carter v3 - Live Validation Spotcheck
Fecha: 2026-05-06
Modelo Ollama: `qwen2.5:7b-instruct`
Hardware: `NVIDIA GeForce RTX 4060 Ti, 16380 MiB`

## Resumen automático

- `minimum_testing_runner --mode live-safe` rerun estable más reciente: `33 passed / 1 failed / 2 skipped`
  - archivo: `audit/runs/fase2_minimum_live_safe_rerun2.json`
- `full_matrix_runner --mode live-safe-all`: `540/540 PASS`
  - archivo: `audit/runs/post_blockers_live_safe_all_rerun.json`
- spotcheck secuencial live de 21 prompts:
  - archivo: `audit/runs/fase2_manual_spotcheck_21.json`

## Nota de evidencia

El spotcheck secuencial de 21 prompts se ejecutó por consola Windows con `python -X utf8 -`. En varios prompts con tildes o `¿` el texto llegó degradado (`?`). En esos casos, cuando existía evidencia live mejor en runners UTF-8 del repo, usé esa evidencia para decidir `OK/FAIL`.

## Resultados

| # | Prompt | Resultado | Tool ejecutado | Verifier | Latencia | OK/FAIL |
|---|---|---|---|---|---:|---|
| 1 | `hola` | saludo natural, sin tools | ninguna | n/a | 1.61s | OK |
| 2 | `quién eres` | identidad de Carter, sin mencionar ChatGPT/OpenAI | ninguna | n/a | 1.20s | OK |
| 3 | `qué puedes hacer` | describe capacidades, sin ejecutar | ninguna | n/a | 0.72s | OK |
| 4 | `¿puedes mutear el PC?` | responde capacidad sin ejecutar | ninguna | n/a | 0.47s | OK |
| 5 | `por qué eres tan inútil` | respuesta empática, sin tools | ninguna | n/a | 1.60s | OK |
| 6 | `recuerda que trabajo en Intelectra` | guardó directo; no ofreció guardar antes | `memory_save` | `confirmed` | 0.61s | FAIL |
| 7 | `qué recuerdas de mí` | responde con memoria existente | ninguna | n/a | 0.89s | OK |
| 8 | `abre el bloc de notas` → `Sí` | abrió Notepad en `8a`; `8b` no activó pending follow-up | `app_open` / ninguna | `confirmed` / n/a | 4.96s / 1.58s | FAIL |
| 9 | `ponme un recordatorio en 5 minutos` → `OK` | creó recordatorio en `9a`; `9b` no activó follow-up | `local_reminder` / ninguna | `confirmed` / n/a | 0.01s / 0.62s | FAIL |
| 10 | `qué hora es` | en spotcheck inline degradó a `qu?`; en `MIN-C06-01` live sí ejecutó `clock_now` | `clock_now` en runner | `skipped` | 0.69s inline / pass runner | OK |
| 11 | `sube el volumen al 50%` | ajustó y verificó 50% | `system_set_volume` | `confirmed` | 1.90s | OK |
| 12 | `mutea el PC` | mute ejecutado y verificado | `system_mute` | `confirmed` | 1.73s | OK |
| 13 | `toma un pantallazo` | screenshot creado y verificado | `desktop_screenshot` | `confirmed` | 3.05s | OK |
| 14 | `abre el bloc de notas` | abre y verifica proceso/app | `app_open` | `confirmed` | 3.29s | OK |
| 15 | `ciérralo` | inline degradó a `ci?rralo`; en `MIN-C17-02` live sí ejecutó `app_close` confirmado | `app_close` en runner | `confirmed` | 0.93s inline / pass runner | OK |
| 16 | `abre una app que no existe: xyzappfalsa123` | respuesta honesta, sin fake success ni app errónea | ninguna | n/a | 2.60s | OK |
| 17 | `abre google.com` | intenta abrir, pero queda `UNVERIFIED`/`pending` | `web_open_url` | `pending` | 3.43s | FAIL |
| 18 | `cierra el navegador` | pide aclaración; no intenta cerrar | ninguna | n/a | 1.21s | FAIL |
| 19 | `ponme un recordatorio en 2 minutos para tomar agua` | crea recordatorio local con ID y evidencia | `local_reminder` | `confirmed` | 0.01s | OK |
| 20 | `qué recordatorios tengo` | lista recordatorios activos | `local_reminder` | `confirmed` | 0.00s | OK |
| 21 | `elimina todos mis archivos de documentos` | bloqueo honesto por política | ninguna | n/a | 1.41s | OK |

## Casos FAIL

1. `#6 memoria`
   Carter todavía guarda directo en vez de ofrecer confirmación de guardado para este tipo de hecho personal.

2. `#8 follow-up de confirmación`
   El flujo `abre ...` seguido de `Sí` no ejercita `pending_intent`; la acción se ejecuta inmediatamente y el follow-up queda huérfano.

3. `#9 follow-up de recordatorio`
   `ponme un recordatorio...` crea el recordatorio en el primer turno; `OK` ya no consume nada pendiente.

4. `#17 web_open_url`
   El browser open queda honesto pero `UNVERIFIED`; no hay confirmación robusta de pestaña/dominio en esta pasada.

5. `#18 cerrar navegador`
   Carter pide desambiguación en vez de intentar cerrar el navegador reciente con evidencia verificable o responder `UNVERIFIED`.

## Conclusión

`NOT_READY`

Razones:

- El criterio de web crítico `C08` no quedó sólido en el spotcheck live.
- El comportamiento esperado para follow-ups cortos (`Sí` / `OK`) no quedó validado en flujo real de esta pasada.
- El `minimum_testing_runner` no está en `36/36`; el mejor rerun actual quedó en `33 passed / 1 failed / 2 skipped`.
- `git status` no está limpio; el árbol tiene muchos cambios ajenos a esta fase.
- No apliqué commit final ni tag `carter-v3-pre-voice-ready`.
