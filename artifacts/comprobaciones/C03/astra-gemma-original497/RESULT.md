# Gemma original: comparación nativa 497

El checkpoint original evita las operaciones adicionales observadas en el publicado. Tres prompts renderizados coinciden exactamente con 494; ambos usan gramática nativa y el perfil documentado de Google. Esto acredita esta comparación acotada, no la aceptación del producto.

La petición contextual de volumen y desmute sigue invirtiendo el booleano en tres respuestas. Cuatro respuestas violan la interfaz declarada sin argumentos. La única selección contextual con argumentos vacíos no acredita todavía nivel ni polaridad. `state=true` silencia y `state=false` reactiva.

| Caso | Interfaz | Resultado literal | Observación |
|---|---|---|---|
| owner46-seed0 | zero | [{"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | violates_declared_zero_argument_interface |
| owner46-seed0 | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | Propuesta nativa correcta; ejecución no probada |
| owner46-seed17 | zero | [{"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | violates_declared_zero_argument_interface |
| owner46-seed17 | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | Propuesta nativa correcta; ejecución no probada |
| owner51-seed0 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\":true}"}] | wrong_mute_state, violates_declared_zero_argument_interface |
| owner51-seed0 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\":100}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\":true}"}] | wrong_mute_state |
| owner51-seed17 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}, {"name": "baxy_audio__mute", "arguments": "{}"}] | unmute_polarity_unproved |
| owner51-seed17 | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\":100}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\":true}"}] | wrong_mute_state |
| volume-unmute | zero | [{"name": "baxy_audio__volume", "arguments": "{\"level\":37}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | violates_declared_zero_argument_interface |
| volume-unmute | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\":37}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\":false}"}] | Propuesta nativa correcta; ejecución no probada |
| word-meaning | zero | Desmutear significa reactivar el sonido o la salida de audio que estaba silenciada. | Propuesta nativa correcta; ejecución no probada |
| word-meaning | typed | Desmutear significa reactivar el sonido o la salida de audio que estaba silenciada. | Propuesta nativa correcta; ejecución no probada |
| negative-only | zero | Entendido, no desmutearé el audio. | Propuesta nativa correcta; ejecución no probada |
| negative-only | typed | No se requiere ninguna acción. | stage_like_prose |

RAM: 1030.965 MiB; VRAM: 1681.988 MiB; tiempo: 62.719 s. Medición del servidor y conductor nativo, no de BAXY completo. EOS y sin truncamiento en las 14 respuestas.

No se modifica el runtime registrado. El siguiente trabajo es la pérdida de cláusulas y el contexto de aclaración en el producto; no se repite un barrido de parámetros.
