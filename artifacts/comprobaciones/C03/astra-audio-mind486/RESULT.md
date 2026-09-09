# 486 — mente integrada: audio, sin ejecutar efectos

Fuente485, modelo registrado Qwen2507 Q4/b9980; comparación de regresión, no clasificación global de modelos. Catálogo real, E5 confirmado listo, turn.decide sin providers.

| Caso | Estado | Respuesta/propuesta | Juicio |
|---|---|---|---|
| owner44 | selection_correct | audio.volume | audio.volume conservado. turn.decide no acredita argumentos ni efecto físico. |
| owner46 | failed | ¿Te refieres a que quieras que el sonido esté completamente activo y sin silencio, o que se active de forma inmediata sin retraso? | Catálogo incluye audio.mute y su descripción de reactivar. El modelo afirma sin herramienta que reactivó sonido; la guarda rechaza correctamente. La recuperación introduce una ambigüedad inexistente. |
| owner51 | failed | ¿Quieres que el volumen esté en el 100% y que el sonido se apague completamente? | La recuperación de candidatos omite audio.volume pese al contexto de la pregunta previa. La respuesta confunde desmutear con apagar el sonido. Requiere conservar objetivo contextual. |
| clitic-alone | selection_correct | audio.mute | audio.mute conservado; falta vincular y verificar muted=false en etapa de argumentos. |
| volume-unmute | selection_correct | audio.volume, audio.mute | Se conservan audio.volume y audio.mute en orden; sólo propuesta. |
| unmute-volume | selection_correct | audio.mute, audio.volume | Se conservan audio.mute y audio.volume en orden; sólo propuesta. |
| negative-unmute | failed | ¿Te refieres a aumentar el volumen a 37 y mantener el silencio en algún lugar específico? | Selector nativo propone correctamente audio.volume en ambos intentos. PlannerContractError en turn_preparation la veta: pero no no se separa para probar prohibición independiente. |
| word-meaning | meaning_correct_voice_failed | No se requiere ninguna acción para responder a esta pregunta. "Desmutear" significa restaurar o activar el estado de sonido de un dispositivo, como el micrófono o la salida de audio, para que pueda captar o emitir sonido nuevamente. | Definición correcta y sin efectos, pero antecedida por prosa interna sobre no requerir acción. |

Cuatro selecciones de operaciones correctas; tres pedidos de acción fallan. La explicación de la palabra es correcta pero tiene prosa interna. No son ocho turnos aceptados.

Picos del árbol de procesos: RAM 1769.023 MiB, GPU 3497.559 MiB; 53.782 s. Sin cortes. No incluye UI ni voz física y no demuestra el consumo conjunto final.

Las entradas y los contextos exactos están en PREREG.json. Requests, catálogo, auditoría y HTTP crudos permanecen en la carpeta privada identificada allí. El significado de las descripciones sí incluye reactivar el audio. No atribuir ese fallo a una descripción incompleta.
