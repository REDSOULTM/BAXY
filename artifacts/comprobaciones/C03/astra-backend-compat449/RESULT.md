# 449 — compatibilidad comprobada; todavía sin inferencia

Cuatro arranques terminados y cerrados: Qwen3.5-4B y Gemma publicado, cada uno
con b9980 y b10809. Sin errores ni cortes de recursos. Tres slots de 4096 tokens
por instancia. El render del mismo payload438 es idéntico entre backends para
cada modelo; huellas en RESULTS.json. Esto no acredita calidad de respuestas.

Los parámetros de muestreo efectivos conservan valores y orden. Cambian campos
inactivos: dry_penalty_last_n pasa de -1 a 64, con dry_multiplier=0 en ambos;
aparecen adaptive_target=-1 y adaptive_decay=0.9, sin sampler adaptive activo.
El diagnóstico450 conserva el payload real T0, max256, thinking desactivado.
Después se comparan perfiles documentados por modelo, exigidos por el dueño.

| Modelo | Backend | RAM pico MiB | VRAM pico MiB | Arranque y lecturas s |
|---|---|---:|---:|---:|
| Qwen3.5-4B | b9980 | 958.95 | 3159.56 | 6.000 |
| Qwen3.5-4B | b10809 | 965.74 | 3168.54 | 3.719 |
| Gemma publicado | b9980 | 2647.13 | 1669.57 | 6.360 |
| Gemma publicado | b10809 | 2638.96 | 1663.79 | 5.937 |

Sólo carga y consultas de propiedades/plantilla: no inferir ahorro del producto
entero ni velocidad de generación de esta tabla. Registro sin cambios; fuente436.
Backend oficial descargado y verificado448 en carpeta separada, no promovido.
