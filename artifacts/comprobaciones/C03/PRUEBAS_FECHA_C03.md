# C03 — entradas, respuestas y evaluación de fecha contextual

2026-09-06. Desarrollo consumido. No son cien casos frescos ni una certificación de C03.
Textos literales de logs; CASES.json conserva procedencia. No se afirma que el orden sea una sesión histórica ni autoría humana demostrada.
Se prueba el producto con conductor sin ventana; no demuestra UI o audio físico.

## astra-real-date3

Resultado de proceso: 0; duración 56.11 s; VRAM 3497.56 MiB. Registro intacto: True.

### t1

Entrada literal:
```text
Dime que hora es
```

Respuesta literal:
```text
Son las 18 horas y 1 minuto.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:01"}
```

### t2

Entrada literal:
```text
y la fecha?
```

Respuesta literal:
```text
¿De qué fecha te refieres?
```

NO APROBADO: pide aclarar una consulta de fecha después de atender la hora.

Datos entregados al generador:
```json
{"kind": "clarification", "cause": "unclear request"}
```

### t3

Entrada literal:
```text
what time is it?
```

Respuesta literal:
```text
It's 18:01.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:01"}
```

Evidencia: [astra-real-date3/paired.json](astra-real-date3/paired.json), [traza del shell](astra-real-date3/shell-trace.jsonl), [procedencia](astra-real-date3/CASES.json).

## astra-real-date-context3

Resultado de proceso: 0; duración 58.08 s; VRAM 3497.56 MiB. Registro intacto: True.

### t1

Entrada literal:
```text
Dime que hora es
```

Respuesta literal:
```text
Son las 18:05.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:05"}
```

### t2

Entrada literal:
```text
y la fecha?
```

Respuesta literal:
```text
La fecha es el 5 de abril de 2024.
```

NO APROBADO: inventa una fecha sin lectura del Core.

Datos entregados al generador:
```json
{"kind": "conversation"}
```

### t3

Entrada literal:
```text
what time is it?
```

Respuesta literal:
```text
It's 18:05.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:05"}
```

Evidencia: [astra-real-date-context3/paired.json](astra-real-date-context3/paired.json), [traza del shell](astra-real-date-context3/shell-trace.jsonl), [procedencia](astra-real-date-context3/CASES.json).

## astra-real-date-shell3

Resultado de proceso: 0; duración 57.09 s; VRAM 3497.56 MiB. Registro intacto: True.

### t1

Entrada literal:
```text
Dime que hora es
```

Respuesta literal:
```text
Son las 18 horas y 13 minutos.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:13"}
```

### t2

Entrada literal:
```text
y la fecha?
```

Respuesta literal:
```text
¿De qué fecha te refieres?
```

NO APROBADO: pide aclarar una consulta de fecha después de atender la hora.

Datos entregados al generador:
```json
{"kind": "clarification", "cause": "unclear request"}
```

### t3

Entrada literal:
```text
what time is it?
```

Respuesta literal:
```text
It's 18:13.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:13"}
```

Evidencia: [astra-real-date-shell3/paired.json](astra-real-date-shell3/paired.json), [traza del shell](astra-real-date-shell3/shell-trace.jsonl), [procedencia](astra-real-date-shell3/CASES.json).

## astra-real-date-final3

Resultado de proceso: 0; duración 54.03 s; VRAM 3497.56 MiB. Registro intacto: True.

### t1

Entrada literal:
```text
Dime que hora es
```

Respuesta literal:
```text
Son las 18 horas y 15 minutos.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:15"}
```

### t2

Entrada literal:
```text
y la fecha?
```

Respuesta literal:
```text
Hoy es el 6 de septiembre de 2026.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"date": "2026-09-06"}
```

### t3

Entrada literal:
```text
what time is it?
```

Respuesta literal:
```text
It's 18:15.
```

APROBADO: conserva la lectura observada y responde al pedido.

Datos entregados al generador:
```json
{"clock": "18:15"}
```

Evidencia: [astra-real-date-final3/paired.json](astra-real-date-final3/paired.json), [traza del shell](astra-real-date-final3/shell-trace.jsonl), [procedencia](astra-real-date-final3/CASES.json).

## Límite de la conclusión

La última corrida aprueba estas tres respuestas conocidas. La anterior fecha inventada se conserva como fallo. La modificación posterior de proyección de pasos anidados se verifica con prueba dueña y queda pendiente de la próxima corrida integrada.
