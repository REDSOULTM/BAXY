# 397 — idioma de la frase, no del nombre

393bT4: petición «Me llamo Álvaro.»; borrador nativo con response_language=es,
pero texto «I understand you're Álvaro. I've noted your name.»; se publicó sin
rechazo. La guardia _reply_uses_opposite_language tiene wanted=2 por la tilde
de Álvaro, other=6 por inglés y sólo rechaza cuando wanted=0. El hecho de que
un nombre lleve tilde no vuelve española la frase que lo contiene.

Reutilizar la lectura única del pedido: para la guardia de respuesta, conservar
el aporte ortográfico al español sólo si hay también evidencia española sin
tildes. No ignorar «Sí» ni las palabras españolas con tilde. Un nombre aislado
sin palabras funcionales sigue siendo neutral. No se enumeran nombres propios,
no cambia el umbral de rechazo ni se impone un idioma a una mezcla solicitada.

Además, las construcciones funcionales «me llamo», «te llamas», «se llama» no
aportan hoy evidencia sin tilde: «Me llamo Jordan» puede heredar inglés del
turno anterior y «Te llamas Jordan» no se detecta como respuesta opuesta. Se
añaden al conjunto existente de frases funcionales españolas, sin clasificarlas
como acciones, sin extraer ni guardar nombres. No hay prompt nuevo.

Baseline de pruebas antes de fuente; controles con otros nombres, declaración
sin tilde, traducción/idioma explícito, mezcla natural y respuesta neutral. Dueñas
Python y Fast después. Medición del turno real por separado; no Full durante
reparación ni declaración de aceptación fresca. Fuente393 y395 permanecen.

Revisión de la primera implementación, antes de medir producto: las frases
funcionales se contaban con substring. «white llamas» contenía «te llamas» y
«These llamas» contenía «se llama»; ambas se leían mixed (es2,en2). Añadir dos
controles ingleses y exigir límites de palabra en el conteo existente de frases
ES/EN. La primera tanda verde (1362 pass/Fast1,33s) no cierra este defecto;
conservar baseline-phrase-boundary.log y la validación final por separado.
