# 492 — polaridad explícita: recuperación parcial y regresión

Único factor nuevo frente a490zero/491typed: descripción audio.mute explica el state real:true silencia;false reactiva. Se mantiene el catálogo como única fuente del significado. Ninguna fuente de producto editada.

| Caso | Interfaz | Respuesta nativa | Juicio |
|---|---|---|---|
| owner46-seed0 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Still repeats audio.volume rather than unmuting. |
| owner46-seed0 | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Correct audio.mute state=false with both seeds; new descriptor plus typed interface recovers typo/context. |
| owner46-seed17 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Still repeats audio.volume rather than unmuting. |
| owner46-seed17 | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Correct audio.mute state=false with both seeds; new descriptor plus typed interface recovers typo/context. |
| owner51-seed0 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Only audio.volume; requested unmute absent. |
| owner51-seed0 | typed | No puedo desmutar el volumen al mismo tiempo que lo pongo en 100. Puedo ajustar el volumen a 100, pero el desmuto debe realizarse por separado. ¿Deseas que primero lo pongo en 100 y luego lo desmutes? | Spurious incapacity to perform volume and unmute together; seed17 also reverses mute polarity. |
| owner51-seed17 | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Only audio.volume; requested unmute absent. |
| owner51-seed17 | typed | No puedo desactivar el sonido (muted) y establecer el volumen al 100 simultáneamente. Si deseas silenciar el sonido, primero debes hacerlo, y luego puedes ajustar el volumen. ¿Deseas que primero lo silencie y luego lo ponga al 100? | Spurious incapacity to perform volume and unmute together; seed17 also reverses mute polarity. |
| clitic-alone | zero | [{"name": "baxy_audio__mute", "arguments": "{}"}] | Correct selection or definition; no arguments/execution proved. |
| clitic-alone | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Expected operations/order/arguments (or definition) retained; no provider execution. |
| volume-unmute | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}, {"name": "baxy_audio__mute", "arguments": "{}"}] | Correct selection or definition; no arguments/execution proved. |
| volume-unmute | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}, {"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}] | Expected operations/order/arguments (or definition) retained; no provider execution. |
| unmute-volume | zero | [{"name": "baxy_audio__mute", "arguments": "{}"}, {"name": "baxy_audio__volume", "arguments": "{}"}] | Correct selection or definition; no arguments/execution proved. |
| unmute-volume | typed | [{"name": "baxy_audio__mute", "arguments": "{\"state\": false}"}, {"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}] | Expected operations/order/arguments (or definition) retained; no provider execution. |
| negative-unmute | zero | [{"name": "baxy_audio__volume", "arguments": "{}"}] | Correct selection or definition; no arguments/execution proved. |
| negative-unmute | typed | [{"name": "baxy_audio__volume", "arguments": "{\"level\": 37}"}] | Expected operations/order/arguments (or definition) retained; no provider execution. |
| word-meaning | zero | Desmutear significa restaurar el sonido en una salida de audio, permitiendo que el sonido se escuche nuevamente. Si el dispositivo o la aplicación estaba silenciado, desmutearlo activa la reproducción de audio. | Correct selection or definition; no arguments/execution proved. |
| word-meaning | typed | Desmutear significa restaurar el sonido en un dispositivo o aplicación, permitiendo que el audio sea escuchado nuevamente. Si estabas en una situación donde el sonido estaba silenciado, desmutearlo activa la salida de audio. Esto se puede hacer mediante una acción específica en el sistema, como la función `baxy_audio__mute` con el parámetro `state=false`. | Definition includes internal function name and state parameter. |
| negative-only | zero | [{"name": "baxy_audio__mute", "arguments": "{}"}] | Proposes audio.mute despite explicit prohibition. Diagnostic only, no effect executed. Regression versus491. |
| negative-only | typed | No realizaré acciones para desmutes el audio. Si necesitas verificar el estado actual del volumen o silencio, puedo ayudarte con eso. | No function call; grammatical defect in prose, native stage not product voice acceptance. |

No adopción. Hay mejora en el pedido con errata usando argumentos reales, pero la petición compuesta retrocede y el control de prohibición en interfazzero propone una acción no pedida. No continuar redacción/sampling de esta misma hipótesis. Cambiar candidato493 con perfil propio documentado.

20callsnativas,0errores/overflow/truncamiento. RAM782.805MiB/GPU3497.559MiB,19.890s.94004recogidaexit0;sin efectos/UI/voz.
