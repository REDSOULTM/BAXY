# C03 — semántica conservada y vetos de presentación

La corrección del referente publica preguntas ES/EN, pero referent-prose/t3
rechaza 07 horas y 13 minutos pese a clock=07:13. Se amplía la misma gramática
numérica a unidades ES/EN, conservando rechazo de minutos distintos y AM/PM
contradictorio. No se sustituye la respuesta por una hora sintética. Palabras
como siete y trece siguen fuera de esta equivalencia; no afirmar cobertura total.

El prefijo responde en spanglish: ocultaba la definición posterior al matcher
anclado. Se incorpora el wrapper con separador al lector de envolturas existente.
Preguntas recuperan knowledge; acciones siguen siendo acciones, texto citado
sigue literal. Cuatro rojas antes; 1557 pass después con hora, catálogo y efectos.

Tres estrategias de instrucciones mixed (segmentos, code-switch y bilingüe)
no producen calidad suficiente: descartadas. Role-sampling predeterminado tampoco
mejora. La plantilla oficial conserva mensajes system sucesivos; no hay evidencia
de que descarte las instrucciones después de la primera.

El contraste mixed-advisory sí demuestra daño del veto positivo de vocabulario:
12/12 publicaciones en vez de agotamientos, aunque sólo máximo8/12 útiles.
Se retira de decisiones y se conserva como mixed_language_needs_review en audits
opt-in, sin nuevos diccionarios. Los tests de bloqueo de estilo se sustituyen por
pruebas de conservación, instrucciones todavía presentes, aviso y retry de eco.
Esto no rebaja la adjudicación: una respuesta sólo española al pedido explícito
de spanglish sigue fallando, y una explicación inexacta tampoco cuenta como pass.
Después: 94 pass C03/compose/voz, 873 pass/1 skip ambiental turn_policy/V8/STT.

Confirmation-route no obtiene confirmación: la apertura falla y los cierres
terminan en fallo de paso antes de confirmar. MindPlanSession descartaba la causa
del response; ahora la conserva. MissionNarration mantiene reason JSON como
objeto, sin doble codificación. Una prueba roja antes; 62 pass/0 skips después
en PlannerAppBoundaryTests y MindPlanSessionTests. Falta contraste real de causa.

Qwen8 con sólo veto mixed convertido en aviso vuelve a fallar: timeouts4s de
composición para un modelo parcialmente en CPU, cuyos decodes nativos medidos
eran 6.4–16.3s. Se detiene el árbol propio tras nueve terminales, STOP.json y
ADJ conservan el resultado parcial. El siguiente contraste reutiliza presupuestos
CPU existentes en el host con ngl20 real en sidecar. No cambia umbrales de calidad
ni autoriza inferir C07; sólo separa plazo de ejecución de calidad semántica.

Estado y procesos activos en CHECKPOINT.md. Sin promoción, aceptación100, Full
final ni publicación. No repetir el barrido de modelos ni otra variante de wording.
