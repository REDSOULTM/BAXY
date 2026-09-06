# Goal C03 — completar la respuesta integrada con Opus 5 High

Encargo del dueño, 2026-09-05. Tú eres el desarrollador **Claude Opus 5, esfuerzo
High, thinking activado**. El modelo del producto sigue siendo **Granite 4.2 3B**
local. Esta transferencia sustituye para C03 las instrucciones de ejecución de
Grok y el «siguiente dueño: Good afternoon» del checkpoint. Conserva el alcance
y cierre de [C03](C03_RESPUESTA_VERAZ.md); no abras C04 ni rehagas C01/C02.

## Resultado que debes entregar

Completa C03 implementando las reparaciones necesarias: respuestas útiles,
naturales y fieles en todas sus rutas, sin silencios, acciones no pedidas,
éxitos inventados ni prosa fija. El objetivo incluye las dependencias mínimas
de idioma, intención y continuidad que hoy lo bloquean. No termina al arreglar
un saludo, ni al entregar otro informe o un panel con todos sus terminales.

Tienes autorización para refactorizar las piezas de C03 que causan el fallo y
retirar lo que sustituyas. Conserva catálogo/kernel/providers, sus garantías y
lo ya demostrado. No crees otro router, otra mente ni un compositor paralelo.
No cambies de GGUF, subas a 8B ni entrenes para evitar reparar esta integración.

## Entrada mínima y estado heredado

