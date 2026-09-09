# Dependencia local de evidencia semántica restaurada

2026-09-06, Goal-c03. No es una recalibración ni una medición de acierto de C03.

El encoder E5 estaba instalado. Faltaba el corpus calibrado, ignorado por Git:
`tests/data/turn_evidence_runtime.v1.jsonl`. El resolver seleccionaba el corpus
histórico alternativo; construía7383registros, pero la política era incompatible.
Esto no prueba por sí solo por qué cada decisión anterior fue léxica.

Se recuperó del repositorio anterior BAXY, sin modificarlo:

- Fuente: `D:/Perfil/Escritorio/ETC/Programacion/BAXY/tests/data/turn_evidence_runtime.v1.jsonl`.
- Destino: `D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/tests/data/turn_evidence_runtime.v1.jsonl`.
- Tamaño:8421417bytes;25156registros elegibles.
- SHA-256: `8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680`.
- Coincide con runtime_source_sha256 de la política vigente y la restauración R234.

Para reproducir en esta máquina, comprobar esa huella en la fuente antes de copiar
al destino ausente y volver a comprobarla después. No sustituir un archivo existente
sin revisar su identidad. No versionar ni distribuir este corpus privado como parte
del producto; el entorno instalado conserva sus requisitos propios de privacidad.

La caché global ya guardaba vectores compatibles. Se validaron mediante el cargador
del producto: esquema, identidad del encoder, SHA del corpus y de vectores, matriz
finita y número de filas. Se guardó la misma caché bajo la clave que corresponde al
path actual. Detalle: encoder-cache-inheritance.json. El original se conserva.
Sin esa caché el servicio puede reconstruirla localmente; la caché no es un modelo
nuevo ni modifica la calibración.

Validación antes: c03-encoder-service-probe.log, ready19,05s,7383registros,
policy=incompatible. Después: c03-encoder-service-cache-inherited.log,
ready20,09s,25156registros,policy=loaded/compatible. Ambos en scratchpad/.
La comprobación del servicio aislado se complementó con corpus-warm: las diez
decisiones registradas raw_attempt usan retrieval=semantic. Adjudicación y espera
de preparación en astra-qwen2507-corpus-warm/. Sí demuestra promoción integrada;
no acredita por sí sola una respuesta útil, pantalla/audio físico ni cierre C03.
