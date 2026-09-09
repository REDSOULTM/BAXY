# 496 — repetición inducida durante generación restringida

Ocho llamadas al mismo endpoint/completion. Cuatro pares con tokens de entrada idénticos y configuraciones efectivas verificadas: sólo cambian grammar,grammar_lazy ygrammar_triggers. Corrección de adaptación495 documentada; se comprueba round-trip de tokens preservados y longitud de prompt.

| Caso | Semilla | Condición | Secuencia | Juicio |
|---|---|---|---|---|
| owner46-seed0 | 0 | native_grammar | baxy_audio__mute, baxy_audio__status, baxy_audio__status, baxy_audio__volume__adjust, baxy_audio__status, baxy_audio__volume__adjust, baxy_audio__status, baxy_audio__status, baxy_audio__volume__adjust, baxy_audio__status | Adds unrequested operations; true in all four constrained cases. |
| owner46-seed0 | 0 | no_grammar | baxy_audio__mute | Requested operations/arguments only; however trailing prose narrates activation/success before execution. Native proposal improvement, not a complete honest product response. |
| owner51-seed0 | 0 | native_grammar | baxy_audio__volume__adjust, baxy_audio__mute, baxy_audio__status, baxy_system__status, baxy_audio__status, baxy_system__status, baxy_media__status, baxy_audio__status, baxy_system__settings__set, baxy_window__maximize, baxy_audio__volume__adjust, baxy_window__maximize, baxy_audio__status, baxy_system__status, baxy_media__status, baxy_audio__status, baxy_window__maximize, baxy_audio__volume__adjust, baxy_window__maximize, baxy_audio__status, baxy_system__status, baxy_media__status, baxy_audio__status, baxy_window__maximize, baxy_audio__volume__adjust, baxy_window__maximize | Adds unrequested operations; true in all four constrained cases. |
| owner51-seed0 | 0 | no_grammar | baxy_audio__volume__set, baxy_audio__mute | No repetition but invents a non-catalogue volume__set operation and claims execution. Cannot map it silently to volume. |
| owner51-seed0 | 17 | native_grammar | baxy_audio__volume, baxy_audio__mute, baxy_audio__status, baxy_audio__status, baxy_input__pointer__control, baxy_audio__status, baxy_input__pointer__control, baxy_audio__volume, baxy_audio__status, baxy_input__pointer__control, baxy_input__pointer__control, baxy_audio__volume, baxy_audio__status | Adds unrequested operations; true in all four constrained cases. |
| owner51-seed0 | 17 | no_grammar | baxy_audio__volume, baxy_audio__mute | Requested operations/arguments only; however trailing prose narrates activation/success before execution. Native proposal improvement, not a complete honest product response. |
| volume-unmute | 0 | native_grammar | baxy_audio__volume, baxy_audio__mute, baxy_audio__status, baxy_audio__status, baxy_system__status, baxy_audio__status, baxy_system__status | Adds unrequested operations; true in all four constrained cases. |
| volume-unmute | 0 | no_grammar | baxy_audio__volume, baxy_audio__mute | Requested operations/arguments only; however trailing prose narrates activation/success before execution. Native proposal improvement, not a complete honest product response. |

Sin gramática desaparece la repetición en los cuatro pares; con ella se producen7–26llamadas. Esto aísla la participación de la restricción en la generación, no un fallo del parser final. No se adopta desactivarla: una propuesta nombra una operación ajena al catálogo y todas las salidas libres añaden prosa de activación/éxito no ejecutado. No recortar/deduplicar ni reparar nombres por proximidad.

RAM1040.754MiB/GPU1692.184MiB,37.828s; todosEOS/truncatedfalse,sincortes.34984recogidaexit0. Sin efectos/UI/voz/cambio producto.
