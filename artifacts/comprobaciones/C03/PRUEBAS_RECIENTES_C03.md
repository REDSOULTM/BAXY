# C03 — las pruebas más recientes, sin corregir las respuestas

**C03 sigue EN_CURSO. Esta captura publicó 21 respuestas: 17 aprobadas y 4 no aprobadas según revisión manual.** Son pruebas de desarrollo repetidas, no los 100 turnos nuevos de aceptación.

Se ejecutó el recorrido integrado con Qwen3-4B y un adaptador experimental v2, mediante conductor y una ventana vacía propia. No equivale a verificar toda la interfaz con `py main.py`. El modelo registrado del producto sigue intacto. Pico de VRAM: 3519,56 MiB, dentro del techo de 4096 MiB.

Cada entrada es el mensaje enviado y cada respuesta es el final capturado, incluyendo errores. Los prompts internos, hechos y borradores rechazados están en la auditoría enlazada.

[paired.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-product/paired.json>) · [compose-audit.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-product/compose-audit.jsonl>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-product/RESULT.json>)

[Aclaración del dueño: cuatro aprobaciones que corrigen la rúbrica anterior](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/ACLARACION_DUENO_2026-09-06.md>)

## Conversación integrada

### t1

**Entrada literal**

```text
¿Qué hora es?
```

**Respuesta literal**

```text
Son las 13:23.
```

**APROBADO:** Hora fiel al reloj observado.

### t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
Son las 13:23 y el volumen está al 100%; audio no está silenciado.
```

**APROBADO:** Conserva hora, volumen y audio no silenciado.

### t3

**Entrada literal**

```text
What time is it?
```

**Respuesta literal**

```text
It is 13:23.
```

**APROBADO:** Hora fiel y respuesta en inglés.

### t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The time is 13:23; audio volume is 100% and the sound is not muted.
```

**APROBADO:** Hora y audio correctos en inglés.

### t5

**Entrada literal**

```text
Dime la hora, please, en spanglish
```

**Respuesta literal**

```text
Son las tres y veintitres; it’s 13:23.
```

**NO APROBADO:** Hora contradictoria: tres y veintitrés no corresponde a 13:23. El verificador se corrigió después de esta captura; este fallo histórico sigue siendo fallo.

### t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Son las 13:23; el volumen está al 100% y el audio no está silenciado.
```

**APROBADO:** APROBADO expresamente por el dueño: respuesta útil y suficientemente sencilla; ver ACLARACION_DUENO_2026-09-06.md.

### t7

**Entrada literal**

```text
Hey, buenas
```

**Respuesta literal**

```text
¡Hola! Bienvenido; welcome to the chat.
```

**APROBADO:** APROBADO expresamente por el dueño: respuesta útil y suficientemente sencilla; ver ACLARACION_DUENO_2026-09-06.md.

### t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
La criptografía protege los datos usando códigos; only authorized users can read them.
```

**APROBADO:** APROBADO expresamente por el dueño: respuesta útil y suficientemente sencilla; ver ACLARACION_DUENO_2026-09-06.md.

### t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
Una copia de seguridad es un archivo; it stores data in case the original is lost or corrupted.
```

**APROBADO:** APROBADO expresamente por el dueño: respuesta útil y suficientemente sencilla; ver ACLARACION_DUENO_2026-09-06.md.

### t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
La gravedad mantiene que objetos caigan al suelo; it pulls things toward each other.
```

**NO APROBADO:** Redacción española incorrecta: mantiene que objetos caigan.

### t11

**Entrada literal**

```text
no abras Paint
```

**Respuesta literal**

```text
No abriré Paint.
```

**APROBADO:** Respeta la petición negativa; no anuncia ni propone abrir Paint.

### t12

**Entrada literal**

```text
what is the capital of Peru
```

**Respuesta literal**

```text
Lima is the capital of Peru.
```

**APROBADO:** Capital correcta.

### t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Plants absorb sunlight to make food; they release oxygen as a byproduct.
```

**NO APROBADO:** Se pidieron dos oraciones; entrega una sola, unida con punto y coma.

### t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque el agua sólida es menos densa que el líquido.
```

**APROBADO:** Explicación correcta de la menor densidad del hielo.

