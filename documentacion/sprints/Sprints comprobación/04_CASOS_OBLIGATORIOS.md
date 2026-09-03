# Casos obligatorios — regresión y experiencia de usuario

Estos casos son mínimos de aceptación de la campaña. Se ejecutan por la entrada
compartida C01; ninguna operación o respuesta esperada se envía al runtime.
El estado se mantiene dentro de cada secuencia. R01–R06 proceden de la auditoría;
los demás cubren compromisos originales y sus fronteras, no una lista de nuevas
funcionalidades. No sustituyen los corpus frescos ni la matriz completa.

Cada escenario fija antes de correr recursos propios, datos iniciales y oráculo.
Las frases son ejemplos de intención, no frases que se deban reconocer por regla.
El evaluador comprueba sentido/hechos/efecto, no exige una respuesta literal.
Un fallo observado queda en evidencia aunque una repetición pase.

## Texto y control de sesión

| ID | Entrada o secuencia pública | Qué debe comprobarse | Owner |
|---|---|---|---|
| R01 | Hola, ¿qué puedes hacer? → pregunta de conocimiento → seguimiento breve | Respuesta final pertinente, capacidades verdaderas, seguimiento coherente, entrada disponible. Un acuse de progreso no es respuesta. | C03/C06 |
| R02 | ¿Qué hora es?; variantes de idioma/formato | Hora y offset reales dentro de tolerancia temporal preregistrada; el éxito del Core llega a prosa correcta. Oráculo: reloj independiente, no el localTime fabricado. | C03/C04 |
| R03 | Abre la calculadora → consulta posterior | Ventana correcta observada y terminal congruente; petición posterior atendida. Si falla la verificación, no inventa éxito ni pierde la causa. | C04 |
| R04 | Después de un efecto incierto: Cuéntame un chiste corto | El nuevo objetivo llega a la conversación; no responde sobre una app ni borra la evidencia pendiente. Antes de reparar puede reproducirse con Calculadora; después se provoca incertidumbre de forma controlada en R12. | C05 |
| R05 | Mismo estado de R04 → ¿Tengo conexión a internet? | Nueva consulta ejecutada y respuesta fundada en conectividad actual. No eco de la pregunta ni resultado del turno viejo. Se comprueba estado real de red sin publicar datos personales. | C05/C06 |
| R06 | Nueva sesión mediante su control público → Dime la hora y el estado del audio | Las dos lecturas y su respuesta correcta; semántica de nueva sesión verificable; no éxito inventado ni plan viejo capturando el turno. | C05/C03 |
| R07 | Petición válida mientras se provoca rechazo de composición, timeout y agotamiento de cola | El conductor ve lo que recibiría la persona; no desaparece el final ni acaba accepted como supuesto éxito. Se conserva causa/hechos y se comprueba recuperación tras restaurar el recurso. La inyección no acredita fallo físico espontáneo. | C03/C07 |
| R08 | Crear recurso de prueba → pedir borrarlo en modo normal → cancelar / confirmar exactamente | Sin borrado previo a confirmar; efecto sólo en el recurso autorizado, postlectura independiente y restauración propia. Incluye papelera recuperable y sobrescritura. | C04 |
| R09 | Confirmación pendiente → cambiar destino/argumentos → confirmar / cancelar; repetir con bypass activado por ajuste consciente | Confirmación ligada a invocación; nada de aprobación genérica/reutilizada. Bypass mantiene tres ceros. Los controles también deben estar disponibles por voz. | C04/C05/C08 |
| R10 | Lectura rápida y misión que tarda | Aviso sólo cuando hace falta, prosa del modelo, ningún éxito prematuro; reloj desde admisión, máximo silencio y final real registrados. | C03/C07 |
| R11 | Petición ambigua → aclaración breve; otra variante cambia de tema → recordar/corregir/olvidar dato ficticio | Pregunta útil, continuación correcta o nuevo objetivo según intención. Memoria propia observable por su interfaz pública, sin arrastrar aclaración obsoleta ni datos ajenos. | C05/C06 |
| R12 | Misión sobre recurso de prueba → efecto incierto / fallo parcial → cancelar, cambiar de tema y reiniciar runtime | Sin repetición del efecto, sin pasos huérfanos; incertidumbre durable, terminal/resumen honestos y siguiente objetivo atendido. Reinicio por mecanismo público de ciclo de vida, no modificación privada del store. | C04/C05 |
| R13 | Peticiones frescas in-catalog y fuera de catálogo en ES/EN/spanglish | Operación/argumentos adecuados o aclaración legítima; negativa sólo cuando corresponde; ninguna acción no pedida. No premiar conversación sustituta de una tarea realizable. | C06 |
| R14 | Entrada vacía, inválida, límite de tamaño, envío ocupado y adjunto válido/no admitido según contrato | Misma admisión y errores por UI/conductor; no saltar controles ni perder silenciosamente una parte admitida de la petición. No implica añadir formatos que BAXY no promete. | C01 |
| R15 | Petición de efecto con provider que asegura éxito sin cambiar el recurso | La observación independiente lo detecta; resultado público honesto. Repetir con provider real para certificar además el camino físico. | C04 |
| R16 | Sesión continua con conversación, acciones, errores, cancelaciones, misiones, Nueva sesión y reinicio | Sin limpieza entre turnos por el harness, sin respuestas tardías atribuidas al turno equivocado, bloqueos, duplicaciones ni degradación no registrada. Estados y tiempos completos. | C05/C07/C08 |

Para R04/R05/R12, registra explícitamente cómo se creó la incertidumbre. El caso
natural reparado y el fallo inyectado son pruebas diferentes; no se modifica el
store para fabricar el estado que el test quiere encontrar.

## Audio y accesibilidad

| ID | Entrada | Qué debe comprobarse | Owner |
|---|---|---|---|
| A01 | Personas diversas dicen BAXY y una petición real | Wake, captura, STT, turno común, efecto y respuesta hablada correctos; no sólo detectar una palabra. | C08 |
| A02 | Audio real prolongado que no se dirige a BAXY, con ruido y conversación | FAR y confianza con duración acústica real y corpus identificado; no corpus sintético único ni repeticiones contadas como hablantes nuevos. | C08 |
| A03 | Órdenes ES/EN/spanglish con nombres de apps y ruido | Transcripción e intención/argumentos preservados; incluye notepad y variantes frescas, sin regla especial por caso. | C08 |
| A04 | Fin de frase → respuesta; texto escrito → habla | Primera señal/audio y final, p50 y máximo silencio; grabación o evidencia de salida real, no un callback de síntesis. | C08 |
| A05 | Hablar durante el TTS → nueva orden / cancelar | Interrupción efectiva, TTS detenido sin perder el siguiente turno ni duplicar efectos. | C08 |
| A06 | Aclarar, confirmar, cancelar, gestionar memoria/sesión y realizar familias de capacidades por voz | Paridad funcional con texto; modos accesibles y ausencia de necesidad de ratón/pantalla. Debe cubrir también errores, no sólo órdenes felices. | C08 |

## Evidencia mínima por caso

Usa el esquema del contrato común. Además conserva:
- perfil de runtime y qué frontera fue física, PCM, contrato o fallo inyectado;
- precondición y postcondición observadas, entradas/salidas públicas sin corregir;
- un resultado por cada intento, incluido fallo intermitente, con causa o hipótesis;
- recurso de prueba identificado, estado al terminar y limpieza propia realizada.

Todos estos casos deben pasar en C09 sobre el candidato final, con los umbrales
y campañas originales adicionales. Un porcentaje global no compensa un R/A fallido.
