# C03 — runtime registrado, UI y recuperación

C03 EN_CURSO. Qwen3-4B-Instruct-2507 Q4_K_M registrado, KVq8 por defecto. No son100 turnos nuevos. La tanda integrada tiene33 respuestas normales publicadas:32 útiles y1 fallo de naturalidad. Las tres averías y los tres turnos restaurados se evalúan aparte. No se acredita progreso narrado: esta tanda no produjo una frase de progreso separada.

Ventana real observada con la skill de Windows tras `py main.py`, sin overrides de modelo/voz/Python. Se vio Qwen4b local, activación encendida, error de recuperación de memoria, cancelación manual y respuesta de hora/audio. Pico del árbol real con voz:3589,12MiB. No acredita por sí solo habla física/STT ni toda la ruta de hardware.

[Detalle del tramo y limitaciones](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/ASTRA-TRAMO-29.md>)

## astra-registered-development-recovery-qwen

[Entradas, respuestas y veredictos individuales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-registered-development-recovery-qwen/RESPUESTAS.md>)

[Hechos y auditorías emparejados](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-registered-development-recovery-qwen/paired.json>)

## astra-registered-integrated-qwen

[Entradas, respuestas y veredictos individuales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-registered-integrated-qwen/RESPUESTAS.md>)

[Hechos y auditorías emparejados](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-registered-integrated-qwen/paired.json>)

## Nueve regresiones directas del compositor

Hechos sintéticos exactos, no efectos nuevos sobre el PC.9/9 útiles:3horas,3recuperaciones de memoria y3de audio. Las opciones retry se conservan como token que ofrece el shell; las respuestas españolas pueden mejorar estilo. El diagnóstico inicial omitió requiredResponseWords y tiene ERRATA explícita; no se presenta como medición fiel del shell.

### clock-es

```text
¿Qué hora es?
```

```text
Son las 16 horas y 9 minutos.
```

### clock-mixed

```text
Dime la hora, please, en spanglish
```

```text
Ahora son las 16:09.
```

### clock-en

```text
What time is it?
```

```text
It's 16:09.
```

### memory-es

```text
Continúa con la recuperación de memoria.
```

```text
¿Quieres continuar con la recuperación de memoria o cancelar? Elige entre continuar o cancelar.
```

### memory-en

```text
Continue the memory recovery.
```

```text
Do you want to continue the memory recovery or cancel it?
```

### memory-mixed

```text
Continúa con la memory recovery, please.
```

```text
¿Quieres continuar con la recuperación de la memoria o cancelarla? Elige entre continuar o cancelar.
```

### audio-es

```text
Continúa con el ajuste de volumen.
```

```text
¿Quieres continuar con el ajuste de volumen o retry?
```

### audio-en

```text
Continue the volume adjustment.
```

```text
Do you want to continue the volume adjustment or retry?
```

### audio-mixed

```text
Continúa el volume adjustment, please.
```

```text
¿Quieres continuar o retry con el ajuste del volumen?
```
