# 491 — argumentos nativos: mejora de selección, polaridad aún incorrecta

Dieciséis llamadas nativas, sin guardas de turnos, efectos ni cambios de fuente. Perfiles y payloads exactos490; controles zero/typed comparables. Ningún error, context overflow ni truncamiento.

| Caso | Interfaz | Respuesta nativa | Juicio |
|---|---|---|---|
| owner46-seed0 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 100}"}] | Requested unmute; returns audio.volume level100, repeating preceding action instead. |
| owner46-seed17 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 100}"}] | Requested unmute; returns audio.volume level100, repeating preceding action instead. |
| owner51-seed0 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 100}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\": true}"}] | Both effects in correct order, but state=true mutes output, contrary to requested unmute. Must be state=false. |
| owner51-seed17 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 100}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\": true}"}] | Both effects in correct order, but state=true mutes output, contrary to requested unmute. Must be state=false. |
| clitic-alone | zero | [{"name": "baxy_audio__mute", "arguments": "{}"}] | Expected effect set/order or no tools; zero interface does not prove arguments. |
| clitic-alone | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Expected operation/arguments/order or correct definition; no execution demonstrated. |
| volume-unmute | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}, {"name": "baxy_audio__mute", "arguments": "{}"}] | Expected effect set/order or no tools; zero interface does not prove arguments. |
| volume-unmute | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Expected operation/arguments/order or correct definition; no execution demonstrated. |
| unmute-volume | zero | [{"name": "baxy_audio__mute", "arguments": "{}"}, {"name": "baxy_audio__volume", "arguments": "{}"}] | Expected effect set/order or no tools; zero interface does not prove arguments. |
| unmute-volume | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}, {"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}] | Expected operation/arguments/order or correct definition; no execution demonstrated. |
| negative-unmute | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Expected effect set/order or no tools; zero interface does not prove arguments. |
| negative-unmute | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}] | Expected operation/arguments/order or correct definition; no execution demonstrated. |
| word-meaning | zero | Desmutear significa restaurar el sonido de una salida de audio, permitiendo que el sonido se escuche nuevamente. Si el dispositivo o la aplicación estaba en modo silencioso, desmutear lo hace activo nuevamente. | Expected effect set/order or no tools; zero interface does not prove arguments. |
| word-meaning | typed | Desmutear significa restaurar el sonido de un dispositivo o aplicación que había sido silenciado anteriormente, permitiendo que se escuchen las señales de audio, como sonidos de notificaciones, música o voz. | Expected operation/arguments/order or correct definition; no execution demonstrated. |
| negative-only | zero | No se realizará ninguna acción que desmute el audio. | Expected effect set/order or no tools; zero interface does not prove arguments. |
| negative-only | typed | No realizaré ninguna acción que desmute el audio. El audio permanecerá silenciado según tu solicitud. | No tool calls, but claims audio will remain muted without evidence of current state. Native prose not safe to publish directly. |

Corrección de terminología: el argumento real es state:boolean. muted corresponde a estado observado; las expectativas auxiliares de486 no demostraron argumentos porque turn.decide no los devuelve. Handler y provider confirman state=true silencia y state=false reactiva. El contrato actual no explica esta polaridad: sólo type:boolean y la descripción dual silencia/reactiva.

No se adopta la interfaz completa todavía. Se prueba492 el hecho contractual de polaridad en la descripción, con ambas interfaces para elegir el cambio más ligero que cumpla.

Sólo servidor nativo: RAM777.883MiB/GPU3497.559MiB,15.062s. No UI/voz ni efectos. Sesión37805recogidaexit0.
