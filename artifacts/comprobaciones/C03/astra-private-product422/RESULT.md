# 422 — atribución de RAM; mismos fallos de conducta

Mismos8casos/fuente418/modelo4B/--no-mmap/límites421; sólo telemetría por PID.
Exit1/corteRAMlibre<768MiB;GPU3177,5625MiB/RAMárbol5303,9921875MiB/52,719s.
Manifiesto intacto.110 muestras, mínimo disponible752,355MiB. No voz física/UI.
El pico por proceso se da en distintos momentos; no sumar picos individuales.
Servidor llama máximo3676,008MiB RSS/7125,102MiB privada comprometida. El auxiliar
Python máximo877,984MiB RSS, mente349,398MiB y App229,367MiB. RSS es suma de
working sets, puede contar páginas compartidas; privada comprometida no es RAM
física residente. El heredado RamSampler usa esa suma RSS, no memoria privada.
El código router.py:466 es el único Popen Python auxiliar: router_worker con E5;
se confirma proceso exacto con commandline en423. Piper también apareció hasta
101,672MiB. Wake desactivado no significa que no haya síntesis en el conductor.

Siete terminales/admisiones;T8 sin llegar.3/7útiles(1,2,4),T3/T6aclaración
incorrecta,T5silencio composition_failed,T7sujeto incorrecto.418 logra recall
tras aclaración EN; no arregla la prosa ES. No se certifica ningún caso humano.

1. Entrada: My name is Jordan. Remember my name.
   Final (published_final): Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

2. Entrada: confirm
   Final (published_final): The memory has been saved successfully.

3. Entrada: Abre una aplicación.
   Final (published_final): ¿Quieres que abra una aplicación?

4. Entrada: What name have you saved in private memory?
   Final (published_final): I saved the name Jordan in private memory.

5. Entrada: Me llamo Álvaro.
   Final (composition_failed): no_response;recovery:no_response;retry_exhausted

6. Entrada: Abre una aplicación.
   Final (published_final): No puedo abrir esa aplicación porque está fuera de lo que hago en este PC.

7. Entrada: ¿Qué nombre tienes guardado en tu memoria privada?
   Final (published_final): Mi nombre es Jordan.

## Siguiente hipótesis acotada
La ayuda del b9980 exacto permite cache-ram y declara8192MiB por defecto.
El servidor crece con cada turno; probar423 sólo --cache-ram0 para distinguir
caché opcional de prompts en RAM de pesos/buffers activos. No reduce contexto,
slots, pesos ni precisión. Se conserva --no-mmap de422 para aislar una variable.
Logs nativos a verbosity4 y commandline por PID se añaden como observación.
Herencia: dossier Carter/Ollama03_Optimizacion...:12–14 hablaba KVq8/contexto
(ya usados aquí); otro backend/modelo, no justifica recortar calidad/contexto.
INVESTIGACION_MODELO_C03 no registra prueba cache-ram. Ayuda exacta b9980 manda.
Primarias consultadas2026-09-08: https://github.com/ggml-org/llama.cpp/pull/16391
documenta cache en RAM para evitar recomputar prefijos y flag0 para desactivar;
https://github.com/ggml-org/llama.cpp/pull/15293 separa checkpoints del contexto.
No cambiar ambos mecanismos juntos ni asumir que esta caché causa todo el pico.
