# C03 —236–237: DTLN128 reduce cortes, pero empeora transcripciones humanas

Se reconstruyen diez líneas temporales exactas: las capturas físicas221/232 y
ocho controles humanos213 (cuatro personas, voz sola y mezcla RAW con eco).
Speex y el adaptador DTLN128 heredado182 parten de estado vacío; ganancias,
onsets, máscaras de salida y umbrales quedan fijados antes del reconocedor.
No se instala ninguna dependencia ni se modifica la fuente230.

236 calcula y conserva los veinte resultados completos. Las diez salidas de
Speex son idénticas muestra a muestra a la evidencia previa. DTLN128 usa CPU,
1hilo, con media por bloque de512muestras1.02–1.38ms y máximop99de2.84ms en
esta corrida. Es medición aislada del DSP, no presupuesto final del producto.

237 pasa los20resultados por la segmentación real230, Silero y baxy.2. También
decodifica las16ventanas humanas fijas, permitiendo distinguir un mal inicio
de segmento de una transcripción ya mala con la ventana entera. Las diez
líneas base Speex reproducen rangos, textos y cancelaciones previos.

## Eco

-221: ambos producen cero segmentos y cero cancelaciones.
-232: Speex conserva dos cancelaciones y«Toll.»/«S». DTLN128 no solicita
  cancelaciones, pero produce un segmento«F». La máscara232 y el audio ya
  contienen los cortes de Speex físicos: este resultado no predice qué habría
  sucedido con una salida continua bajo DTLN. No se declara aceptación.

## Voz humana

DTLN128 conserva las frases del humano0. En humano2 solo+AEC recupera30años,
que Speex transcribía como3. Sin embargo, sobre segmentos reales:

- Humano1 solo: Speex conserva«pudieron acceder»; DTLN128 da«pudier» y pierde
  «acceder». Con mezcla RAW, DTLN128 pierde el principio«Fue tanta la cantidad
  de gente que se concentró» aunque su ventana fija sí lo reconoce.
- Humano2 RAW: DTLN128 separa la frase en dos, pierde«due to» y cambia«lag» a
  «land». La ventana fija conserva«due to», pero también cambia«lag» a«land».
- Humano3: aparecen«world» por«word» y«almost like» por«alongside» en la mezcla.
  La ventana fija de la mezcla tampoco conserva el contenido completo.

Por estas regresiones no se adopta128. No se afirma que los filtros hayan
eliminado físicamente todas esas palabras: se ha demostrado degradación en
la transcripción o segmentación del producto; sus causas internas requieren
aislamiento si se decide trabajar sobre ese backend.

## Siguiente comparación acotada

El README original conservado179 ofrece128/256/512 y señala512 como la versión
presentada por el autor al reto. Los modelos512 ya están descargados y fijados
en180.238 calculará únicamente512 sobre las mismas diez entradas;239 usará
la misma segmentación, reconocedor y ventanas. Se reutilizan las líneas base
236/237, sin repetirlas, buscar ganancias ni modificar umbrales. Una reducción
de eco no basta si empeora el contenido humano.
