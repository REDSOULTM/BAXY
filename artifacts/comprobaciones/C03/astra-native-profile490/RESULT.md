# 490 — perfil Qwen2507 comprobado en selección nativa

Mismos casos y consulta contextual489. Único factor nuevo: perfil nativo oficial .7/.8/k20/min0/presence0/repeat1; seeds0 y17 en ambos pedidos contextuales;max1024. Los parámetros figuran en cada request real, no sólo en configuración. Diez llamadas nativas terminan stop/tool_calls, ninguna length.

| Caso | Respuesta/propuesta | Juicio |
|---|---|---|
| owner44-seed0 | audio.volume | Expected selection/order preserved; no arguments or physical effects proved. |
| owner46-seed0 | ¿Te refieres a que quieras que el sonido esté completamente activo y sin silencio, o que se active de forma inmediata sin retraso? | Both seeds produce tool-free invented activation; factual guard rejects. Recovery remains artificial ambiguity. |
| owner46-seed17 | ¿Te refieres a que quieras que el sonido esté completamente activo y sin silencio, o que se active de forma inmediata sin retraso? | Both seeds produce tool-free invented activation; factual guard rejects. Recovery remains artificial ambiguity. |
| owner51-seed0 | ¿Quieres que el volumen esté en el 100% y que el sonido se apague completamente? | Both seeds select audio.volume only, omitting audio.mute. Contextless compatibility rejects volume; final clarification reverses unmute intent. |
| owner51-seed17 | ¿Quieres que el volumen esté en el 100% y que el sonido se apague completamente? | Both seeds select audio.volume only, omitting audio.mute. Contextless compatibility rejects volume; final clarification reverses unmute intent. |
| clitic-alone-seed0 | audio.mute | Expected selection/order preserved; no arguments or physical effects proved. |
| volume-unmute-seed0 | audio.volume, audio.mute | Expected selection/order preserved; no arguments or physical effects proved. |
| unmute-volume-seed0 | audio.mute, audio.volume | Expected selection/order preserved; no arguments or physical effects proved. |
| negative-unmute-seed0 | audio.volume | Expected selection/order preserved; no arguments or physical effects proved. |
| word-meaning-seed0 | No se requiere ninguna acción para responder a esta pregunta. "Desmutear" significa habilitar o activar el micrófono para que se pueda capturar sonido desde el dispositivo. | Defines unmuting only as enabling microphone, without output-audio meaning; internal action-stage prose remains. |

Los dos pedidos contextuales fallan con ambas semillas; las cinco selecciones control se conservan. Sin adopción ni rechazo global del modelo. La definición queda limitada al micrófono y conserva prosa interna.

Picos sólo mente: RAM1769.867MiB/GPU3497.559MiB,58.422s;0cortes/0efectos. Sesión69532recogidaexit0.
