# Ministral622: clasificación insuficiente y formato incompatible

Ministral3-3B-Instruct2512 Q4 heredado, hash verificado9ed150d4; backendb10809, perfilT0,05/p0,95/k0/min0/repetición neutra. La ficha oficial recomiendaT<0,1; no se presenta el resto del perfil como óptimo. Se consultaron la ficha GGUF y el informe técnico2601.08584, además de los rechazos previos de coste y aritmética. Los52 casos previstos no se completaron:40 respuestas de clasificación, luegoHTTP500 en la primera prosa y11sin intentar.

Guardia original14/20 y subtipo11/20 normalizados. Se conservan errores de completitud, cardinalidad y lecturas actuales; el subtipo no se adopta. El HTTP500 se debe a la plantilla Jinja: el historial como datos ocupa un mensaje user y la petición otro user consecutivo. Es un error de serialización anterior al decode, no una respuesta incorrecta del modelo.

623 conserva todos los textos y roles al unir sólo user consecutivos; no borra historial ni inventa una respuesta intermedia. Esta avería y las40 clasificaciones quedan separadas. Ningún cambio de fuente/registro/cobertura:25/717/0.