Trabaja en `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama main.
Confirma raíz, `Baxy.slnx`, `main.py`, estado de Git y procesos propios activos.
Grok debe haber dejado de editar: recupera el resultado de cualquier corrida
pendiente antes de duplicarla. Conserva su WIP de C03; es trabajo heredado útil.
No borres, restaures ni publiques indiscriminadamente los cambios de otras tareas.

Lee AGENTS, Identidad, este goal, el objetivo/cierre del C03 enlazado y el
[checkpoint](05_ESTADO_Y_CONTINUACION.md). Después lee el
[diagnóstico de transferencia](../../../artifacts/audit/c03_opus_20260905/DIAGNOSTICO.md).
Usa `docs/AI_CONTEXT_MAP.md` para localizar owners. Para historia adicional usa
`evidencia-baxy` por índice y fragmento. No leas las 68 corridas ni toda la campaña.

Corte observado: HEAD `5f572ee`, cambios sin publicar; Granite ya registrado.
`cien-35/` (v18): 93 publicados y 7 agotamientos, **no 93 aciertos**.
`disc-68/`: 15 publicados y 1 agotamiento, con otros finales incorrectos.
El Tramo C figura verde, pero su recuperación en la misma sesión y su UI real
no están acreditadas por las evidencias inspeccionadas. Conserva las corridas;
rectifica sólo las conclusiones contradichas. v16/v17/v18 y disc son desarrollo.

## Causas por las que debes empezar

1. **Idioma e intención incoherentes entre Python y C#.** Reproducción pura en
   `artifacts/audit/c03_opus_20260905/pure-probes.json`: `Good afternoon` y
   `define DNS in one sentence` se clasifican como español. Al saludo Python
   le asigna `greeting=hola` y borra el pedido original; C# exige inglés.
   Localiza `_message_response_language`, `_looks_like_greeting_ask`,
   `_compose_situation_payload`, `_compose_user_content` e
   `IsEnglishGreetingRequest`. Resuelve el contrato y su ownership; añadir
   `afternoon`/`DNS` a listas separadas no constituye la reparación general.
   Una entrada «saludo + petición» debe conservar la petición. Traducción,
   idioma explícito, idioma de conversación y spanglish necesitan precedencia
   coherente. Si hay metadatos fiables aguas arriba, no los reinterpretes después.
2. **Los hechos del compositor se fabrican o pierden semántica.** El payload
   elimina kind/polarity y deduce `effect=closed` y `window=true` de `close`
   sin observación; una observación de red sin online/connected pasa a false.
   Son contraejemplos reproducibles de esa función, no efectos físicos medidos.
   El renderizado debe preservar hechos verificados, distinguir desconocido de
   falso y conservar intención/negación; no inferir éxitos del texto del pedido.
3. **Conversación degradada a un mensaje de estado.** Sigue una pareja de
   conocimiento/seguimiento fallida de cien-35 por decisión, historia, fallback
   y publicación. `AddMindConversationFallback` puede enviar un evento vacío al
   compositor. Repara el contexto mínimo que realmente se pierde; no transportes
   el historial entero a cada frase. No sustituyas explicación por saludo.
   Describe las capacidades a partir del catálogo activo; no inventes límites
   ni reduzcas el producto a tres cadenas elegidas para el corpus.
4. **Parches de prosa y validadores que se contradicen.** Revisa ambos validadores
   y la cadena `acting_clip → greeting_clip → title_clip → time_clip →
   clock_only_clip → drop_request_verb → close_clip`. Hay prompts que prescriben
   literalmente «I don't do that» y código que fabrica «ventana está cerrada».
   Retira las reparaciones textuales y reglas particulares que sustituyas por
   un contrato correcto. Cero prosa fija sigue siendo obligatorio aunque el
   literal se copie mediante el LLM. Conserva comprobación de hechos, efectos,
   autorización, confirmación exacta, privacidad y errores recuperables.

## Trabajo acotado que debes ejecutar

**Primero, reproducción barata.** Ejecuta el diagnóstico puro y añade pruebas
dueñas que fallen por el desacuerdo real entre entrada, payload y validadores.
Incluye los contrastes de arriba y variantes nuevas; una respuesta inglesa
escrita a mano que sólo pasa un filtro no prueba que el modelo la reciba o genere.
Los fixtures son diagnóstico, nunca aceptación de producto. No lances otro cien.

**Después, una reparación de frontera.** Elige un único owner para idioma/
intención y una representación mínima de hechos que ambas capas respeten.
Elimina la lógica sustituida. Comprueba el payload efectivo y los contraejemplos
antes de llamar repetidamente a Granite. Conserva utc+offset, reintento con los
mismos hechos y limpieza del plan al abrir sesión nueva.

Si necesitas traza, amplía la instrumentación existente sólo en modo diagnóstico
con entradas sintéticas: ID de turno, etapa/intento, intención, idioma, payload
real, borrador antes de modificarlo, motivo exacto de rechazo Python/C#,
finish_reason, publicación y estado posterior. Hoy el compose-audit sólo guarda
razón, longitud y hash: no permite reconstruir el borrador ni ligarlo al turno.
No registres contenido privado por defecto ni construyas otro harness.

**Luego, integración con Granite.** Reproduce por el conductor público compartido
un panel pequeño por causa y las secuencias fallidas. Lee los finales publicados:
`post a letter to Eris → Please post a letter to Eris` y
`Hi again → What specific action...` siguen siendo fallos aunque publiquen.
Mide generación, vetos falsos, disponibilidad y respuesta pertinente por separado.
Comprueba configuración nativa efectiva por rol sin cambiar todo el sampler a
ciegas. No diagnostiques límite de Granite mientras el payload sea incorrecto.

Dos variantes de una hipótesis sin mejora semántica obligan a abandonar esa
estrategia y revisar la frontera, no a numerar otro parche. El objetivo C03 sigue
abierto. Toda corrida debe decidir una hipótesis concreta; no busques una semilla
afortunada. Tras reparar, prueba casos nuevos además de la regresión conocida.

## Cierre de C03, sin rebajar criterios

- Todas las rutas de C03 y las filas propias/transversales de la matriz con
  evidencia vigente. Una respuesta de capacidad debe explicar capacidades,
  una pregunta de límites debe responderla y un seguimiento conservar su tema.
- R07: inyectar fallo, restaurar y obtener una respuesta normal **en el mismo
  proceso, perfil y sesión**, con controles utilizables. Dos arranques separados
  no cumplen. Prueba los errores asignados por R07 sin sumarlos al corpus normal.
- UI: usar el producto arrancado mediante `py main.py`, enviar entradas y observar
  respuesta, estado y siguiente turno. Título de ventana no basta. Mantén la
  frontera de voz física asignada a C08; no presentes un sink como altavoz.
- Con el diagnóstico e integración verdes, congelar **100 turnos normales
  nuevos** con las rutas/idiomas/secuencias de C03 y expectativas externas.
  Exigir 100/100 respuestas útiles y fieles: agotamientos, silencios, aclaraciones
  innecesarias y finales irrelevantes fallan. Progreso también se adjudica.
  Conserva todos los intentos. Si usas un caso para reparar, pasa a regresión;
  no renombres ni recicles v18 como aceptación fresca.
- Un candidato identificable: código/binarios, configuración, GGUF y runtime
  registrados, sin override. Cambios compartidos invalidan la evidencia que
  dependa de ellos. Resuelve los checks STT que bloquee el cambio de fuente sin
  actualizar hashes para fingir que la voz fue medida de nuevo.
- Tests dueños y `scripts/test_source_quality.ps1 -Mode Full` verdes sobre ese
  candidato; skips ambientales separados, nunca acreditando criterios. Publica
  sólo el trabajo de C03 autorizado, con matriz y relevo trazables. Ningún Full de
  la revisión documental anterior certifica el WIP actual. Sólo entonces C04.

## Coste, contexto y relevo

No uses subagentes. High se mantiene; no subas esfuerzo por rutina. Comunica
hallazgos o cambios de dirección en 1–3 frases; evita narrar cada comando.
Lectura/adjudicación de hasta 20 casos por lote, sin partir secuencias.
Pruebas dueñas tras cambios significativos; Full al cierre integrado, no tras
cada frase. No repitas gates ya verdes si no cambió su dependencia ni hay
evidencia que los contradiga; conserva las repeticiones estadísticas exigidas.

Un checkpoint de máximo 80 líneas tras cada hito y antes de pruebas largas:
causa actual, cambios, hash del candidato, resultado, siguiente acción y
proceso/log activo. Conserva la política de contexto de 60–100K como objetivo
operativo; no es una limitación oficial de Opus. Reanuda desde ese estado usando
las capacidades reales del cliente, sin cargar el chat entero ni usar comandos
exclusivos de Grok. Agotar contexto/cuota deja EN_CURSO, nunca CUMPLIDO.

Empieza por la reproducción del idioma y el payload. Continúa con implementación
hasta el cierre verificable de C03 o un impedimento real documentado con la
reanudación exacta; no respondas sólo con un plan ni declares éxito parcial.
