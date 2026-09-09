# Producto380 — 6/10 útiles,1parcial,1silencio

Mismos diez controles sintéticos370, fuente379 (374guarda,377idioma,379cancelación); modelo/muestreo/prompt sin cambios. Diez admissions200, ningún timeout, launcher exit0. Sin UI real, voz física, promoción ni reserva humana.

## 1. útil

**Entrada:** My name is Jordan. Remember my name.

**Respuestas visibles:**

> Jordan, I remember your name. The save operation failed because memory was disabled.

> Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

## 2. útil

**Entrada:** What would I be confirming?

**Respuestas visibles:**

> I need your decision on enabling private local memory. Do you want to confirm or cancel?

## 3. útil

**Entrada:** cancel

**Respuestas visibles:**

> The memory enable action has been cancelled.

## 4. útil

**Entrada:** Who am I?

**Respuestas visibles:**

> You are Jordan, a user who just asked me to remember your name.

## 5. fallo: silencio

**Entrada:** What is my name?

**Respuestas visibles:**
(silencio; no_response;recovery:no_response;retry_exhausted)

## 6. útil

**Entrada:** Me llamo Álvaro y quiero que guardes mi nombre.

**Respuestas visibles:**

> Hola Álvaro, no puedo guardar tu nombre porque la memoria está deshabilitada.

> Hola Álvaro, ¿te gustaría que active mi memoria privada para guardarte tu nombre? Por favor, dime si quieres confirmar o cancelar.

## 7. parcial: eco antes de identificar activación

**Entrada:** ¿Qué vas a activar?

**Respuestas visibles:**

> ¿Qué vas a activar? ¿Confirmar o cancelar la activación de la memoria local privada?

## 8. útil

**Entrada:** cancelar

**Respuestas visibles:**

> Se ha cancelado la activación de la memoria privada local.

## 9. fallo: responde su identidad, no la del humano

**Entrada:** quién soy ahora

**Respuestas visibles:**

> Soy BAXY, tu compañero en el PC.

## 10. fallo: confunde conversación con persistencia

**Entrada:** ¿Cómo me llamo?

**Respuestas visibles:**

> No puedo decirte tu nombre porque la memoria está deshabilitada.

Journal: memory.status completed; dos memory.save failed y dos memory.recall failed. No memory.enable ejecutado, ni nombre guardado. 370→380 gana ambos cancelados; T9 cambia una limitación falsa por identidad de BAXY, sigue fallando. Primera respuestaI remember your name coincide370 y distingue explícitamente fallo de guardado; no se atribuye persistencia. No cerrar C03 ni confundir6/10 con aceptación final.
