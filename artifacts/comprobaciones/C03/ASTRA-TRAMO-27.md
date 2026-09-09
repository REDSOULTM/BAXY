# C03 — tramo27: validar la intención sin imponer puntuación

EN_CURSO, sin bloqueo externo. La tanda anterior produjo evidencia causal.
Se conserva la protección de hechos; cambios acotados a bloqueos demostrados:

- Saludo: una pregunta social no provoca rechazo por sí sola. Una pregunta de
  conocimiento todavía exige una respuesta; el lector heredado separa el saludo.
- Confirmación: conserva opciones y estado pendiente; admite dos preguntas o
  una petición declarativa de confirmación. El kernel y la invocación no cambian.
- Progreso: admite morfología progresiva sin exigir literalmente «sigo» o «still».
  Se verifica la primera afirmación: un gerundio posterior no valida un éxito falso.
- Nombres: _glued_proper_name toma nombres tipados, no verbos capitalizados de la
  petición. «Find»→«finding» y «Revisa»→«revisando» dejaban de publicarse por esto.

Se investigó _truncated_fact_word y se restauró: no causaba estos dos rechazos.
Primera suite:143pass/3fallos; localizados y corregidos sin ocultar la evidencia.
Final:148pass (2,01s), test_c03_request_preservation/test_compose_contract/test_goal06_voice.
Fast10411 TERMINAL0,0errores/0advertencias. Full final pendiente.
llm.py SHA c80241a416a41505841d1580a0adebf4b9724e5d7d908013b6e426e17a20c0aa.

Prueba real9casos por modelo: astra-presentation-guards-fixed-{registered,qwen-base}.
Qwen9útiles, sin silencios; Granite5útiles,1revisión,3fallos. Son casos consumidos,
no aceptación fresca. Último filtro de primera afirmación añadido después de esta
captura y probado con el borrador falso; se preserva el orden temporal.
GPU Granite2687,55MiB y Qwen3497,56MiB. Ningún modelo registrado modificado.

Integrado75705 TERMINAL0: astra-presentation-product-qwen,21/21 útiles.
Diagnóstico adicional25921 TERMINAL0:12/12publicados pero t6 inventa inexistencia.
Prompt62830 sin mejora; guarda86417 agota respuesta. Integrado41856 TERMINAL0:
11/12publicados, t6 composition_failed y t8/t9 contaminados por diálogo previo.
Se retiraron prompt/guarda fallidos. Fuente vuelve al SHA del Fast verde indicado.
148pass tras reversión en2,07s. Datos fallidos preservados, no reinterpretados
como aprobación. CHECKPOINT y DIAGNOSTICO_POR_CAPAS_C03 actualizados.
Registro Granite intacto, Qwen no promovido. Full/100/UI siguen pendientes.
