# C03 — presupuesto de conocimiento y alcance de negación

Tramo 39, 2026-09-06. Veintitrés entradas/respuestas literales: diez sondas y trece turnos de producto. Son desarrollo consumido y controles sintéticos declarados; ninguno pertenece a la reserva de cien.

## Cambio integrado

El presupuesto de conocimiento pasa de 128 a 256 tokens. Se adopta la política ya medida en el tramo38: una frase por defecto, con excepción explícita cuando se pide profundizar, detalle o un formato. No cambia el modelo, sampler, identidad, catálogo ni otros roles. No garantiza que cualquier respuesta detallada quepa en256.

Se hereda INVESTIGACION_MODELO_C03.md: ficha específica Qwen3-4B-Instruct-2507, documentación del servidor b9980, papers y reportes reproducibles. La evidencia anterior de Steam ya diferenciaba truncamiento de desconocimiento. Aquí se cambia sólo el presupuesto respecto de cada política retenida y se miden tokens, recursos y producto.

## Sonda controlada del presupuesto

[Prerregistro](astra-knowledge-budget/PREREG.json), [payloads](astra-knowledge-budget/posts.jsonl), [respuestas](astra-knowledge-budget/replies.jsonl), [recursos](astra-knowledge-budget/RESULT.json). Wrapper BAXY con historial vacío, temperatura0 y max_tokens256; no es modelo aislado. Comparadores128 están en las sondas del tramo38. 11,94s; GPU3497,56MiB; RAM2857,54MiB; registro intacto; proceso terminó0.

### Sonda 1 — current_256

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua es H₂O. Es una molécula compuesta por dos átomos de hidrógeno y uno de oxígeno. Es la fórmula química más conocida y fundamental para la vida.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 2 — current_256

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (78%) y oxígeno (21%), mientras que H2O es el agua. El aire no contiene agua en forma líquida ni como compuesto principal.
```

NO ACREDITA mejora de precisión: el aumento de presupuesto conserva ampliaciones problemáticas de la política actual.

### Sonda 3 — current_256

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve. Permite descargar, jugar, comprar y gestionar juegos, además de ofrecer servicios como actualizaciones automáticas, soporte técnico y comunidad de jugadores. También incluye aplicaciones como Steam Workshop para crear y compartir contenido personalizado. Es muy popular en el mundo del gaming por su amplia selección y facilidad de uso.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 4 — current_256

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network. It's what you see when you scan for available networks on your device. You need to enter the SSID to connect to a Wi-Fi network. It's like a password for your wireless connection, but instead of a password, it's a name.
```

NO APROBADO: analogía falsa entre SSID y contraseña.

### Sonda 5 — current_256

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0,9%), dióxido de carbono (0,04%) y pequeñas cantidades de gases inanimados como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es un componente variable que influye en el clima, la temperatura percibida y la capacidad del aire para retener gases como el CO₂. Aumenta la conductividad térmica y afecta la evaporación y la condensación. Su presencia también modifica la densidad del aire y puede influir en la salud respiratoria y en procesos biológicos.
```

NO ACREDITA mejora de precisión: el aumento de presupuesto conserva ampliaciones problemáticas de la política actual.

### Sonda 6 — brief_by_request

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua es H₂O.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 7 — brief_by_request

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (78%) y oxígeno (21%), mientras que H2O es el agua.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 8 — brief_by_request

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 9 — brief_by_request

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices use to connect to the internet.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

### Sonda 10 — brief_by_request

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0.9%), dióxido de carbono (0.04%) y pequeñas cantidades de gases inanimados como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es un componente variable que influye en la temperatura, la sensación térmica y en procesos como la evaporación y la condensación. Aunque no es un gas fijo, el vapor de agua afecta directamente el clima, la salud humana y los procesos biológicos, como la fotosíntesis y la respiración.
```

ÚTIL en esta sonda; no prueba conducta integrada con historial.

## Producto — astra-knowledge-budget-integrated8

[Prerregistro](astra-knowledge-budget-integrated8/PREREG.json), [casos](astra-knowledge-budget-integrated8/CASES.json), [eventos y respuestas](astra-knowledge-budget-integrated8/paired.json), [traza de interpretación](astra-knowledge-budget-integrated8/turn-audit.jsonl), [resultado](astra-knowledge-budget-integrated8/RESULT.json). Runtime registrado, perfil propio, sin overrides de modelo/sampling. La segunda corrida prueba una variante de resolución por cláusulas que se retiró al no mejorar el producto.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

