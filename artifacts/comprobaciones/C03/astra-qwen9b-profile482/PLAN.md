# Qwen3.5-9B482 — perfil documentado, calificación acotada

El usuario exige comparar cada modelo con documentación vigente y ajustes efectivos.
La búsqueda por títulos en biblioteca/01_INVENTARIO.md no encuentra una investigación
9B/Qwen3.5; no aplicar recetas2507 ni expedientesGemma de otra arquitectura/hardware.
Se heredan descarga388 y cargas390/441:14 capas en GPU, no-mmap/cache0, alrededor de
4GiB RAM y3GiB VRAM.441 falló tres lecturas españolas con el backend anterior y T0,
no evaluó las confirmaciones actuales ni el perfil general no-thinking del fabricante.

Fuentes2026-09-08: https://huggingface.co/Qwen/Qwen3.5-9B (perfil general explícito,
T.7/p.8/k20/min0/presence1.5/repeat1; enable_thinkingFalse), informe oficial enlazado
https://qwen.ai/blog?id=qwen3.5 (no trasladar benchmarks BF16 a esteGGUF), y reproducción
de mantenedor https://github.com/ggml-org/llama.cpp/pull/28068 (corrige normalización
GDN; afecta qwen35; sus números sobre otros modelos no predicen nuestro resultado).
454/455 comprobaron que b10865 incluye esa corrección;456 no mejoró memoria4B por
backend solo. Reutilizar esa evidencia, sin atribuir una calificación9B a un solofactor.

Mismo contenido fuente466/fixtures465 y controles468, dos semillas predeterminadas.
No instrucciones472–476 ni otras redacciones. 1024tokens/120s permiten inspeccionar
terminación, sin prometer esa latencia ni declarar una respuesta truncada fallo de
capacidad. Se usa el contexto4096 por slot existente, suficiente para estos mensajes
cortos; no se afirma cumplir el contexto largo anunciado ni se modifica RoPE/YaRN.

Antes de cargar deben quedar4900MiB libres; durante la prueba guardas768MiB libres y
3800MiB GPU. No cerrar programas del usuario. Si no cabe, registrar la calificación
incompleta sin inferencia semántica. Una mejora sólo permite integración y medir voz/UI,
no promoción inmediata. No barrido de semillas/modelos a partir de una corrida favorable.
