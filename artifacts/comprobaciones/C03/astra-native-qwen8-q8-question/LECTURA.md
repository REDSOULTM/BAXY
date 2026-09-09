# Qwen3-8B, pregunta conservada — diagnóstico 2026-09-06

12 casos conocidos, un brazo, seed y sampler conservados. Fuente de producto
sin editar mientras corría Full; el adaptador diagnóstico sustituye sólo
«Explain the concept in one short sentence» por responder la pregunta real.
La fuente actual también contiene el prompt común nuevo respecto del ensayo
qwen8-q8 anterior. No atribuir todas las diferencias a una única frase.

| Caso | Veredicto | Evidencia |
|---|---|---|
| 1 | Falla | «Nueve seis» no expresa 96 con naturalidad. |
| 2 | Pasa | Cuarenta y tres. |
| 3 | Pasa | Eighty-four, ya no define la multiplicación. |
| 4 | Pasa | DNS caching conserva resoluciones y acelera búsquedas posteriores. |
| 5 | Pasa | Reduce búsquedas repetidas y recursos usados. |
| 6 | Pasa | Router conecta redes y dirige tráfico. |
| 7 | Pasa | Conecta dispositivos a Internet y gestiona la red. |
| 8 | Pasa | Explica el efecto de la latencia en la rapidez de transmisión; no introduce una cifra falsa. |
| 9 | Pasa | Proxy intermedia y puede ocultar la IP del cliente/redirigir tráfico. |
| 10 | Pasa | Checksum permite detectar cambios en los datos. |
| 11 | Falla | Conserva mezcla de idiomas, pero copia «Explica la encriptación, pero en simple». |
| 12 | Pasa | Copia de respaldo permite recuperar originales perdidos/dañados. |

**10/12**, igual al diagnóstico previo por recuento: corrige unos fallos y
desplaza otros. No promover ni repetir ajustes de este perfil sin causa nueva.
En el caso 12 el lector clasifica español (sólo los sustantivos backup copy son
ingleses); la salida española no contradice el idioma recibido por el compositor.

La corrida terminó exit 0. Pico 3333.57 MiB del proceso diagnóstico y sus hijos;
no certifica app/voz. Coincidió con Python de Full: los tiempos se conservan como
observaciones, sin comparación de latencia. No son aceptación integrada ni 100
frescos. PREREGISTRO.json y results.jsonl contienen perfil, hashes y payloads.
