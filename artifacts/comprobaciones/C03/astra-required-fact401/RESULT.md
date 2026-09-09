#401 — valor observado retenido por el contrato existente

Ocho casos fijados, dos reales393b y seis controles sintéticos; compositor Python
real con guardas/reintentos, no App/UI/voz/efectos. Primeros payloads baseline
idénticos a393b, comprobados offline y durante inferencia. Sólo requiredFacts
añade el valor único, corto y ya proyectado; vacío/redactado quedan idénticos.

3/8 útiles baseline →5/8 con valor retenido. Mejoran las dos consultasEN de nombre,
sin regresiones en este panel. NombresES siguen mal atribuidos a BAXY y dato
redactado sigue agotando composición hasta cadena vacía en ambos brazos.
No llamar a esto cierre de memoria ni cambiar esa adjudicación por conservar
el literal. Se justifica transportar el dato mediante el contrato compartido,
con prueba dueña de privacidad y ausencia de efecto; sujeto y redacción pendientes.

| Caso | Baseline | Valor retenido | Adjudicación |
|---|---|---|---|
| stored-en | I don't have any private memories saved. | I saved the name Jordan in private memory. | fallo→útil: deja de negar lectura |
| stored-es | Mi nombre es Jordan. | Mi nombre es Jordan. | fallo→fallo: sujeto BAXY |
| new-name-en | I don't have any private memories saved. | I saved the name Priya in private memory. | fallo→útil: deja de negar lectura |
| new-name-es | Mi nombre es Renata. | Mi nombre es Renata. | fallo→fallo: sujeto BAXY |
| preference-en | Your saved favorite color is indigo. | Your saved favorite color is indigo. | útil→útil |
| preference-es | Tu color favorito guardado es el turquesa. | Tu color favorito guardado es turquesa. | útil→útil |
| empty-en | I don't have any private memories saved. | I don't have any private memories saved. | útil→útil |
| redacted-es | [vacío] | [vacío] | fallo→fallo: final vacío, no fuga |

Recursos: GPU3173.5625MiB, RAM4015.49609375MiB; 12.719s. Telemetría disponible, sin infracciones, manifiesto intacto. No aceptación conjunta.
