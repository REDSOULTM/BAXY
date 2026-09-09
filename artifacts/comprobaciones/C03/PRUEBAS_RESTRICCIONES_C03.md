# Pruebas de restricciones — C03, tramo 36

2026-09-06. Diagnóstico de desarrollo: 56 respuestas a ocho entradas literales consumidas del corpus; no son 56 casos independientes ni la reserva de cien. No se certifica autoría humana o ausencia de exposición al entrenamiento.

Se comparó el compositor existente con una representación de restricción sin operaciones ni observaciones, luego una instrucción de alcance temporal, el muestreo documentado con tres semillas y el alcance como dato. Los prompts completos y respuestas brutas están en los enlaces de cada corrida. No se cambió el producto ni el runtime registrado.

Criterio aplicado a mano conforme a las aclaraciones del dueño: aceptar reconocimientos sencillos, variaciones de estilo y compromisos de primera persona de no actuar. La palabra «nunca» por sí sola no convierte un reconocimiento en una afirmación falsa del estado del PC. No aceptar observaciones inventadas, garantías sobre cambios ajenos a BAXY ni capacidades de vigilancia añadidas. Esta adjudicación se realiza después de las sondas y no altera sus preregistros ni demuestra aceptación final.

Corrección de la interpretación inicial del experimento: la insistencia en primera persona exacta y en rechazar todo «nunca» sobrecalificaba el estilo. No usarla para justificar más filtros, más prompts o un cambio de modelo.

Los dictámenes siguientes son del contenido emitido por estas sondas. Las variantes directas conocen de antemano que la entrada es una restricción; todavía no demuestran que BAXY la identifique y la presente bien en una conversación real.

## astra-constraint-purpose

11/16 respuestas útiles según el criterio anterior. 6.81 s; pico GPU 3497.56 MiB; pico RAM 2839.57 MiB. Registro intacto: True.

[Preregistro y procedencia](astra-constraint-purpose/PREREG.json) · [Mensajes completos enviados y devueltos](astra-constraint-purpose/posts.jsonl) · [Respuestas](astra-constraint-purpose/replies.jsonl) · [Recursos](astra-constraint-purpose/RESULT.json)

### 1. existing_composer

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I'll not open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 2. existing_composer

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
No pongo música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 3. existing_composer

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
No cierres Spotify porque así no pierdes la conexión con tus playlists.
```

**NO APROBADO:** Añade una consecuencia no sustentada sobre la conexión con playlists y devuelve una instrucción al usuario.

### 4. existing_composer

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
No cierro Spotify porque está en uso.
```

**NO APROBADO:** Afirma que Spotify está en uso sin haberlo observado.

### 5. existing_composer

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 6. existing_composer

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
No baje el brillo, estábamos en modo de ahorro.
```

**NO APROBADO:** Afirma un modo de ahorro previo sin evidencia.

### 7. existing_composer

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
Asegúrate de que el sonido esté activo.
```

**NO APROBADO:** Devuelve al usuario una tarea de comprobar el sonido en vez de reconocer su restricción.

