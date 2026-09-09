# Desarrollo en caliente: catálogo semántico comprobado

Sesión26550 terminó0,179,22s totales,GPU3497,56MiB,RAM5225,75MiB;registro intacto.
21/21publicados, **no21aciertos**. COMMAND_RELEASE.json registra150,188s de
preparación con stdin abierto antes de enviar los comandos. No es una medición
de latencia de inicio frío. No ocultar esa espera ni llamarla tiempo de respuesta.

El observador de SkillRegistry sólo examinaba kwargs.encoder, pero load_default
lo pasa posicionalmente: su encoderSupplied=false no demuestra ausencia de encoder.
Por eso el driver liberó los comandos al límite150s y no al terminar la carga.
No cambiar retrospectivamente esa evidencia. No es un bug del producto.

**Prueba de integración conseguida:** las diez decisiones raw_attempt registradas
(ids27,30,33,39,42,45,48,51,56,64) usan retrieval=semantic. Antes, la misma población
en corpus-inherited figuraba lexical. Se restauró corpus/caché exactos y se comprobó
la promoción en el proceso real. Esto no prueba una mejora estadística de acierto.

| Turno | Evaluación individual |
|---|---|
| t1 | Hora12:18 fiel, forma oral. |
| t2 | «desmudado» no es una formulación válida del estado del audio; falla prosa. Volumen/hora coinciden. |
| t3 | Hora correcta en inglés. |
| t4 | Hechos correctos; descripción técnica de mute state. |
| t5 | Hora fiel; repite traducción de la hora y usa «amigos» sin necesidad. Spanglish poco natural. |
| t6 | Hora/audio/volumen fieles, pero todo en español ante pedido mixto. |
| t7 | Saludo pertinente, «meterse en el día» y emoji poco apropiados. |
| t8 | Explicación básica de cifrado útil; mezcla limitada al sustantivo inglés, extensa. |
| t9 | Copia permite recuperar datos; analogía de otro cuarto frente a incendio es débil. Mezcla mínima. |
| t10 | Atracción/caída explicadas aproximadamente; «cuando los soltas» tiene errores y la mezcla es mínima. |
| t11 | Respeta negación, no abre Paint. |
| t12 | Lima, correcta. |
| t13 | Dos frases en inglés, fotosíntesis básica correcta; segunda frase figurada. |
| t14 | Explicación correcta de densidad/volumen; peso comparado se entiende a igual volumen. |
| t15 | Sólo español pese a Spanglish explícito y definición circular de archivo. |
| t16 | Lista vacía verificada, inglés. |
| t17 | Confirmación exacta del título con opciones correctas. |
| t18 | Cancelación fiel; repite detalles de la detección interna. |
| t19 | Nueva confirmación exacta. |
| t20 | Cierre verificado, prosa técnica redundante. |
| t21 | Nueva hora12:19 correcta en inglés. |

Journal del perfil corpus-warm: seq24/26 resuelven título exacto/PID14476;
seq28 app.close verified=true/windowClosed=true. Fixture cerrada por BAXY tras
confirmar, sin limpieza externa; Baxy/llama/fixture ausentes al recoger.

La herencia resolvió una dependencia real. Siguen bloqueando C03 la fidelidad y
naturalidad de la narración y el spanglish, no la instalación de E5. No seguir
repitiendo estos21casos para obtener una corrida favorable.
