# Detector estadístico: no adoptado

Lingua 2.2.0, instalado sólo en scratchpad/c03-lingua-deps (wheel 170.1 MB).
13/16 según etiquetas preregistradas; pierde tres mezclas breves. 0.155 s total,
5.81 MiB de incremento RSS en este proceso; no usa GPU. La documentación advierte
que la segmentación mixed es experimental y pierde precisión en textos breves:
https://github.com/pemistahl/lingua-py#117-detection-of-multiple-languages-in-mixed-language-texts
No se incorpora a dependencias/runtime/producto y no se ajustan umbrales ni palabras
para aprobar estos ejemplos. El detector de idioma de ENTRADA se conserva.
