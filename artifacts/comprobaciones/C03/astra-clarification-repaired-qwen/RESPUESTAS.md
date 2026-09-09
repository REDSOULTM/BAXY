# astra-clarification-repaired-qwen

Entradas y respuestas literales del conductor. Las expectativas se adjudican por contenido y estado; publicación no equivale a aprobación.

## t1 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 100.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t2 — ÚTIL

**Entrada literal**
```text
Ajusta el volumen.
```

**Respuesta literal**
```text
¿Cuánto deseas ajustar el volumen y en qué dirección (subir o bajar)?
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t3 — ÚTIL

**Entrada literal**
```text
Déjalo al 80%.
```

**Respuesta literal**
```text
El volumen se bajó al 80%. No está muteado.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t4 — ÚTIL

**Entrada literal**
```text
¿A qué volumen está?
```

**Respuesta literal**
```text
Está en volumen 80, no está mutado.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t5 — ÚTIL

**Entrada literal**
```text
Set the volume.
```

**Respuesta literal**
```text
How much and in which direction should the volume be adjusted?
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t6 — ÚTIL

**Entrada literal**
```text
Set it to 60%.
```

**Respuesta literal**
```text
The volume was set to 60%, and it is not muted.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t7 — ÚTIL

**Entrada literal**
```text
What is the volume?
```

**Respuesta literal**
```text
The volume is 60. Mute is off.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t8 — FALLO

**Entrada literal**
```text
Set the volume, por favor.
```

**Respuesta literal**
```text
¿Te refieres al volumen del sonido del equipo o de otro dispositivo?
```

Se conserva el objetivo pendiente, pero el dominio rechaza la coma tras volume; la continuación pregunta por descuento/tiempo y no aplica40%.

Terminal: published_final.

## t9 — FALLO

**Entrada literal**
```text
Al 40%, please.
```

**Respuesta literal**
```text
¿Te refieres al 40% en relación con algo específico, como un descuento o un porcentaje de tiempo?
```

Se conserva el objetivo pendiente, pero el dominio rechaza la coma tras volume; la continuación pregunta por descuento/tiempo y no aplica40%.

Terminal: published_final.

## t10 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 60.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t11 — ÚTIL

**Entrada literal**
```text
Pon el volumen al 100%.
```

**Respuesta literal**
```text
Puse el volumen al 100% y el sonido está activo.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t12 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 100.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.
