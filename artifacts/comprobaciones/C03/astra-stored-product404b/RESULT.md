#404b — nombre conversacional correcto; presentación y composición abiertas

Seis sintéticos:3útiles,1parcial,2fallos. Una composition_failed, no timeout;6admissions200, exit0, manifiesto intacto. No UI/voz física/aceptación fresca.

T6 mejoró deJordan persistido aÁlvaro del diálogo. T4 ahora agota composición en lugar de aclarar; T5, sin aclaración pendiente que lo desvíe, vuelve a leer memoria y atribuyeJordan aBAXY. No convertir estas diferencias en mejora general ni ocultar el final ausente.

Comparación del primer payload nativo28tools de Me llamoÁlvaro con402b: igualdad=False. La fuente404 sólo cambia el dispatch de consulta genérica; no atribuir variaciónT4 a un nuevo prompt ni borrar ninguna corrida.

## 1. útil

**Entrada:** My name is Jordan. Remember my name.

> Jordan, I remember your name. The save operation failed because memory was disabled.

Ruta: error

> Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

Ruta: confirmation

Causa memoria deshabilitada y confirmación de activación honestas.

## 2. parcial

**Entrada:** confirm

> Memory configuration enabled.

Ruta: result

> The memory has been saved successfully.

Ruta: result

Activación/guardado reales, narración genérica.

## 3. útil

**Entrada:** What name have you saved in private memory?

> I saved the name Jordan in private memory.

Ruta: result

LecturaJordan conserva el valorEN.

## 4. fallo

**Entrada:** Me llamo Álvaro.

Sin prosa final. Terminal: composition_failed.

Composición agotada, final ausente ante presentación normal; no sustituirlo por el terminal técnico.

## 5. fallo

**Entrada:** ¿Qué nombre tienes guardado en tu memoria privada?

> Mi nombre es Jordan.

Ruta: result

Esta vez sí pasa por resultado de lectura y diceMi nombreJordan; sujeto incorrecto.

## 6. útil

**Entrada:** ¿Cómo me llamo?

> Tu nombre es Álvaro.

Ruta: conversation

404 conserva conversación actual: respondeÁlvaro, noJordan persistido.

## Comparación posterior de los payloads T4

Campos distintos de messages iguales; mensajes system iguales: True. 404b incluye la bienvenida inicial como mensaje assistant; 402b no la incluye. La diferencia entre aclaración y final ausente no es una variación con payload idéntico. No se atribuye a la nueva selección de alcance404. Véase payload-diff.json.
