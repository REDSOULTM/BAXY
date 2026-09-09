# 462 — lectura de embeddings bajo demanda ahorra RAM en Gemma

Mismas12composiciones y13inferencias que460; único cambio `--lazy-mode on`.
RAM del árbol:2832,90→1005,51MiB (2,77→0,98GiB). VRAM1695,79→1692,18MiB.
Las12respuestas finales son idénticas y conservan el número de intentos.
45,859s frente49,859s totales; una pareja no acredita una mejora universal de
velocidad. No corte de recursos; manifest intacto; fuente436 sin editar.
Baseline10/11 y11/11 con único valor público obligatorio, igual que460.

El código exacto5266f24da marca el PLE de Gemma como TENSOR_READ_LAZY.
Auto no aplica a esta tabla menor de4GiB; on la mapea bajo demanda incluso
cuando los demás pesos usan no-mmap. Windows completa la inferencia; recursos
muestran el ahorro efectivo. El conjunto de páginas puede crecer con vocabulario
más variado: no es un máximo universal ni una prueba de voz o producto completo.

Herencia: dossier12_OPT_GEMMA4_DOSSIER.md, líneas23–27, E4B/16GBGPU anterior
al mecanismo. Fuente425 no-mmap probado conQwen, no óptimo universal deGemma.
[PR27794](https://github.com/ggml-org/llama.cpp/pull/27794) introduce lectura
perezosa y reporta coste de rendimiento en E4B; [PR27837](https://github.com/ggml-org/llama.cpp/pull/27837)
separa esa decisión del modo de carga general. Los datos del autor no se
trasladan a estaRTX3060 ni al checkpointBAXY. Consulta2026-09-08, fuente exacta
archivada en esta carpeta; método/prereg y mediciones locales conservados.

Siguiente463: mismos8turnos de producto461, sumando exclusivamente lazy-mode on.
No promoción hasta integración y regresión. C03 continúa íntegro.
