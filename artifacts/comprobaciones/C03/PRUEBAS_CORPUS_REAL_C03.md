# C03 — primeras 20 entradas literales de los logs

Evaluación manual: **14 respuestas aceptadas (dos con observaciones), 6 fallos**. Son casos de desarrollo, no los cien de aceptación ni un porcentaje de completitud del goal.

Las entradas se copiaron del conjunto heredado del Goal 10 y los logs locales, sin traducir, corregir erratas ni añadir «en spanglish». La secuencia de esta corrida fue organizada para el diagnóstico: no se afirma que estos veinte turnos fueran consecutivos en una sesión histórica. Que una entrada figure en un log no prueba por sí solo autoría humana ni independencia del entrenamiento. CASES.json conserva todas las referencias.

Se aprueban explicaciones sencillas, español ante mezcla natural y aclaraciones razonables. No se exige alternar idiomas. Se rechazan omisiones de lo pedido, pérdida de contexto, silencio ante una petición normal y afirmaciones sin datos suficientes.

Runtime registrado: Qwen3-4B-Instruct-2507 Q4_K_M base, sin LoRA ni overrides de modelo. Conductor del producto, sin ventana y con wake desactivado por diseño. 117,09 s; pico atribuido de GPU 3499,56 MiB; proceso terminado con código 0. El código 0 acredita ejecución de la medición, no calidad de las respuestas. Full pendiente.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:14349` · ID `98c059da76bf5e7c9848d4a9ce59c003bdf10f8db9e697a2f3e915e898bc18ba`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:32184` · ID `0da72197e898ebe1814471a76048ed137a089f595c1e7038f2b70e98645e7652`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:11177` · ID `002054cfe5d3304f488e1f5f18b0ccde054d0f45f0ea292169f136b564bec307`.

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

Procedencia: `gemma4_local/sessions/b9ed21dbb103.json` · `turns/10` · ID `c1462d73e8235964a0ee3211585afbc4e44375a76b0810aa350140d450cd8b29`.

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

Procedencia: `gemma4_local/sessions/b9ed21dbb103.json` · `turns/12` · ID `c773877cafeef7aa4dc25eb6e61efc90a6eccc7c5426490eccf970b92f80cd5d`.

## 6. APROBADO

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma que permite descargar, jugar y gestionar videojuegos en línea.
```

Responde de manera útil y fiel a lo pedido.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:34124` · ID `93617357913a0ea6d4e872cd678164debc36fcef08da79daedb3e5d75c0cfee1`.

## 7. APROBADO

**Entrada literal**
```text
Dime que hora es
```

**Respuesta literal**
```text
Son las 16 horas y 34 minutos.
```

Responde de manera útil y fiel a lo pedido.

Procedencia: `D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI\Carter_v1\carter_session.log` · `line:40503` · ID `fb76695707f5c912d07bcec0a43b24bec5ac354f27059113ceaff56b2131a8b1`.

## 8. NO APROBADO

**Entrada literal**
```text
y la fecha?
```

**Respuesta literal**
```text
¿De qué fecha te refieres?
```

Después de pedir la hora, pide aclarar de qué fecha se habla. Pierde el contexto cotidiano.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:12346` · ID `62f9c6512803bdae2964f2a4ebc1a1ade6c70fc92c7a21690f42cd13130a241e`.

## 9. APROBADO

**Entrada literal**
```text
what time is it?
```

**Respuesta literal**
```text
It's 16:34.
```