### t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Un archivo es un objeto; a folder contains several files.
```

**NO APROBADO:** Archivo como objeto no explica la diferencia; una carpeta puede estar vacía.

### t16

**Entrada literal**

```text
What is on my to do list?
```

**Respuesta literal**

```text
You don't have any tasks on your to do list.
```

**APROBADO:** Fiel a la lectura: tasks=[], count=0 en el perfil de prueba; no se extrapola a otras cuentas o perfiles.

### t17

**Entrada literal**

```text
cierra la ventana titulada Ventana C03 de prueba
```

**Respuesta literal**

```text
¿Confirmar o cancelar la acción de cerrar la ventana titulada Ventana C03 de prueba?
```

**APROBADO:** Identifica el cierre solicitado y ofrece confirmar o cancelar.

### t18

**Entrada literal**

```text
cancelar
```

**Respuesta literal**

```text
Se ha cancelado la solicitud para cerrar la ventana titulada "Ventana C03 de prueba".
```

**APROBADO:** Describe la cancelación; el cierre no se ejecuta.

### t19

**Entrada literal**

```text
cierra la ventana titulada Ventana C03 de prueba
```

**Respuesta literal**

```text
¿Confirmar o cancelar la acción de cerrar la ventana titulada Ventana C03 de prueba?
```

**APROBADO:** Nueva solicitud y nueva confirmación ligada a la ventana resuelta.

### t20

**Entrada literal**

```text
confirmar
```

**Respuesta literal**

```text
La ventana titulada "Ventana C03 de prueba" se cerró.
```

**APROBADO:** Cierre real verificado: app.close, windowClosed=true; la fixture no necesitó limpieza externa.

### t21

**Entrada literal**

```text
What time is it?
```

**Respuesta literal**

```text
It is 13:24.
```

**APROBADO:** Nueva lectura correcta tras finalizar la acción, en el mismo recorrido.

## Reproducción del fallo de hora tras corregir el verificador

Se reutilizaron hechos históricos de las 13:23. En el primer caso se inyectó el borrador contradictorio de t5: fue rechazado con `reversed_result`; el reintento sí lo generó el modelo local. Los otros tres casos fueron generaciones locales normales, sin efectos sobre el PC.

[Auditoría de rechazo y reintento](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-word-clock-replay/compose-audit.jsonl>)

### Reproducción · injected-contradiction

**Entrada literal**

```text
Dime la hora, please, en spanglish
```

**Respuesta literal**

```text
Son las 13:23; son las 13:23
```

Hora corregida, pero repetida y sólo en español: no aprobado.

### Reproducción · es

**Entrada literal**

```text
¿Qué hora es?
```

**Respuesta literal**

```text
Son las 13:23.
```

Hora correcta en español: aprobado.

### Reproducción · en

**Entrada literal**

```text
What time is it?
```

**Respuesta literal**

```text
It is 13:23.
```

Hora correcta en inglés: aprobado.

### Reproducción · mixed

**Entrada literal**

```text
Dime la hora, please, en spanglish
```

**Respuesta literal**

```text
Son las 13:23; it’s 13:23.
```

Hora correcta, pero repite la traducción completa: no aprobado.

## Pruebas automáticas y pendientes

| Comprobación | Resultado | Evidencia |
|---|---|---|
| `pytest tests/test_c03_request_preservation.py tests/test_compose_contract.py -q` | 125 pass | [log](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/scratchpad/c03-word-clock-owner-final.log>) |
| `scripts/test_source_quality.ps1 -Mode Fast` | Verde; compilación sin errores ni advertencias | [log](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/scratchpad/c03-word-clock-fast.log>) |
| Full final | Pendiente | El candidato todavía falla en conducta visible |

Faltan calidad consistente de desarrollo, los 100 turnos nuevos adjudicados, los ocho recorridos completos, recuperación final, UI real, runtime reproducible registrado y Full verde final. No se certifican los goals posteriores con esta captura.

## Más evidencia y contexto

- [Archivo completo de conversaciones registradas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_C03_PARA_EMMAN.md>)
- [54 respuestas comparadas del segundo ajuste](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_AJUSTE_2_C03.md>)
- [78 respuestas posteriores de formato: mejora parcial y regresiones de contenido; no promovido](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_AJUSTE_3_C03.md>)
- [27 respuestas de la escala descartada](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_ESCALA_C03.md>)
- [Estado y siguiente acción para reanudar](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/CHECKPOINT.md>)
