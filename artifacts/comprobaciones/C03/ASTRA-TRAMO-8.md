# C03 — heredar el checkpoint Instruct-2507

R82, REGISTRO_DE_MANTENIBILIDAD.md 4061–4084, registra 178/180 contratos,
con dos fallos GPU idénticos en arguments-06; las narraciones eran rápidas.
El modelo AWQ convertido del diagnóstico astra-native-qwen es otro archivo.
El prerregistro de adquisición señala la ruta exacta, y allí sigue disponible:
D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/
Qwen3-4B-Instruct-2507-Q4_K_M.gguf; 2497281120 bytes;
SHA 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597.
No se descargó, movió ni registró otro modelo. Bartowski publica una cuantización
distinta, que sólo se consultó; no se confunde con el archivo de R82.

La documentación oficial confirma que este checkpoint sólo usa non-thinking:
https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices.
Se usa su muestreo .7/.8/top-k20/min-p0 en el override diagnóstico, igual que
el contraste 8B. El monitor heredado vigila el árbol y aborta sobre 4096 MiB.

astra-qwen2507-product: 5/6 útiles, 6 publicados; 3497.56 MiB VRAM, 59.83 s.
ADJ escrita. T4 pregunta innecesariamente por AES/RSA; T5 explica en spanglish.
Se generaliza el clasificador de conocimiento existente a explain/explica/
explicame, sin lista de temas y sin quitar la consulta del catálogo. La lectura
compartida incorpora Explain. Cuatro regresiones antes fallan; después las
suites dueñas dan 1246 pass/101 subtests; pins V8/STT 17 pass/1 skip ambiental.
ASTRA-TRAMO-7 conserva la reparación previa de presupuesto. Fast terminó verde
antes de este último ajuste Python: estática y build Release, 0 errores/avisos.
Full permanece reservado al cierre. Estado operativo en CHECKPOINT.md.

No promover hasta revalidar el defecto histórico arguments-06, los demás roles,
las ocho rutas, runtime sin override, UI real y aceptación reservada. Primero
volver al panel de desarrollo heredado con este candidato; no reparar fallos
antiguos de Granite sin ver si también aparecen en él.