Responde de manera útil y fiel a lo pedido.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:35201` · ID `482bbb9128050f734a2e44f15c0bb1066848c6b18444a90c771061c030ff2534`.

## 10. NO APROBADO

**Entrada literal**
```text
Que gpu tengo?
```

**Respuesta literal**
```text
Tengo la GPU integrada del procesador, que es Radeon Graphics.
```

El resultado de system.status contiene el nombre del CPU, no un inventario de GPU. Presenta Radeon Graphics como respuesta verificada y omite la GPU dedicada; los datos recibidos no sustentan esa identificación.

Procedencia: `D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI\Carter_v1\carter_session.log` · `line:40356` · ID `19d586f4f40fcc654e5d199954f278852efb32b7c1a309e087877617d9241985`.

## 11. NO APROBADO

**Entrada literal**
```text
no subas el volumen
```

**Respuesta visible:** no hubo respuesta final en lenguaje natural. El estado técnico fue `composition_failed`.

No publica una respuesta útil a una restricción negativa. Termina en composition_failed (missing_literal_fact;recovery:missing_literal_fact;retry_exhausted), con controles disponibles. Los borradores internos no son respuestas visibles.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:12669` · ID `b5a155050f4f58891710cc0b02043f466897e297259a9a064f126157ce8dc126`.

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

Procedencia: `D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI\Carter_v1\carter_session.log` · `line:1693` · ID `a05566639e402d487490acfcad2cc80e5233541d507818dd76d51eed9605372d`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:1229` · ID `16485ae7910a5e59f87a8233ac50e941375f07e8f96330c4b42b90fe5e3f4618`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:40270` · ID `acff43c4b843b390b60c3f56daf2f02a187cc4b0ccd383a5b8886ba133f2bbd1`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:40396` · ID `a59b4669cbf4ce8033348da3f360a6572fc986a1da03f725a9b6be545f8f786f`.

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

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:16563` · ID `80d5cfc93603cfedda1c26aeda30ef97586041b005af6f6f09c1a45c14d45189`.

## 17. NO APROBADO

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
Este pedido está fuera de lo que hago en este PC.
```

Tras consultar el volumen, rechaza ponerlo a 100 como fuera de sus funciones. No ejecuta la restauración: pierde el referente.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:29578` · ID `950bf158bb9ed1512d7d1bbbeca87078b7a47901077c5ea5b8547a1fe348abb9`.

## 18. NO APROBADO

**Entrada literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
¿En qué puedo ayudarte?
```

Saluda pero omite responder quién es. El problema es la pregunta ignorada, no el estilo del saludo.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:64752` · ID `f7390173d73af32343ebbdb2be8eee94ed90c4ff7add6fc60416af0ae9313b82`.

## 19. APROBADO

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
¿Estás refiriéndote al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

Aclaración aceptable: dispositivo de audio puede referirse a salida o micrófono. No se penaliza una ambigüedad razonable.

Procedencia: `D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI\Carter_v1\carter_session.log` · `line:22254` · ID `6cb550776b93b4cef257099d46dda820f576d6455d7cb5fd1c4dca28093fa69d`.

## 20. NO APROBADO

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
¿Te refieres al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

Repite la aclaración sobre dispositivos del turno anterior; no reconoce la nueva restricción de no silenciar el audio.

Procedencia: `probando_gemma4/gemma4_agent/data/traces.jsonl` · `line:2047` · ID `adcfc708d00cf2d8af02b81dc2eb1c94400363dc0241de12f6ea8cc897da012c`.

## Evidencia y límites

- `astra-real-users-development20/CASES.json`: expectativas y referencias anteriores a la corrida.
- `PREREG.json` y `RESULT.json`: candidato, huellas y recursos.
- `paired.json`, `events.jsonl` y `compose-audit.jsonl`: entradas, respuestas, estados y hechos recibidos.
- `adjudication.json`: dictamen individual; no se obtiene del estado published_final.
- El turno 12 verificó el cambio real de 100 a 35. El turno 17 falló al restaurarlo. La restauración posterior se registra aparte en `astra-real-users-volume-restore/` y no corrige retrospectivamente ese fallo.

Pendiente: revisar idiomas y autoría del conjunto provisional, completar cobertura histórica, recuperar contexto original de las secuencias seleccionadas y reservar entradas no consumidas para aceptación. No ejecutar efectos de un log sin revisar la situación actual.