### 8. existing_composer

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
No subo el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 9. constraint_purpose

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
Got it, I won't open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 10. constraint_purpose

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Claro, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 11. constraint_purpose

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 12. constraint_purpose

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 13. constraint_purpose

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
Entendido, no abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 14. constraint_purpose

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, nunca bajará el brillo.
```

**NO APROBADO:** Garantiza que el brillo nunca bajará, aunque BAXY sólo puede comprometer su propia actuación.

### 15. constraint_purpose

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
Entendido, nunca silenciaré el audio.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 16. constraint_purpose

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

## astra-constraint-scope

8/8 respuestas útiles según el criterio anterior. 4.41 s; pico GPU 3493.56 MiB; pico RAM 2819.20 MiB. Registro intacto: True.

[Preregistro y procedencia](astra-constraint-scope/PREREG.json) · [Mensajes completos enviados y devueltos](astra-constraint-scope/posts.jsonl) · [Respuestas](astra-constraint-scope/replies.jsonl) · [Recursos](astra-constraint-scope/RESULT.json)

### 1. constraint_purpose

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 2. constraint_purpose

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Entendido, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 3. constraint_purpose

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cerraré Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 4. constraint_purpose

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify mientras estés usando tu PC.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 5. constraint_purpose

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 6. constraint_purpose

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, no bajaré el brillo.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 7. constraint_purpose

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio nunca.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 8. constraint_purpose

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

## astra-constraint-sampling

23/24 respuestas útiles según el criterio anterior. 7.45 s; pico GPU 3493.56 MiB; pico RAM 2819.09 MiB. Registro intacto: True.

[Preregistro y procedencia](astra-constraint-sampling/PREREG.json) · [Mensajes completos enviados y devueltos](astra-constraint-sampling/posts.jsonl) · [Respuestas](astra-constraint-sampling/replies.jsonl) · [Recursos](astra-constraint-sampling/RESULT.json)

### 1. constraint_purpose_seed0

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 2. constraint_purpose_seed0

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Entendido, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 3. constraint_purpose_seed0

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierre Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 4. constraint_purpose_seed0

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, no cerraré Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 5. constraint_purpose_seed0

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 6. constraint_purpose_seed0

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, no bajaré el brillo.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 7. constraint_purpose_seed0

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 8. constraint_purpose_seed0

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 9. constraint_purpose_seed17

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 10. constraint_purpose_seed17

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Entendido, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 11. constraint_purpose_seed17

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cerraré Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 12. constraint_purpose_seed17

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, no cerraré Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 13. constraint_purpose_seed17

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 14. constraint_purpose_seed17

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, no bajaré el brillo.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 15. constraint_purpose_seed17

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio nunca.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 16. constraint_purpose_seed17

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 17. constraint_purpose_seed42

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 18. constraint_purpose_seed42

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Entendido, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 19. constraint_purpose_seed42

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 20. constraint_purpose_seed42

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 21. constraint_purpose_seed42

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador, como tú me has indicado.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 22. constraint_purpose_seed42

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, no bajaré el brillo.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 23. constraint_purpose_seed42

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio, siempre estaré atento a cada sonido.
```

**NO APROBADO:** Añade una promesa de atender cada sonido que esta prueba no establece.

### 24. constraint_purpose_seed42

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
No subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

## astra-constraint-scope-data

8/8 respuestas útiles según el criterio anterior. 4.66 s; pico GPU 3493.56 MiB; pico RAM 2818.98 MiB. Registro intacto: True.

[Preregistro y procedencia](astra-constraint-scope-data/PREREG.json) · [Mensajes completos enviados y devueltos](astra-constraint-scope-data/posts.jsonl) · [Respuestas](astra-constraint-scope-data/replies.jsonl) · [Recursos](astra-constraint-scope-data/RESULT.json)

### 1. constraint_purpose

**Entrada literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome — I'm respecting that rule for now.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 2. constraint_purpose

**Entrada literal**
```text
no pongas música
```

**Respuesta literal**
```text
Entendido, no pondré música.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 3. constraint_purpose

**Entrada literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cerraré Spotify.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 4. constraint_purpose

**Entrada literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Entendido, no cierro Spotify mientras estés en la sesión.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 5. constraint_purpose

**Entrada literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
Entendido, no abriré el navegador.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 6. constraint_purpose

**Entrada literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
Entendido, no bajaré el brillo.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 7. constraint_purpose

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
Entendido, nunca silenciaré el audio.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

### 8. constraint_purpose

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.

## Límites y decisión

50/56 respuestas aprobadas en conjunto, con entradas y variantes repetidas: esta suma no es una tasa independiente de calidad de BAXY ni un porcentaje del goal. El compositor existente obtiene 4/8; la representación específica inicial 7/8; la variante de alcance 8/8; muestreo 23/24; alcance como dato 8/8.

No se promueve el muestreo: añade una promesa de vigilancia en una semilla y no ofrece una ventaja demostrada frente a la variante determinista. La representación específica sí ofrece una hipótesis útil de integración, pendiente de verificar la detección de restricciones frente a negaciones conversacionales y acciones positivas posteriores.

Errata de descripción conservada: algunos scripts derivados mantienen en PREREG.method la descripción de dos etapas del primer experimento, aunque sus listas stages y los posts muestran una etapa o tres semillas. No se reescribieron los preregistros congelados. Las 56 filas anteriores proceden de replies.jsonl, no de esa descripción heredada.

Herencia y estado del arte: se reutilizó INVESTIGACION_MODELO_C03.md (ficha oficial Qwen3-4B-Instruct-2507, configuración de generación y llama.cpp b9980). La búsqueda exploratoria de otros modelos no produjo una comparación local nueva; no se adopta ni se descarta otro modelo a partir de ella.
