# 454 — correcciones posteriores a la estable; b10865 justificado para medir

Comparación oficial b10809…b10865:56 commits completos; COMMITS.json conserva
hashes, fechas y enlaces. No equivale a afirmar que todo lo nuevo mejora BAXY.

- [28068](https://github.com/ggml-org/llama.cpp/pull/28068),6 de septiembre:
  corrige la normalización GDN de qwen35 y otras arquitecturas, colocando epsilon
  dentro de la raíz como la referencia Qwen/FLA. Afecta al cálculo del modelo
  actual; los resultados publicados en otros tamaños no prueban una mejora en
  Qwen3.5-4B/BAXY. Es evidencia nueva suficiente para comparar b10865.
- [28475](https://github.com/ggml-org/llama.cpp/pull/28475): corrige carreras
  detectadas por racecheck en MUL_MAT_ID. No atribuir a ella la memoria privada
  de un modelo denso sin comprobar que usa la ruta afectada.
- [27870](https://github.com/ggml-org/llama.cpp/pull/27870): barrera divergente
  de FlashAttention f16. La reproducción usa otro hardware y KVf16; BAXY usa
  KVq8_0. No se afirma que nuestro kernel concreto tuviese ese fallo.
- [26705](https://github.com/ggml-org/llama.cpp/pull/26705): desempaquetado
  Q4_K/Q5_K más barato y prefetch condicionado por hardware. Hay reproducciones
  y medidas de usuarios, pero en GPUs distintas. Medir aquí sin trasladar sus
  porcentajes ni asumir mejora de calidad.
- [28208](https://github.com/ggml-org/llama.cpp/pull/28208): escribe capas
  recurrentes explícitas en conversión. Resuelve stacks no uniformes; no exige
  reconvertir el Qwen3.5-4B estándar de patrón uniforme sólo por este cambio.
- [28302](https://github.com/ggml-org/llama.cpp/pull/28302): conserva checkpoints
  recientes en prompts cortos antes de alcanzar la capacidad. Relevante para
  reutilización de contexto de modelos recurrentes, no una garantía semántica.

455 descarga el paquete oficial Windows/CUDA12.4 junto a las versiones anteriores.
No se cambia el manifest.453 continúa la medición thinking de b10809; los tiempos
son diagnósticos, con auditoría/descarga concurrente, no benchmarks aislados.
Después se comparan inputs/perfiles efectivos iguales con b10865. No repetir
prompts rechazados ni cambiar varias capas para atribuir una mejora al motor.
