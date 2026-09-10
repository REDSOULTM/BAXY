# Reparación del verificador de BAXY — 791

Dos contraejemplos de la revisión790 demostraban errores de BAXY. Un título seguido de punto y otra frase recibía cero menciones aunque aparecía una vez. Un proceso escrito entre paréntesis junto al título podía contarse como otra ventana sin título. Ambos se reparan en el helper existente de inventario, protegiendo los nombres antes de separar frases y reconociendo la anotación del proceso observado.

Las 72 variantes nuevas fallaban antes de la reparación: 72 fallos y 89 controles existentes correctos. Tras la reparación, las siete suites específicas sumaron 808 pass en 5,30 s. La validación final de las 21 suites dio **3062 pass, 1 skip ambiental STT y 121 subtests en 19,52 s**; Fast terminó con exit 0. Comandos y resultados completos: VALIDATION.json, validated.log y fast.log. El skip no acredita voz.

No cambian el primer prompt, los pesos, el muestreo, los presupuestos ni el backend. El candidato hereda787 y789, todavía sin adoptar; sus13 archivos exactos están preservados en SOURCE_SNAPSHOT.json y SOURCE_PATCH.diff. El programa407 es c851950899b91e2c6b120f1649f12ef92c666c0df78e06be6f768e1526f7a88c. La validación no acredita por sí sola recuperación de respuestas con el LLM real.

La siguiente prueba792 compara las mismas50 tareas completas por brazo. A usa el compositor original; B elimina únicamente el campo rejected_draft del JSON de corrección factual al enviar el reintento. Los hechos, las cuentas de identidad y las instrucciones restantes se conservan. La influencia de ese borrador es una hipótesis; no se adopta la eliminación antes de medir su efecto.

Esto estudia integración con Qwen y no decide si Qwen supera a K2. El registro mantiene28 requisitos cubiertos y714 abiertos; sin crédito de reserva, UI, voz ni recursos del producto completo. Full final permanece pendiente conforme al goal.
