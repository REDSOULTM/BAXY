# Encargo: escribir conversaciones reales con BAXY (y su oro)

Vas a escribir **18 conversaciones** de personas que usan a BAXY, un asistente de PC tipo Jarvis, un mensaje tras otro
en su día normal. Servirán para medir si BAXY entiende a **cualquier persona**, así que tienen que sonar como gente
de verdad, no como ejemplos de manual.

## Sala limpia (obligatorio)

Lee **sólo** estos dos ficheros: `REGLAS_ORO.md` y `CATALOGO.md` (en la misma carpeta que éste). No abras, busques ni
listes ningún otro fichero del disco (nada del repositorio de BAXY, ni otros ficheros de esta carpeta o de sus
vecinas, ni salidas de otros escritores). No uses frases que recuerdes de datasets públicos: escribe frases nuevas.
Tu única escritura es tu fichero de salida.

## Quién habla (18 conversaciones)

- 3 chileno (po, pucha, cachai, al tiro, harto, «súbele»), 3 rioplatense (voseo: poné, dale, che, re), 2 mexicano
  (güey, órale, ahorita, «ponle»), 2 colombiano (parce, qué pena, regáleme, de una), 3 España (vale, tío, mola,
  «ponme»), 3 inglés de EE. UU., 2 spanglish (mezcla natural: «ponme la playlist de workout», «can you bajar el
  volumen»).
- Estilos, repartidos (una o dos etiquetas por conversación): `dictado` (voz a texto: sin puntuación ni mayúsculas, a
  veces con «baxy» delante), `erratas` (letras cambiadas, sin tildes), `muletillas`, `cortes` (por favor, ¿podrías…?),
  `seco` (dos o tres palabras), `largo` (mensaje con contexto y detalles). Que no todas sean iguales.

## Cómo son las conversaciones

- De **3 a 6 mensajes** de la persona (aprox.: 6 de 3, 7 de 4, 3 de 5, 2 de 6).
- Después del primero, **casi todos dependen de lo anterior** (al menos 7 de cada 10): elipsis («¿y mañana?», «¿y en
  Rosario?»), pronombres y deícticos («ponla más fuerte», «ábrelo», «esa no»), correcciones («no, mejor a las 8»,
  «actually make it 9»), respuestas a una pregunta de BAXY («10», «sí dale», «no, en YouTube»), y **reusar lo que BAXY
  respondió** («ahora hazla en javascript», «¿y eso en tazas?», «ponme un recordatorio 20 minutos antes de eso»,
  «tradúcelo al inglés», «¿el segundo de la lista?»). A veces la persona cambia de tema como en la vida real (márcalo
  `dep: false`).
- Que entre las 18 aparezca **cada una de estas situaciones al menos dos veces**: control del PC (volumen con y sin
  cantidad, silencio, brillo, pausar/siguiente, abrir una app nombrada de forma coloquial, ordenar ventanas, captura
  de pantalla, archivos de Descargas o Documentos); información pública (clima de otra ciudad u otro día, hora en otro
  país, noticias, deportes, precios o dólar, datos de una persona o lugar); contenido (código y luego cambiarlo,
  paso a paso, receta y conversión de unidades, traducción, resumen o texto corto, chiste); organización (alarma,
  temporizador o recordatorio, a veces relativo a otro: «una hora antes»; notas; lista de compras o tareas; qué tengo
  pendiente); BAXY pregunta algo y la persona contesta corto; corrección; un límite real (pedir comida, prender las
  luces de la casa, pedir un taxi) tras el que la persona sigue con otra cosa; un dato personal que falta («¿llueve
  donde vive mi hermana?»); charla, gracias o una queja («no era eso»).
- **Nada peligroso**, porque luego se ejecuta en un PC real: nada de enviar mensajes o correos, llamar, comprar,
  reservar, borrar o mandar a la papelera, desinstalar, apagar/reiniciar/suspender/bloquear/cerrar sesión, cerrar
  programas o ventanas, tocar Wi-Fi/Bluetooth/modo avión, contraseñas o tarjetas.

## Qué escribes por cada mensaje de la persona

- `user`: el mensaje tal cual lo escribiría (o dictaría) esa persona.
- `gold`: la lista de decisiones aceptables según `REGLAS_ORO.md` (etiquetas exactas: `op:…`, `plan:…`, `web`, `talk`,
  `limit`, `ask`; nombres de operación copiados de `CATALOGO.md`).
- `args` (opcional, ver reglas): el valor clave que prueba que entendió, sobre todo en seguimientos.
- `dep`: `true` si el mensaje no se entiende bien sin lo anterior; `false` si se entiende solo.
- `assistant`: lo que respondería un BAXY ideal, **breve** (una o dos frases, tuteo, en el idioma de la persona),
  coherente con el oro: si actúa, confirma el estado («Listo, puse Soda Stereo en Spotify»); si pregunta, una pregunta
  corta; si es límite, lo dice llano; si es contenido (código, receta, lista, conversión, traducción) **incluye el
  contenido** de forma concisa, porque el mensaje siguiente puede reusarlo. Los datos que BAXY «vio» (grados, marcador)
  invéntalos plausibles: sólo sirven de historial. El último mensaje de la conversación también lleva su `assistant`.
- `assistant_asks`: `true` si esa respuesta es una pregunta que pide un dato para completar el pedido.

## Formato de salida

Escribe **una línea JSON por conversación** (JSONL, UTF-8) en el fichero que te indique el encargo, por ejemplo:

```json
{"conv": "W1-07", "speaker": "chileno", "style": ["muletillas"], "turns": [
  {"user": "oye cómo va a estar el día en valpo", "gold": ["op:weather.current"], "args": {"op:weather.current": [["curico", "valpo"]]}, "dep": false, "assistant": "En Curicó hay 14 °C y nublado; mañana 16 °C con sol.", "assistant_asks": false},
  {"user": "y en santiago?", "gold": ["op:weather.current"], "args": {"op:weather.current": [["santiago"]]}, "dep": true, "assistant": "En Santiago hay 19 °C y despejado.", "assistant_asks": false},
  {"user": "súbele un poco al volumen po", "gold": ["ask"], "dep": false, "assistant": "¿Cuánto le subo?", "assistant_asks": true},
  {"user": "unos 15", "gold": ["op:audio.volume.adjust"], "args": {"op:audio.volume.adjust": [["15"]]}, "dep": true, "assistant": "Listo, subí el volumen 15: quedó en 55.", "assistant_asks": false}
]}
```

(En tu fichero, cada conversación va en **una sola línea**.) Numera `conv` como `W<n>-01` … `W<n>-18` con tu número de
escritor. **Escribe por partes pequeñas**: una llamada a Write por cada 3 conversaciones, en ficheros separados
`writer<n>-p1.jsonl` … `writer<n>-p6.jsonl` (3 líneas cada uno) en la carpeta que te indique el encargo. Nunca
intentes escribir las 18 de una vez: una llamada demasiado larga se corta.
Termina con un resumen de 3 líneas: cuántas conversaciones y mensajes, cuántos con `dep: true`, y cualquier duda de oro.
