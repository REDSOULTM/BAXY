# C03 — escritorio, voz y recursos conjuntos: tramo260

Arranque real `py main.py`, fuente257, lock60 instalado, Qwen3.5 con override.
Ejecución de600,51s, sesión72258 recogida exit0. Límite temporal alcanzado;
launcher0, cleanup0, procesos observados cerrados y volumen restaurado exactamente.
No promoción. La fuente del prereg cambió en: [].

Picos atribuidos a BAXY: **3516.66MiB de VRAM** y
**4822.60MiB de RAM residente**. VRAM menor que4096MiB.
No es el consumo de todo Windows ni una garantía de máximos para otras cargas.
Los comandos efectivos están en PROCESSES_OBSERVED.json.

El click derecho del agente en el micrófono de la ventana real produjo modo
directo y captura activa. La sospecha de bloqueo por el wake no se reprodujo:
no cambiar React para corregirla. Verificador wake ausente y cascada inválida
siguen declarados en ready; no se valida wake ni C08.

9 eventos de habla durante escucha; 8800 bloques AEC
observados acumulados (281.60s), micrófono y referencia no nulos.
10 audios Piper verificados por hash y muestras. DSP medio observado
0.791ms y máximo58.592ms: el máximo supera
un bloque32ms, no se afirma plazo duro. No hubo transcripciones humanas: las
entradas fueron texto, confirmado expresamente por el dueño en este chat.
Esto acredita convivencia de componentes y señales físicas, no exactitud ASR
ni inteligibilidad completa del altavoz mediante sólo el audio generado.

## Respuestas que bloquean C03

| Entrada literal observada del dueño | Salida visible | Evaluación |
|---|---|---|
| Hola como me puedes ayudar hoy? | Puedo ayudarte con cualquier pregunta, explicación o charla que necesites hoy. ¿Qué tienes en mente? | Respuesta general, no acredita explicar capacidades operativas. |
| Tengo en mente que abras steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Fallo: petición normal no resuelta. Investigar alcance real y selección, no aceptar negativa como éxito. |
| No se que me hablas, tu si puedes hacer eso | No puedo hacer eso porque la interpretación de tu solicitud no fue válida. | Recuperación contractual honesta pero no útil ante corrección normal. |
| abre steam | ¿Quieres que abra Steam? | Aclaración innecesaria ante pedido explícito. |
| Si, abre steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Sigue sin resolver la petición. |
| mhhhhh, porque no?, cuales son tus capacidades? | Soy BAXY, un asistente virtual que vive en este PC y puedo ayudarte con información, explicaciones y charla, pero no tengo la capacidad de ejecutar aplicaciones como Steam ni controlar el hardware directamente. | Negación general falsa de capacidades del catálogo. |

UI_OBSERVED.txt y UI_FINAL_OBSERVED.txt conservan accesibilidad; también se observó
la pregunta de Tortugas Ninja y el mensaje del dueño identificándose. No todos los
textos posteriores generados por Piper tienen captura visual independiente; no
confundir generación, composición y publicación. La frase posterior «Puedo abrir
y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de
otras cosas» consta en Piper, sin acreditar por eso ejecución de ninguna operación.

Primera petición Steam (request11): shortlist28 sin app.open → game.launch bruto
→ domain_grounding lo convierte en unsupported → composición atribuye fuera de
catálogo. El siguiente turno(request16) tiene dos PlannerContractError y recuperación.
El problema empieza antes de prosa. La disponibilidad real de Steam y el rango de
app.open se comprobarán contra un hello nuevo en261, distinguiéndolo del original.

Prereg260 tenía tres controles planeados; no se enviaron porque el dueño estaba
probando la ventana. Sus mensajes son desarrollo humano, no reserva congelada.
Fuente sin editar en260; no tests ni Full repetidos. C03 íntegro EN_CURSO.
