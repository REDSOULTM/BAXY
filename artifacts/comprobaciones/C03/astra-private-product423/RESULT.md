# 423 — desactivar caché RAM permite completar los ocho turnos

Una diferencia funcional contra422: --cache-ram0; se mantiene --no-mmap.
Logsverbosity4/commandline por PID son observación. Ayuda exacta y log confirman
prompt cache disabled,4096tokens por slot×3,KVq8_0,CPUweights497,31MiB,
GPUweights2603,50MiB/KV204MiB/estado recurrente150,75MiB. Checkpoints siguen
activados; no se cambió capacidad de contexto/pesos/precisión ni memoria privada.

RAMárbol3173,4296875MiB frente5303,9921875MiB422: reducción2130,5625MiB(~40,17%).
GPU3177,5625MiB igual.56s, sin violaciones, mínimo RAMlibre2747.621MiB.
Exit0,manifiesto intacto.8admisiones200/8terminales:7respuestas y1composition_failed.
Primeros7finales idénticos a422; T8 nuevo «Te llamas Álvaro.» correcto.
4/8útiles(T1,T2,T4,T8);T3permiso redundante,T5silencio,T6falsarefusal,T7sujeto
equivocado siguen abiertos. Igualdad textual no demuestra regresión general.
Sintéticos de desarrollo;0casos humanos finales. No UI/voz física conjunta.
La commandline confirma auxiliar baxy_mind.router_worker. Datos RSS y privada
no son intercambiables; verATTRIBUTION.json y samples privados. Árbol cerrado.

424 retirará sólo --no-mmap para probar si cache-ram0 basta con la carga original.
Mismos8casos/configuración/source418/guards. Sólo después decidir fuente; evitar
conservar un flag sin mejora demostrada. No promoción del modelo ni nuevo runtime.

1. My name is Jordan. Remember my name.
   published_final: Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

2. confirm
   published_final: The memory has been saved successfully.

3. Abre una aplicación.
   published_final: ¿Quieres que abra una aplicación?

4. What name have you saved in private memory?
   published_final: I saved the name Jordan in private memory.

5. Me llamo Álvaro.
   composition_failed: no_response;recovery:no_response;retry_exhausted

6. Abre una aplicación.
   published_final: No puedo abrir esa aplicación porque está fuera de lo que hago en este PC.

7. ¿Qué nombre tienes guardado en tu memoria privada?
   published_final: Mi nombre es Jordan.

8. ¿Cómo me llamo?
   published_final: Te llamas Álvaro.
