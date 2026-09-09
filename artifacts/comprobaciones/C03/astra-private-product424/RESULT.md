# 424 — retirar no-mmap aumenta RAM; ambas medidas son necesarias

Una diferencia funcional frente423: carga vuelve a mmap=true, cache-ram0 sigue.
8/8terminales idénticos a423;4/8útiles y mismos4fallos. Exit0/manifiesto intacto.
RAMárbol5207,203125MiB frente3173,4296875MiB423: +2033,7734375MiB.
GPU3177,5625MiB igual,55,516s frente56s. Sin violaciones, mínimo RAM libre
1099.914MiB. Que no corte esta vez no prueba consumo menor: entorno libre
varía. RSS cuenta páginas del archivo mapeado residentes/compartibles; no implica
que todas sean privadas irreclamables. El beneficio no-mmap es residente medido,
no se confunde con private commit.423es mejor perfil de los comparados.

Conclusión conjunta420–424: no-mmap sin limitar cache no basta; cache0 con mmap
completa pero retiene mayor working set. No-mmap+cache0 completa los mismos8,
con~3,10GiB RAM y3,10GiB VRAM. No disminuye contexto/slots/precisión/pesos.
No certifica voz/ASR/wake conjunto ni mínimo global. No nueva fuente424.

425 adoptará cache-ram0 en el perfil del backend local y no-mmap cuando hay GPU.
CPU-only conserva mmap: allí no hay offload y no se demostró mejora retirándolo.
Sin selector nuevo/configflag del producto ni cambio del modelo registrado.
Pruebas dueñas de arranque GPU/CPU y suites planner/transporte/composición;
Fast después. Full al candidato final, no ahora. Hook retirado para confirmar
comando de producción al comprobar producto posterior. Falta arreglar conducta.

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
