# 494 — las llamadas extra ya están generadas

Tres solicitudes exactas493typed con verbose:true. La fuente fijada5266f24da confirma que esta opción agrega metadatos al resultado; no cambia prompt, muestreo ni parser.

En los tres casos, la secuencia de llamadas en el texto bruto coincide exactamente con la lista interpretada:15,7y8llamadas. stop_type=eos ytruncated=false. El intérprete de salida no añadió las operaciones extra. La generación todavía estaba limitada por la gramática nativa, por lo que no se atribuye el fallo a los pesos sin aislarla.

No se usa skip-chat-parsing como simple observador: la fuente demuestra que cambia la ruta de gramática/template. Los reportes21375/22786 aportan hipótesis de otras versiones, no una causa probada aquí.

Picos servidor:RAM1066,117/GPU1694,184MiB,17,532s.16948recogidaexit0. Sin promoción ni efectos.