APROBADO: identifica correctamente H₂O.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
¿Te refieres a que el aire es H₂O (agua), o estás preguntando si el aire contiene oxígeno o otro compuesto similar?
```

NO APROBADO: pide aclaración innecesaria. La primaria ya devuelve mode=clarify; no es el compositor recortando una respuesta correcta.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, que permite descargar, jugar, comprar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

APROBADO: explicación sencilla de Steam.

### Turno 4

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0,9%), dióxido de carbono (0,04%) y pequeñas cantidades de gases como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es el componente que varía según la temperatura y el lugar, y juega un papel clave en el clima, la evaporación, la condensación y el equilibrio hídrico en el entorno.
```

APROBADO: completa composición del aire y papel de humedad, sin corte visible.

### Turno 5

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices use to connect to the internet. It's like a password or identifier that lets your phone, laptop, or tablet know which network to join.
```

NO APROBADO: añade analogía falsa con contraseña.

### Turno 6

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

APROBADO: nombre observado del endpoint, volumen y silencio conservados.

### Turno 7

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

NO APROBADO: pierde la lectura de hora solicitada después de la negación social.

### Turno 8

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
19:58
```

APROBADO: publica la lectura real de hora.

## Producto — astra-clause-scope5

[Prerregistro](astra-clause-scope5/PREREG.json), [casos](astra-clause-scope5/CASES.json), [eventos y respuestas](astra-clause-scope5/paired.json), [traza de interpretación](astra-clause-scope5/turn-audit.jsonl), [resultado](astra-clause-scope5/RESULT.json). Runtime registrado, perfil propio, sin overrides de modelo/sampling. La segunda corrida prueba una variante de resolución por cláusulas que se retiró al no mejorar el producto.

### Turno 1

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

NO APROBADO: persiste pérdida de lectura solicitada.

### Turno 2

**Entrada literal**
```text
I don't mind, tell me the time
```

**Respuesta literal**
```text
I couldn't understand your request. Please rephrase it so I can assist you better.
```

NO APROBADO: persiste pérdida de lectura solicitada en inglés.

### Turno 3

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal**
```text
No abro Steam, te digo que son las 14 horas.
```

NO APROBADO: publica una hora no verificada; no contar como recuperación ni éxito.

### Turno 4

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal**
```text
No te digo la hora. ¿Qué necesitas ahora?
```

APROBADO: reconoce la prohibición sin decir la hora.

### Turno 5

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
20:04
```

APROBADO: lectura real de hora tras el fallo.

## Variante retirada y causa siguiente

En resolve_explicit_effects se probó permitir una orden directa en cualquier cláusula ya separada, añadiendo `and not any(_is_direct_request(clause) for clause in clauses)` a la comprobación de entrada. La lectura española aislada empezó a resolverse, pero unresolved_compound_contract siguió devolviendo veto por negación global; la cláusula inglesa `I don't mind` siguió contándose como acción desconocida. La primaria aún eligió conversación sin observación y se publicó una hora inventada en un control. Este ajuste fue retirado; no queda como reparación parcial.

Los tests existentes pasaron2454/2454 durante esa variante. Los seis controles nuevos dieron5pass/1fail (el reconocimiento inglés), y el producto sólo2/5útiles. Se conservaron los resultados; no se promovió la variante ni se declara resuelto el requisito inglés. Los controles técnicos retirados exigían resolver las dos frases sociales anteriores, y rechazar `no me digas la hora`, `don't tell me the time`, `no uses herramientas, dime la hora`, `traduce: no me molesta, dime la hora`.

Pendiente: conservar alcance de negación en el contrato semántico completo, no sólo en el reconocimiento léxico. No repetir el mismo parche ni añadir una excepción para «no me molesta». La aclaración del aire nace en la primaria; SSID falla en la prosa incluso con política breve. El cambio de presupuesto no se presenta como solución de esos fallos.

## Preparación del corpus

La auditoría acotada cuenta560textos únicos en traces (la copia histórica y la viva se solapan), 115en Carter_v1 y16ficheros de sesiones .gemma4. El detalle permanece privado en LOCALAPPDATA/BAXY/C03-real-user-pool-20260906/session_source_candidates.json. Una sesión contiene transcripciones compatibles con audio de fondo; observed_user y request_start no certifican por sí solos autor humano ni intención dirigida a BAXY. Revisar origen/contexto antes de reservar100.

## Validación final de la tanda

Tras retirar la variante de cláusulas:

`python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py tests/test_effect_intent.py tests/test_c03_request_preservation.py -q`
→ 2609 pass, 0 skips, 47,85 s; proceso8528 terminado0.

`scripts/test_source_quality.ps1` → Fast verde, compilación sin errores ni avisos;
proceso14130 terminado0. Ruff y git diff --check pasan. Logs:
scratchpad/c03-knowledge-final-owner.log y c03-knowledge-final-fast.log.
No se ejecutó Full: desarrollo y aceptación todavía pendientes.
