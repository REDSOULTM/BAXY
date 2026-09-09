# C03 — separación de admisión y reconocimiento252–254

##252 y253: hipótesis y corrección del instrumento

252 no produjo resultados: al copiar los globals de voice antes de conectar
el stream finito, el método de captura leyó la cola PCM vacía original. Se
confirmaron y detuvieron los PIDs42836/47768; exec86038 recogido exit-1.
Se conserva ABORTED.json. No se cuenta como fallo o pase del producto.
253 usa el mismo método experimental en los globals vivos de voice, como el
método original. No se modificó ningún archivo del producto instalado.

El mismo AEC3 produce dos señales: lineal para ASR y candidata de voz; final
para confirmar admisión y energía de interrupción. Hay estados VAD separados.
Se retrasa lineal64 para alinear con final a256muestras. UmbralVAD0.5,
tres frames para barge-in, energía vigente, guarda raw y pausa0.7s intactos.
La continuidad admite actividad de cualquiera de las dos vistas. Se conserva
el comienzo en candidato sin publicar/ducking antes de confirmar; terminarTTS
por sí solo ya no convierte un candidato en una intervención admitida.

Tres controles de eco quedan sin cancelaciones ni segmentos. La primera
cláusula de h2raw se recupera, aunque siguen dos segmentos: ambos contienen
ahora contenido humano (no D boxy). No contar dos segmentos como fallo por
el número, ni presentarlos como una única intervención física comprobada.
Persisten diferenciasASR:h1near pudier, h3raw world/given por word/even.
No declarar ocho pases semánticos ni aceptación global del reconocimiento.

## Literales253

### echo221

Eventos en replay con máscara fija: [].

### echo232

Eventos en replay con máscara fija: [].

### h0-near

Eventos en replay con máscara fija: [].

Referencia humana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo de clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje.

Segmento[87552:261632]: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

Ventana fija: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

### h0-raw

Eventos en replay con máscara fija: [182, 194, 306, 323, 336, 354, 367].

Referencia humana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo de clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje.

Segmento[59392:262144]: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

Ventana fija: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

### h1-near

Eventos en replay con máscara fija: [].

Referencia humana: Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la Plaza de San Pedro.

Segmento[93184:212992]: Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro.

Ventana fija: Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro.

### h1-raw

Eventos en replay con máscara fija: [193, 199, 306, 319, 327, 333, 360, 365].

Referencia humana: Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la Plaza de San Pedro.

Segmento[93184:213504]: Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro.

Ventana fija: Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro.

### h2-near

Eventos en replay con máscara fija: [].

Referencia humana: However, due to the slow communication channels, styles in the west could lag behind by 25 to 30 year.

Segmento[72192:210432]: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

Ventana fija: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

### h2-raw

Eventos en replay con máscara fija: [151, 189, 202, 306].

Referencia humana: However, due to the slow communication channels, styles in the west could lag behind by 25 to 30 year.

Segmento[62464:129536]: However, due to the slow communication channels.

Segmento[129536:210432]: styles in the West could lag behind by twenty five to thirty years.

Ventana fija: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

### h3-near

Eventos en replay con máscara fija: [].

Referencia humana: All nouns, alongside the word Sie for you, always begin with a capital letter, even in the middle of a sentence.

Segmento[65024:201728]: All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence.

Ventana fija: All nouns alongside the word say for you always begin with a capital letter even in the middle of a sentence

### h3-raw

Eventos en replay con máscara fija: [137, 144, 161, 169, 179, 197, 347, 365].

Referencia humana: All nouns, alongside the word Sie for you, always begin with a capital letter, even in the middle of a sentence.

Segmento[59392:201216]: All nouns alongside the world say for you. Always begin with a capital letter, given in the middle of a sentence.

Ventana fija: All nouns on one side of the world say for you. Always begin with a capital letter, even in the middle of a sentence.

### echo243

Eventos en replay con máscara fija: [].

##254: física experimental

Mismo AEC nativo176 y método252 con conexión corregida253. Los tres impulsos
(lineal/final/raw) coinciden en8256 para entrada8000:retardo total256muestras.
No se sustituye el proveedor instalado; el driver declara el enlace experimental.
42.112s,1316frames,cuatro Piper,0barge-in,0transcripciones,0errores.
Windows effects[],volumen/mute restaurado exactamente a0/true, todos workers
cerrados. Wake sigue unavailable/wake_verifier_manifest_missing, sin bypass.
No persona hablando simultáneamente, no UI/LLM ni presupuesto conjunto.
Piper se regenera: se conservan las cuatro ondas efectivas, no se llaman PCM
idénticos a240/243. TRACE_METRICS.json confirma señal presente y coste del DSP.

## Siguiente255: integración candidata, manteniendo límites

La separación mejora la combinación eco/contenido frente a249/251, y supera
una prueba física. Merece preparar una integración reproducible; no cierreC03.
Una sola implementación AEC, sin filtros en cascada ni pesos nuevos. Sustituir
DTLN productivo conservando sus activos/evidencia externa. Native176 sólo es
diagnóstico: fabricar wheel propio reproducible con exportación lineal necesaria
y sin métricas nativas sin uso, desde source174 atestado. Ver build_sherpa_runtime
como patrón de receta/hash/versión local, no copiar complejidad innecesaria.
Actualizar lock/requirements, retirar dependenciasDTLN que sólo servían a él,
revisar overrides de assets antes de retirar la declaración obsoleta, instalar
por lock y validar puente/ownership/dosVAD/colas/wake/provisional/errores.
No promover por este panel; conservar regresionesASR y probar de nuevo producto
con sus ocho rutas y UI/voz/recursos. No Full durante la reparación.

Se releyeron C03_ASTRA_AUTORIDAD y C03_RESPUESTA_VERAZ:el criterio de cierre es
la utilidad/fidelidad de cien respuestas normales reales, ocho rutas,recuperación,
producto/UI/runtime/voz y Full/publicación. Estos controles de desarrollo no
son la reserva ni certifican C08. Se mantiene el objetivo completo sin inventar
una cuota de transcripciones FLEURS perfectas ni ocultar sus errores medidos.
