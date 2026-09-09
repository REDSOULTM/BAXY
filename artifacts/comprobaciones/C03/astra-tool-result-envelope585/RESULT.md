# Nativo585 — separar evidencia con roles no corrige el sujeto

Ocho capturasCPU recientes582 por dos representaciones,16 EOS. La variante mueve la línea situation intacta a role:tool, precedida por una representación estructural sintética de la lectura ya observada; no es un tool_call producido en aquel turno. Identidad, pregunta, hechos, instrucciones, muestreo greedy/seed0 y límites permanecen iguales. El template efectivo contiene tool_call/tool_response conforme al template oficial exactoQwen2507. No se ejecutan herramientas ni se introduce un borrador de prosa escrito a mano.

Ambos formatos conservan cuatro respuestas correctas (conteos4/9 y usos14/23), pero ambos fallan en los sujetos10/12/20/21. El formato tool sigue diciendo Estoy/I'm/Tengo al describir la CPU total. No hay mejora que justifique incorporarlo; no se modifica el producto. Esta comparación a muestreo constante aísla la representación, no clasifica modelos ni afirma que greedy sea su óptimo general.

GPU3497,559MiB/RAM721,680MiB,8,829s. Fuentes consultadas2026-09-09: tokenizer_config oficialQwen3-4B-Instruct-2507 y documentaciónQwen3 de function calling. Sin UI/voz ni consumo conjunto final. Encuesta13 cubiertos/729 abiertos/0NA intacta.
