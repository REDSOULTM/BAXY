# C03 — contraste AEC3 original248–249

Fuente242/DTLN512 y runtime instalado intactos. Sólo wheel original174 aislado.

248 verifica hashes del wheel y de todos los binarios/__init__ extraídos.
El puente512→160 añade128muestras, mínimo para max(n512 mod160).
La fuente nativa aporta64deframing+64desupresión; un impulso verifica128.
Puente frente a llamada nativa sobre25600muestras:igualdad exacta.
Retardo total256muestras(16ms), aplicado también al par de guardas.

Once salidas DSP congeladas antes de ASR:221/232/243+8humanos213, mismos
gains/onsets/máscaras que238. CPU media0.331–0.361ms por512muestras; sólo DSP.
249 usa captura/segmentación242, Silero reiniciado y ASR baxy.2/greedy real.
No efectos físicos, sin hints, cambio de umbrales ni inferencias de la reserva100.

## Decisión

AEC3 final no se adopta: aunque221/232/243 quedan sin cortes ni segmentos,
pierde palabras/cláusulas humanas y fragmenta h2-raw. El rechazo de fidelidad
persiste bajo las correcciones RAW/ASR actuales. No otra ganancia/variante.
La máscara de reproducción es fija: los múltiples eventos de cancelación
humanos son contrafactuales del replay, no un número de cortes físicos reales.

## Literales completos

### echo221

Cancelaciones en replay: []. Segmentos: 0.

### echo232

Cancelaciones en replay: []. Segmentos: 0.

### h0-near

Cancelaciones en replay: []. Segmentos: 1.

Referencia humana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo de clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje.

AEC3 segmento0: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

AEC3 ventana fija: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

DTLN512239 segmento0: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

DTLN512239 ventana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

### h0-raw

Cancelaciones en replay: [182, 194, 306, 323, 336, 354, 367]. Segmentos: 1.

Referencia humana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo de clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje.

AEC3 segmento0: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo de extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

AEC3 ventana fija: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

DTLN512239 segmento0: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje.

DTLN512239 ventana: Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje.

### h1-near

Cancelaciones en replay: []. Segmentos: 1.

Referencia humana: Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la Plaza de San Pedro.

AEC3 segmento0: Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro.

AEC3 ventana fija: Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro.

DTLN512239 segmento0: Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro.

DTLN512239 ventana: Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro.

### h1-raw

Cancelaciones en replay: [193, 199, 306, 319, 327, 333, 360, 365]. Segmentos: 1.

Referencia humana: Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la Plaza de San Pedro.

AEC3 segmento0: Tanta la cantidad de gente que se concentró que no todos pudieron acceder al general en la plaza de San Pedro.

AEC3 ventana fija: Tanta la cantidad de gente que se concentró que no todos pudieron acceder al general en la plaza de San Pedro.

DTLN512239 segmento0: Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro.

DTLN512239 ventana: Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro.

### h2-near

Cancelaciones en replay: []. Segmentos: 1.

Referencia humana: However, due to the slow communication channels, styles in the west could lag behind by 25 to 30 year.

AEC3 segmento0: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

AEC3 ventana fija: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

DTLN512239 segmento0: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

DTLN512239 ventana: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

### h2-raw

Cancelaciones en replay: [151, 203, 306]. Segmentos: 4.

Referencia humana: However, due to the slow communication channels, styles in the west could lag behind by 25 to 30 year.

AEC3 segmento0: How

AEC3 segmento1: Communication channels.

AEC3 segmento2: Styles in the West could lag.

AEC3 segmento3: To thirty years.

AEC3 ventana fija: How communication channels styles in the West could last to 30 years.

DTLN512239 segmento0: However, due to the slow communication channels, styles in the West can lag behind by 25 to 30 years.

DTLN512239 ventana: However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years.

### h3-near

Cancelaciones en replay: []. Segmentos: 1.

Referencia humana: All nouns, alongside the word Sie for you, always begin with a capital letter, even in the middle of a sentence.

AEC3 segmento0: All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence.

AEC3 ventana fija: All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence.

DTLN512239 segmento0: All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence.

DTLN512239 ventana: All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence.

### h3-raw

Cancelaciones en replay: [137, 144, 161, 169, 179, 197, 347, 365]. Segmentos: 1.

Referencia humana: All nouns, alongside the word Sie for you, always begin with a capital letter, even in the middle of a sentence.

AEC3 segmento0: All now for one point for you. Always begin with a capital letter.

AEC3 ventana fija: All now for one thing will say for you. Always begin with a capital letter.

DTLN512239 segmento0: All nouns alongside the world say for you. Always begin with a capital letter, even in the middle of a sentence.

DTLN512239 ventana: All nouns alongside the world say for you. Always begin with a capital letter, even in the middle of a sentence.

### echo243

Cancelaciones en replay: []. Segmentos: 0.

## Siguiente250

Localizar primera transformación que pierde palabras: inspeccionar el bundle
diagnóstico176 existente, que expone la salida lineal anterior al supresor.
Primero exigir paridad de salida final176 con248 sobre las once señales RAW
actuales. Si coincide, guardar salida lineal/pares con retardo nativo64+puente128
(192muestras), comprobado por impulso, antes de ASR. No instalar ni recompilar
de entrada, no adoptar salida lineal por conservar voz si deja pasar eco.
Si la paridad no coincide, diagnosticar la divergencia antes de comparar textos.
Esto es una medición intermedia, no otro barrido de modelos o ganancias.

C03 completo sigue activo: eco robusto, ASR/wake/voz humana física,8rutas,
100humanos sin congelar y100/100,averías/recuperación,UI/audio/LLM/4GB,
instalación/runtime,C04–C09,Full/publicación fuera main.
