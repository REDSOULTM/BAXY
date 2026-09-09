# 463 — menor RAM, pero perfil de razonamiento no equivalente

8terminales:5útiles,2respuestas inadecuadas y1composition_failed. No promoción.
RAM2685,06MiB (2,62GiB),GPU1694,18MiB (1,65GiB),54,25s,0cortes.
Logs Windows: PLE1837,50MiB CPU_Mapped; CUDA_Host baja2152,50→315MiB.
El producto completo crece respecto al compositor; esa diferencia no se oculta.

**Causa localizada:** request.reasoning_budget_tokens=-1 hereda el presupuesto
DEL SERVIDOR en server-common.cpp5266f24da:1366–1369. Con servidor0 no significa
razonamiento ilimitado. Las7calls con profile_override no tuvieron reasoning_content;
algunas publicaron deliberación, otras las rechazaron las guardas. 460/462 usaban
servidor-1. El arnés463 no reprodujo ese perfil; corregir configuración, no prompt.

T8 es otra responsabilidad: conversación inicial recupera Álvaro pero en inglés,
se rechaza por idioma y recuperación agota. No atribuirlo a la memoria persistente.
T1 no explicita qué permiso se acepta. Esos fallos siguen dentro de C03 aunque
la corrección de razonamiento resuelva los recalls. No están aún corregidos.

## Turno1 — fallo

Entrada: My name is Jordan. Remember my name.

BAXY: Got it, Jordan. I'll remember your name. Which choice do you want: confirm or cancel?

Confirmation does not identify enabling persistent memory; future promise is not a claimed completed save, but exact choice is unexplained.

## Turno2 — útil

Entrada: confirm

BAXY: Confirming the operation status. The memory was successfully saved.

Authorized enable and save completed; final states saved.

## Turno3 — útil

Entrada: Abre una aplicación.

BAXY: ¿Qué aplicación deseas abrir?

Missing application is asked.

## Turno4 — fallo

Entrada: What name have you saved in private memory?

BAXY: The user is asking what name I have saved in private memory. I need to look at the situation data to see what was recalled. The situation shows that the memory "name" was successfully retrieved with the value "Jordan". I will state this briefly in English, as requested.

Publishes internal deliberation/operation name instead of direct answer.

## Turno5 — útil

Entrada: Me llamo Álvaro.

BAXY: Qué onda, Álvaro. ¿En qué te puedo ayudar hoy?

Greets conversational name without unauthorized save.

## Turno6 — útil

Entrada: Abre una aplicación.

BAXY: ¿Qué aplicación deseas abrir?

Missing application is asked.

## Turno7 — útil

Entrada: ¿Qué nombre tienes guardado en tu memoria privada?

BAXY: Jordan.

Returns saved Jordan with no false subject.

## Turno8 — fallo

Entrada: ¿Cómo me llamo?

BAXY: no_response;recovery:no_response;retry_exhausted

No published useful response: initial chat gives Alvaro in English for Spanish request, existing retry/recovery then fails.

