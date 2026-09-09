# Prueba de guarda causal: experimento rechazado

Doce turnos de desarrollo. Once publicaciones no equivalen a once aciertos. La guarda y el prompt experimentales fueron retirados; los datos permanecen intactos.

## t1 — REVISAR CONTINUIDAD

**Entrada literal**
```text
Ajusta el volumen.
```

**Respuesta literal**
```text
¿Cuánto deseas ajustar el volumen y en qué dirección (subir o bajar)?
```

Terminal: published_final. Pregunta para aclarar volumen; falta comprobar respuesta con un nivel y continuación real.

## t2 — ÚTIL

**Entrada literal**
```text
cancelar
```

**Respuesta literal**
```text
La clarificación fue cancelada.
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.

## t3 — ÚTIL

**Entrada literal**
```text
Abre EstudioC03Inexistente.
```

**Respuesta literal**
```text
Este pedido está fuera de lo que hago en este PC.
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.

## t4 — REVISAR CONTINUIDAD

**Entrada literal**
```text
Set the volume.
```

**Respuesta literal**
```text
How much and in which direction should the volume be adjusted?
```

Terminal: published_final. Pregunta para aclarar volumen; falta comprobar respuesta con un nivel y continuación real.

## t5 — ÚTIL

**Entrada literal**
```text
cancel
```

**Respuesta literal**
```text
La clarificación fue cancelada.
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.

## t6 — FALLO

**Entrada literal**
```text
Open EstudioC03Inexistente.
```

**Respuesta literal**
```text
composition_failed
```

Terminal: composition_failed. composition_failed; no hay respuesta final. Bloquear la causa inventada no logró una recuperación útil.

## t7 — REVISAR CONTINUIDAD

**Entrada literal**
```text
Set the volume, por favor.
```

**Respuesta literal**
```text
¿A qué volumen te refieres?
```

Terminal: published_final. Pregunta para aclarar volumen; falta comprobar respuesta con un nivel y continuación real.

## t8 — FALLO

**Entrada literal**
```text
cancelar
```

**Respuesta literal**
```text
¿Qué deseas cancelar exactamente?
```

Terminal: published_final. La respuesta no resuelve el turno actual; arrastra la cancelación/aclaración anterior.

## t9 — FALLO

**Entrada literal**
```text
Open EstudioC03Inexistente, por favor.
```

**Respuesta literal**
```text
¿Podrías especificar qué estás tratando de cancelar exactamente?
```

Terminal: published_final. La respuesta no resuelve el turno actual; arrastra la cancelación/aclaración anterior.

## t10 — ÚTIL

**Entrada literal**
```text
Hey, buenas
```

**Respuesta literal**
```text
¡Hola! Bienvenido. ¿Cómo estás?
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.

## t11 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 3:11 PM.
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.

## t12 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 100.
```

Terminal: published_final. Responde al turno; no se atribuyen efectos que no se verificaron.
