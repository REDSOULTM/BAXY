# 456 — b10865 cambia respuestas, no resuelve el bloqueo

44 respuestas, todas stop; sin errores ni cortes. Templates idénticos a449.

| Modelo | Perfil | Semilla | Útiles/11 | Respuestas iguales a b10809 |
|---|---|---:|---:|---:|
| qwen35-4b | greedy | None | 6/11 | 8/11 |
| qwen35-4b | documented | 0 | 4/11 | 5/11 |
| qwen35-4b | documented | 17 | 5/11 | 6/11 |
| gemma-published | greedy | None | 8/11 | 11/11 |

La corrección GDN no puede atribuirse aisladamente: el backend incorpora otros
cambios. Sí está justificada técnicamente; no demuestra resolver nuestro problema.
Gemma sirve como control de otra arquitectura: las once respuestas son idénticas.
No se promueve runtime. No seguir cambiando versiones para buscar un acierto.
Perfiles y respuestas completas en PREREG/ADJUDICATION/COMPARISON; fuente436.
