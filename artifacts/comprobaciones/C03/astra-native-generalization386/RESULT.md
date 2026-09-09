# Generalización385/386 — 13/17 → 14/17 útiles en contenido

Población fijada antes de ambos candidatos, SHA671c6ce96ae26ed7273e2ccfe431ea0d44080e1767a3e23e806a0b3f91f788d6. Cinco casos371, contexto del sintético380T9 y once controles explícitamente sintéticos. Nunca reserva humana. Baseline385 descarta initial_reply al entrar a chat;386usa fuente383 sin cambios. Igual modelo/template/prompt/muestreo/catálogo/guardas, no operación ejecutada.

Las acciones sólo son propuestas: reloj system.time se conserva, volumen sin cantidad pide el nivel y no actúa. La definición Steam no abre la aplicación. No regresión de autoridad en esta población. Tres fallos compartidos siguen abiertos. Identidad de BAXY y aire se vuelven más extensos: no afirmar mejora uniforme de concisión/voz propia ni aceptación C03.

## t5 — Útil en ambos

**Entrada:** What is my name?

**385:** Your name is Jordan.

**386:** Your name is Jordan.

## t10 — Mejora: antes añadía limitación falsa; ahora Eres Álvaro.

**Entrada:** ¿Cómo me llamo?

**385:** Tu nombre es Álvaro, pero como no tengo acceso a tu memoria privada, no puedo recordarlo automáticamente en esta conversación.

**386:** Eres Álvaro.

## third-party — Útil en ambos

**Entrada:** What is my name?

**385:** I don't know your name.

**386:** I don't know your name.

## assistant-conflict — Útil en ambos

**Entrada:** What is my name?

**385:** Your name is Jordan.

**386:** Your name is Jordan.

## explicit-persistence — Niega capacidad privada que existe en catálogo, oculta al selector.

**Entrada:** What name have you saved in private memory?

**385:** I don't have access to your private memory or saved names; I only know what you tell me in our current conversation.

**386:** I don't have access to private memory or saved names. I can only interact with the systems and data available on your device through the tools I have. If you'd like to check your own notes or reminders, I can help with that.

## product380-t9 — Identifica BAXY/niega datos disponibles de la persona.

**Entrada:** quién soy ahora

**385:** Soy BAXY, tu compañero en el PC.

**386:** Soy BAXY, tu asistente virtual. No tengo información sobre quién eres, ya que la memoria está deshabilitada.

## assistant-identity — Útil en ambos

**Entrada:** Who are you?

**385:** I'm BAXY, your PC companion.

**386:** I'm BAXY, your system assistant. I can help you with various tasks on your computer, such as checking system status, managing Wi-Fi, handling notes, or monitoring network connections. How can I assist you today?

## human-identity-es — Propone system.identity (cuenta Windows) pese a nombre humano Eva disponible.

**Entrada:** ¿Quién soy?

**385:** ["system.identity"]

**386:** ["system.identity"]

## family-identity — Útil en ambos

**Entrada:** What is my name?

**385:** I don't know your name.

**386:** I don't know your name.

## mixed-self-name — Útil en ambos

**Entrada:** Me llamo Lucía. What's my name?

**385:** Tu nombre es Lucía.

**386:** Tu nombre es Lucía.

## corrected-self-name — Útil en ambos

**Entrada:** What is my name?

**385:** Your name is Casey.

**386:** Your name is Casey.

## ram-definition — Útil en ambos

**Entrada:** Explain RAM in one sentence.

**385:** RAM is the computer's short-term memory that temporarily stores data for quick access by the CPU while programs are running.

**386:** RAM is the computer's short-term memory that temporarily stores data for quick access by the CPU while programs are running.

## air-composition — Útil en ambos

**Entrada:** El aire es H2O?

**385:** No, el aire no es H₂O; el H₂O es agua, mientras que el aire es una mezcla de gases principalmente nitrógeno y oxígeno.

**386:** No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (N₂) y oxígeno (O₂).

H2O es la fórmula química del agua.

## capital-france — Útil en ambos

**Entrada:** ¿Cuál es la capital de Francia?

**385:** La capital de Francia es París.

**386:** La capital de Francia es París.

## steam-no-effect — Útil en ambos

**Entrada:** No abras Steam; explícame qué es.

**385:** Steam es el catálogo y plataforma de distribución de videojuegos más grande del mundo, donde puedes comprar, descargar y jugar a miles de títulos en PC.

**386:** Steam es el catálogo y plataforma de distribución de videojuegos más grande del mundo, donde puedes comprar, descargar y jugar a miles de títulos en PC.

## clock-read — Útil en ambos

**Entrada:** ¿Qué hora es?

**385:** ["system.time"]

**386:** ["system.time"]

## volume-missing — Útil en ambos

**Entrada:** Pon el volumen.

**385:** ¿A qué nivel quieres que ponga el volumen?

**386:** ¿A qué nivel quieres que ponga el volumen?

Tiempo total de turnos:385 35.918s;386 30.695s. No benchmark de arranque, hardware o voz. Ambos EXIT.completed true, manifest intacto, handle46996 cerradoexit0.

Decisión: conservar fuente383 por recuperar contenido sin perder decisiones útiles en este panel, manteniendo abiertos concisión y los tres fallos. El casoEva no falla por una guarda: la primaria ya elige system.identity y todas las capas lo conservan. Su descriptor actual habla de usuario/dominio efectivos del proceso, no de nombre de la persona; siguiente hipótesis acotada es aclarar ese alcance real en descripción de catálogo, con controles de lectura Windows. No nueva lista de nombres ni regla que impida cuentas Windows legítimas.
