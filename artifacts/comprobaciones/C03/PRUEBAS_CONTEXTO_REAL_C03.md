# C03 — contexto real: entradas y respuestas actuales

**17 de20 casos conocidos aceptados;3 pendientes.** Dos turnos adicionales restauraron y verificaron el volumen al100. Esto no es porcentaje del goal ni aceptación fresca.

La identidad quedó recuperada. La aclaración pendiente ya no absorbe una petición completa, pero la respuesta negativa aún falla. El fallo nuevo de hora en17:04 se diagnosticó en la frontera C#: rechazaba minutos de un dígito pese a que Python y la hora observada coincidían. Las pruebas con los hechos capturados aceptan17:04 y rechazan tiempos distintos. La corrida actual observó17:12; no se presenta como repetición física de17:04.

1030 pruebas Python;118.NET;Fast verdes. Full pendiente. Runtime registrado sin overrides,conductor sin ventana/wakeoff.90,16s,GPU3499,56MiB,RAM5073,18MiB. Sin procesos propios pendientes.

## 1. APROBADO

**Entrada literal**
```text
hola buenas
```

**Respuesta literal**
```text
Hola, ¿qué tal? Bienvenido.
```

Responde de manera útil y fiel a lo pedido.

## 2. APROBADO

**Entrada literal**
```text
Hello?
```

**Respuesta literal**
```text
Hey, what's up?
```

Responde de manera útil y fiel a lo pedido.

## 3. APROBADO

**Entrada literal**
```text
cuál es la capital de francia
```

**Respuesta literal**
```text
París
```

Responde de manera útil y fiel a lo pedido.

## 4. APROBADO

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

Responde de manera útil y fiel a lo pedido.

## 5. APROBADO

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno y oxígeno, mientras que H₂O es agua.
```

Responde de manera útil y fiel a lo pedido.

## 6. APROBADO

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de gaming y servicios digitales desarrollada por Valve. Permite jugar a juegos en línea, comprar y descargar contenido, y también ofrece servicios como almacenamiento de juegos, streaming de contenido y acceso a aplicaciones como Steam Workshop.
```

Explica la función principal de Steam de forma útil. Llamar aplicación a Workshop es una imprecisión secundaria anotada; no se exige exhaustividad técnica.

## 7. APROBADO

**Entrada literal**
```text
Dime que hora es
```

**Respuesta literal**
```text
Son las 17 horas y 12 minutos.
```

Hora17:12 observada y conservada. La regresión capturada17:04 también está fijada con pruebas de frontera.

## 8. NO APROBADO

**Entrada literal**
```text
y la fecha?
```

**Respuesta literal**
```text
¿De qué fecha te refieres?
```

El modelo eligió system.time, pero domain_grounding retiró la lectura y produjo una aclaración innecesaria. Sigue fallando.

## 9. APROBADO

**Entrada literal**
```text
what time is it?
```

**Respuesta literal**
```text
It is 17:12.
```

Responde de manera útil y fiel a lo pedido.

## 10. APROBADO

**Entrada literal**
```text
Que gpu tengo?
```

**Respuesta literal**
```text
Tengo una GPU NVIDIA GeForce RTX 3060 en el portátil.
```

Identifica RTX3060 desde adapters de scope gpu_identity verificado, no desde el nombre del CPU.

## 11. APROBADO

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Okay, no subo el volumen.
```

Reconoce que no subirá el volumen. Mezcla breve entendible; sin efecto propuesto.

## 12. APROBADO

**Entrada literal**
```text
pon el volumen del PC al 35%
```

**Respuesta literal**
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 13. APROBADO

**Entrada literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen está en 35 y el sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 14. APROBADO

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal**
```text
El volumen está en 35 y el sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 15. APROBADO

**Entrada literal**
```text
turn up the volume
```

**Respuesta literal**
```text
how much and in which direction should the volume be adjusted?
```

Aceptada con observación: solicita una cantidad que no se especificó. Preguntar además la dirección es redundante, porque up ya la indica; no se convierte esa torpeza aislada en un bloqueo.

## 16. APROBADO

**Entrada literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 35. El sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 17. NO APROBADO

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
Este pedido está fuera de lo que hago en este PC.
```

Sigue rechazando la referencia al volumen. El selector propone ajuste relativo y el contador adicional interpreta varios efectos. No se completó la petición.

## 18. APROBADO

**Entrada literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
Hola, soy BAXY, tu compañero en el PC. ¿Cómo estás? 😎
```

Ahora responde quién es BAXY, conservando la pregunta después del saludo.

## 19. APROBADO

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
¿Te refieres al dispositivo de audio de salida o de entrada?
```

Aclaración aceptable: dispositivo de audio puede referirse a salida o micrófono. No se penaliza una ambigüedad razonable.

## 20. NO APROBADO

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
SIEMPRE. ¿Qué necesitas que haga con el audio?
```

Ya no arrastra la aclaración anterior, pero SIEMPRE y la pregunta posterior no expresan claramente que respetará la restricción. Sigue sin aprobar.

## 21. APROBADO

**Entrada literal**
```text
pon el volumen al 100
```

**Respuesta literal**
```text
Puse el volumen al 100. El sonido no está silenciado.
```

Restauración100 aplicada y verificada (t21); lectura independiente100/no silenciado (t22).

## 22. APROBADO

**Entrada literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen está en 100 y el sonido no está silenciado.
```

Restauración100 aplicada y verificada (t21); lectura independiente100/no silenciado (t22).

## Evidencia

astra-real-users-pending22/:CASES,PREREG,RESULT,paired,adjudication,events,compose-audit y turn-audit. Procedencias literales en CASES;los20 se organizaron para diagnóstico,no se afirma sesión histórica consecutiva. ASTRA-TRAMO-32.md documenta cambios y comparaciones por capas.
