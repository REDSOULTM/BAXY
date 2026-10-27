---
name: arreglar-fallo
description: Arregla un fallo de BAXY demostrándolo primero con una prueba que falla, luego el cambio mínimo hasta verde, revisión del diff y verificación. Úsala cuando algo existente está roto (salida mala, excepción, regresión), no para conducta nueva.
---

# Arreglar un fallo

Probar que el fallo existe es lo que separa un arreglo de un retoque. El método general (causa raíz antes de
tocar nada) es la skill `systematic-debugging`; esto es lo que BAXY añade. Si el fallo llega de un caso real
(un chat de BAXY, una app que no respondió), el arreglo es general: un mecanismo para todas las apps, nunca
una excepción para la que falló, y se prueba un caso cada vez en el notebook (skill `prueba-en-vivo`).

1. **Localiza.** `docs/AI_CONTEXT_MAP.md` primero; `grep` acotado a `src tests scripts main.py`; lee sólo
   rangos. Si la causa no se ve, traza la operación por su nombre literal (`"operacion.exacta"`).
   Antes de abrir una línea nueva de investigación, busca en el archivo histórico y en `git log` (ley 1):
   puede estar ya medido y rechazado.
2. **Reprodúcelo en el test dueño.** Una prueba nueva en el fichero que ya cubre esa frontera
   (`tests/test_*.py` o `tests/Baxy.<Proyecto>.Tests`) que falla por la razón correcta. Si no es
   reproducible en prueba (hardware, voz, ventana real), dilo y deja la evidencia que sí tienes.
3. **Arregla con el diff mínimo**, en la pieza dueña. Nada de un router, fallback o capa que tape el caso:
   si hace falta una capa, retira la que sustituye en el mismo cambio. Sin listas de apps en código.
4. **Verde** el test nuevo y los de su fichero. Después, skill `verificar` hasta el peldaño que toque, y
   «arreglado» sólo con esa evidencia delante (skill `verification-before-completion`).
5. **Revisa tu diff**: cada hallazgo con línea exacta, fallo concreto y severidad defendible. Si el dueño pide
   una revisión a fondo, `/pr-review-toolkit:review-pr` lanza los revisores oficiales; si el cambio toca red,
   providers o confirmación, también el agente `revisor-privacidad`.
6. **Commit** en español, en una frase que diga qué conducta queda arreglada, con la línea de coautoría que
   indique el harness. Sin `--no-verify`.

Para: si el arreglo exige cambiar un invariante o una decisión de `00_IDENTIDAD.md`, no lo hagas; anótalo
en `documentacion/APLAZADOS.md` con el motivo.
