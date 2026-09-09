# C03 — captura con reloj y referencia continua — 2026-09-07

EN_CURSO. Herencia/contraste138–142 en PRUEBAS_REFERENCIA138_142.md; fuente136
fijada por TRAMO136_142_PINS.json. No otro AEC ni cambio de umbrales.

143 sustituye MME bloqueante por WASAPI callback con ADC válido y cola acotada.
El dueño de captura hace el DSP. Referencia anclada una vez a ADC y leída con cursor
de muestras, sin latest para el filtro. Ring circular4s (cola mic64×32ms más
historial282ms), warmup de resampler antes del callback, esperas acotadas/cancelables
y errores explícitos ante pérdidas. PCM inyectado no afirma AEC sobre el escritorio.
Pruebas de continuidad/vida y medición física pendientes. No Full ni promoción.

Resultado posterior:148pass/0skips/13,12s y Fast17999exit0/Release2,85s.
144 falla al abrir WASAPI en el worker antes de hablar;145/146 aíslan COM.
Continúa ASTRA-TRAMO-147.md. No se considera143 aceptado físicamente.
