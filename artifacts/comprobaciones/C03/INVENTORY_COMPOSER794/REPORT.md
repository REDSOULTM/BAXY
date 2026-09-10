# Verificación de integración con Qwen — 794

El panel terminó con **36/50 respuestas completas correctas**, frente a32/50 de792A: cuatro recuperaciones y ninguna pérdida de calidad en este conjunto. Se adopta la reparación793. La selección del modelo ya estaba cerrada; esta corrida verifica BAXY con Qwen, sin comparar modelos ni cambiar instrucciones del redactor.

| Caso recuperado | Fallo de BAXY reparado | Resultado real |
|---|---|---|
| inventory785-1-3 | Inventario vacío confundido con instrucción copiada | Respuesta fiel en una llamada,0,469s |
| inventory785-1-4 | Mismo falso veto con petición mezclada | Respuesta fiel en una llamada,0,422s |
| inventory785-2-2 | Dos ventanas de la página confundidas con el total de siete | Identidades y alcance correctos, una llamada,1,265s |
| inventory785-4-1 | “No representa todas” interpretado como afirmación de exhaustividad | Doce entradas con sus multiplicidades, total observado20 y página parcial, una llamada,5,265s |

Los50 primeros payloads son idénticos a los congelados. Se registraron59 intentos:57 respuestas HTTP exitosas y2 errores, todos con terminal. Los parámetros efectivos se verificaron en los57 éxitos. Ningún texto bruto es nuevo respecto a792: cambió su entrega. La reproducción controlada793 confirma el efecto del verificador sobre los cuatro borradores capturados. Otro final varió antes de la intervención en2-3, conservando su calidad; no se cuenta como mejora causal.

Root revisó los cinco finales cambiados;45 finales idénticos conservan la adjudicación previa. Quedan14 fallos, incluidos2 timeouts y3 finales vacíos: multiplicidad incompleta, discrepancias de nombres y errores de sujeto/etiqueta de memoria siguen abiertos. Las seis listas densas completas se mantienen correctas en una llamada.

Duración136,516s;3499,56MiB de VRAM y764,42MiB de RAM residente del árbol del compositor/servidor, no de BAXY completo. Fuente, manifiesto y driver permanecieron intactos; sesión56452 terminó con exit0 y fue recogida. No hay inferencia activa.

La validación de fuente793 pasó3134 pruebas y121 subtests, con1 skip ambiental STT; Fast exit0. C03 permanece activo:28 requisitos cubiertos y714 abiertos. No se concede cobertura de encuesta, reserva, interfaz ni voz a este diagnóstico. La siguiente categoría preparada es la lectura de procesos, con seis requisitos históricos y variantes hasta completar al menos50 casos de producto real.
