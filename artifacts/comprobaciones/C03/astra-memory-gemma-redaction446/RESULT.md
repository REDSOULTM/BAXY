# 446 — redacción tipada intercambia errores en Gemma

Los8 controles normales siguen correctos. En3protegidos/mixtos,1/3→1/3:
EN mejora y deja de inventar una eliminación; el mixto ahora emite fake tools
y afirma un save no pedido. ES mantiene fake tools. No adopción de proyección
ni promoción de modelo. Todos stop;10,188s/GPU1719,5703125MiB/RAM2836,23046875MiB,
sin violaciones, manifiesto intacto, cliente cerrado. No repetir la representación.

447 conserva444 exactamente y contrasta formato de salida: un objeto con
message:string, sin contenido predefinido, frente a texto libre. La fase debe
redactar, no proponer herramientas. Hereda response_format/json_schema y el
transporte existente, no añade otro modelo, juez, reintento ni parche de nombres.
Se conserva la advertencia de INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md:
gramática válida no implica semántica correcta. Las fuentes LetMeSpeakFreely y
la reproducción de dotTXT allí contrastadas justifican controlar el formato
con mensajes/sampler idénticos; no son una garantía para este checkpoint.
El resultado requerido es utilidad11/11, no sólo JSON válido o ausencia de tools.
