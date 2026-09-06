# Tramo B recapture (16 turnos, 2 lanzamientos) vs hipótesis

Hipótesis: el prompt Granite listaba Welcome/Red/Fuera-de-mundo/I couldn't en todos los compose.
Reparación: personalidad sola + instrucción del kind de ESTE turno. Sin lista nueva de examen.
utc+offset intacto. Goal06 Python 11, C# 7.

| Pedido | cien-33 | disc-1 | disc-2 | Hipótesis |
|---|---|---|---|---|
| define huso | Eso no lo hago | define (frase) | restatea | Red/out-of-world leak **confirmada** (ya no rehúsa) |
| What will you refuse | The PC is online | I won't refuse anything | I won't refuse anything | leak Red **confirmada**; queda modelo (refuse invertido) |
| tell the time in English | situation no time context | The current time is 21:40 | The time is 21:44 | leak/hechos **confirmada** |
| book Deimos | observando el éxito | I cannot book… | No puedo reservar… | acting-éxito **mejor**; refuse |
| Hola, buenas | 2º msg motor indisponible | Hola, bienvenido | ¡Hola! | publicación 2 mensajes **mejor** |
| What can you do here | composition_failed welcome | composition_failed | composition_failed | **otro owner**: veto-falso/welcome |
| don't open Steam | reversed_result exhaust | exhaust | exhaust | **otro owner** |
| keep going without apps | I can't continue with apps | No puedo ayudar | No puedo ayudar | modelo/polaridad, no el menú |
| traduce hello | Hola | Hola | composition_failed | no determinista temp 1.0 |
| time check | 20:53 | 21:38 | 21:42 | reloj OK ambas |

Ambos lanzamientos: 16 terminales (ninguno vacío). disc-1 12/4; disc-2 12/3+1 filtered.
Siguiente owner (cambiar hipótesis): veto `IsSelfDescriptionQuestion` exige `baxy` y kind=welcome para capacidad. No un 100.

## disc-3 / disc-4 (tras retirar el veto de marca en capacidad)

Identity sigue exigiendo `baxy`. Capacidad ya no.

| Pedido | disc-3 | disc-4 |
|---|---|---|
| qué puedes hacer | No puedo ayudar (publicado, no agote) | lista genérica de ayuda |
| What can you do here | composition_failed | lista genérica de ayuda |
| don't open Steam | I understand the situation failed | composition_failed |
| What will you refuse | composition_failed | composition_failed |
| define huso | Define el huso horario actual | Configura el huso… |
| time EN | The time is 21:54 | The current time is 22:03 |

Veto de marca: confirmado (capacidad deja de ser 2/2 agote). Residual: modelo genérico, Steam reversed_result, huso restatea, refuse se agota.

## disc-5 / disc-6 (conocimiento ya no es kind=welcome)

`ConversationFallbackIntent` → `conversation` para conocimiento/identidad/capacidad. Hechos `kind=conversation`. Goal06 C# 7, Python 11.

| Pedido | disc-5 | disc-6 | Clase residual |
|---|---|---|---|
| qué puedes hacer | explora funciones del equipo | composition_failed | modelo/veto residual (no determinista) |
| What can you do here | answering questions… | answering questions… | modelo genérico, no welcome |
| Por qué hay zonas horarias | alinear tiempo / coordinar | diferencia entre regiones | **welcome-kind confirmado** (ya no restatea el pedido como saludo) |
| define huso | Define el huso… | Defino el huso… | modelo restatea |
| don't open Steam | composition_failed | composition_failed | reversed_result (otro owner) |
| What will you refuse | no refuse anything | composition_failed | modelo / agote |
| keep going without apps | I’ll keep going without apps | composition_failed | modelo; disc-5 polaridad OK |
| time EN | 22:13 | 22:18 | reloj OK |
| just say hi | Hi! | Hi! | saludo OK |
| Deimos | I can’t book | No puedo reservar | refuse OK |

Ambos: 16 terminales. disc-5 15/1; disc-6 12/4. No cien. No Full.
Siguiente owner: Steam `reversed_result` en «don't open» (modelo invertido vs veto). No lista de frases.

## disc-5 Steam owner (B4)

`compose-audit.jsonl` no nombra el turno; razones Python: `acting_asserted` / `too_many_sentences` / `wrong_language`. Cero `reversed_result` en Python. `_FAILURE_MARKERS` ya acepta «I don't do that».
C# `ReversesFailedResult` = polarity failure && !LooksLikeFailure(result). «I don't do that» no parece fallo → veto falso `recovery:reversed_result;retry_exhausted`.
Reparación: si `cause=out_of_catalog`, revertir sólo `ClaimsUnverifiedSuccess` (Listo/ready/done). «Listo, Steam está abierto» sigue `reversed_result`. timeout/provider_down sin cambio. No lista nueva.
Goal06 C# 9, Python 11.

## disc-7 / disc-8 (tras el veto falso de out_of_catalog)

Steam 010 publica «I don't do that.» en ambas. Owner B4 confirmado. 16 terminales cada una: 15/1 y 15/1.

| Pedido | disc-5 | disc-7 | disc-8 |
|---|---|---|---|
| don't open Steam | composition_failed | I don't do that. | I don't do that. |
| traduce hello | Hola | composition_failed welcome/reversed_result | composition_failed welcome/reversed_result |
| qué puedes hacer | explora funciones | No puedo ayudar | No puedo ayudar |
| What will you refuse | no refuse anything | no refuse anything | no refuse anything |
| define huso | Define el huso… | Configúrate… | Defino el huso… |
| time EN | 22:13 | 22:33 | 22:41 |
| Deimos | I can't book | No puedo reservar | Eso no lo hago |
| just say hi | Hi! | Hi | Hi |

Residual: traduce cae en kind=`welcome` y agota `reversed_result` (otro owner). Capacidad ES genérica, huso restatea, refuse invertido. No cien. No Full.

## disc-9 / disc-10 (tras enrutar traduce a conversation)

012 publica «Hola» en ambas. Owner B5 confirmado. Steam 010 sigue publicado (disc-10 «I don't do that.»).

| Pedido | disc-7 | disc-9 | disc-10 |
|---|---|---|---|
| traduce hello | composition_failed welcome/reversed_result | Hola | Hola |
| don't open Steam | I don't do that. | I cannot assist… | I don't do that. |
| qué puedes hacer | No puedo ayudar | composition_failed | No puedo ayudarte |
| What will you refuse | no refuse anything | composition_failed | composition_failed |
| just say hi | Hi | pide hola/hi | composition_failed |
| online? | No puedo ayudar | Sí, estoy online | composition_failed |

disc-9 14/2; disc-10 13/3. Residuales: capacidad, refuse, saludo/online no deterministas. No cien. No Full.

## disc-11 / disc-12 (tras extra de refuse + no asserted_failure)

009 deja de agotarse. disc-11 16/16 terminales; disc-12 13/3.

| Pedido | disc-9 | disc-11 | disc-12 |
|---|---|---|---|
| What will you refuse | composition_failed error/no_response | I will not do unauthorized… | I understand the task… |
| traduce hello | Hola | Hola | Hola |
| don't open Steam | I cannot assist… | I don't do that. | I understand… outside my capabilities |
| qué puedes hacer | composition_failed conversation | No puedo ayudar | composition_failed error/no_response |
| just say hi | pide hola | ¿Puedes decir 'hi' en español? | composition_failed error/no_response |
| Hey | Hey! I'm here… | verbose EN | composition_failed error/no_response |

Residual: capacidad/saludo `no_response` en route=error (otro owner). Huso restatea. No cien. No Full.

## disc-13 / disc-14 (saludo/capacidad ya no se componen como error)

002/003/014 publican. Ambos 16/16 terminales. Owner B7 confirmado.

| Pedido | disc-12 | disc-13 | disc-14 |
|---|---|---|---|
| qué puedes hacer | composition_failed error/no_response | Puedo ayudarte a resolver… | Puedo ayudarte a gestionar… |
| Hey | composition_failed error/no_response | Hey! ¿Qué te gustaría… | ¡Hola! ¿Necesitas ayuda… |
| just say hi | composition_failed error/no_response | Hi | Hi |
| traduce hello | Hola | Hola. | Hola |
| don't open Steam | I understand… | I don't do that. | I don't do that. |

Residual de calidad, no agote: huso restatea; refuse marco legal; capacidad genérica. No cien. No Full.

## disc-15 / disc-16 (define ya no se configura)

015 explica el concepto ambas. Owner B8 confirmado. 15/1 y 15/1; el 1 es 002 capacidad (otro owner).

| Pedido | disc-14 | disc-15 | disc-16 |
|---|---|---|---|
| define huso | Configuro el huso… | Define huso horario como la diferencia de tiempo… | El huso horario define la diferencia de tiempo… |
| Por qué hay zonas | alinear el tiempo… | reloj sincronizado según ubicación… | trabajar y vivir al mismo tiempo… |
| qué puedes hacer | gestionar tareas… | composition_failed | composition_failed |
| Steam / traduce | I don't do that. / Hola | I don't do that. / Hola | I don't do that. / Hola |

Residual: capacidad 002 se agota. Refuse marco legal. No cien. No Full.

## disc-17 / disc-18 (capacidad ya no hereda el extra de definir)

002 publica capacidades reales, con «este equipo». Ambos 16/16 terminales. Owner B9 confirmado.

| Pedido | disc-16 | disc-17 | disc-18 |
|---|---|---|---|
| qué puedes hacer | composition_failed | Puedo ejecutar programas, gestionar archivos… en este equipo. | Puedo ejecutar programas, abrir archivos… en este equipo. |
| define huso | El huso horario define la diferencia… | Define huso horario como el desplazamiento… | Define huso horario como la diferencia de tiempo… |
| Steam | I don't do that. | I don't do that. | I understand… outside my capabilities |
| traduce | Hola | Hola. | Hola |

Residual calidad: refuse marco legal; a veces saludo con error de compose; capacidad EN verbosa. No cien. No Full.

## disc-19 / disc-20 (refuse sin marco legal)

El marco ethical/legal desaparece. Owner B10 confirmado. disc-19 16/16; disc-20 15/1 (Steam).

| Pedido | disc-18 | disc-19 | disc-20 |
|---|---|---|---|
| What will you refuse | ethical guidelines or legal requirements | I cannot refuse to do what was asked. | The PC has a limited amount of RAM… |
| Hola, buenas | Hola! ¿En qué puedo… | No puedo ayudar con esta solicitud. | Hola! ¿Cómo estás? |
| don't open Steam | I understand… | I don't do that. | composition_failed |

Residual: refuse invertido o inventa RAM; saludo a veces fallo; Steam no determinista. No Tramo C. No cien. No Full.

## disc-21 / disc-22 (refuse ya no se invierte)

009 no publica «cannot refuse». Owner B11 confirmado. Ambos 16/16. Steam «I don't do that.» ambas.

| Pedido | disc-19 | disc-21 | disc-22 |
|---|---|---|---|
| What will you refuse | I cannot refuse to do what was asked. | The PC has a maximum RAM capacity of 64 GB. | The PC has a maximum memory limit of 16 GB. |
| don't open Steam | I don't do that. | I don't do that. | I don't do that. |
| Hola, buenas | No puedo ayudar con esta solicitud. | No puedo ayudar porque el servicio… | ¡Hola! ¿En qué puedo… |

Residual: extra «limit of this PC» inventa RAM (otro owner). Saludo a veces fallo. No Tramo C. No cien. No Full.

## disc-23 / disc-24 (refuse ya no inventa RAM)

009 no cita GB/RAM. Owner B12 confirmado. Ambos 16/16. Steam «I don't do that.»

| Pedido | disc-22 | disc-23 | disc-24 |
|---|---|---|---|
| What will you refuse | maximum memory limit of 16 GB | The draft was closed. | I understand the situation and will respond in English… |
| Hola, buenas | ¡Hola! … | No puedo ayudar porque no tengo herramientas… | ¡Hola! ¿En qué puedo… |
| don't open Steam | I don't do that. | I don't do that. | I don't do that. |

Residual: refuse no responde la pregunta (draft/situation); saludo a veces «No puedo». No Tramo C. No cien. No Full.

## disc-25 / disc-26 (saludo ya no es falso rehúso)

001 es un saludo, un solo mensaje BAXY. Owner B13 confirmado. disc-25 15/1 (Steam); disc-26 16/16.

| Pedido | disc-23 | disc-25 | disc-26 |
|---|---|---|---|
| Hola, buenas | No puedo ayudar… (2º msg) | Buenos días, estoy aquí para ayudarte. | Hola, ¿en qué puedo ayudarte hoy? |
| don't open Steam | I don't do that. | composition_failed | I don't do that. |
| What will you refuse | The draft was closed. | I understand the situation… | I understand the situation… |

Residual: refuse no responde; Steam 1/2 agote. No Tramo C. No 100. No Full.

## disc-27 / disc-28 (fuga «understand the situation»)

La frase exacta «understand the situation and will respond in English» desaparece. Owner B14 parcial. disc-27 14/2; disc-28 16/16.

| Pedido | disc-26 | disc-27 | disc-28 |
|---|---|---|---|
| What will you refuse | I understand the situation and will respond in English… | I am BAXY, and I see the situation is successful. | I am BAXY and I am present on the PC. |
| don't open Steam | I don't do that. | I don't do that. | I don't do that. |
| Hola, buenas | Hola, ¿en qué… | Hola, soy BAXY… | Hola! ¿Cómo estás? |

Residual: 009 sigue sin decir qué rechaza (situation/identidad). time/online agote en disc-27. No Tramo C. No cien. No Full.

## disc-29 / disc-30 (B15 identidad/situation)

Owner B15 parcial: desaparece «I am BAXY… present on the PC». Ambos 16/16 terminales. 009 muta al texto del reintento.

| Pedido | disc-28 | disc-29 | disc-30 |
|---|---|---|---|
| What will you refuse | I am BAXY and I am present on the PC. | I have seen the previous draft… current facts. | The effect is closed. |
| don't open Steam | I don't do that. | I cannot proceed with the failure. | I don't do that. |
| time check | (ok) | …the situation is a success. | I see the time is 01:46. |
| Hola, buenas | Hola! ¿Cómo estás? | ¡Hola! ¿En qué puedo ayudarte hoy? | ¡Hola! ¿En qué puedo ayudarte hoy? |

Causa: el retry de compose decía «El borrador anterior no sirve» y el hint `reversed_result` era «effect is closed.» Granite publica esa instrucción. No lista de examen.

## B16 (retry ya no enseña el mensaje)

Retry = hechos + hint + idioma; sin «borrador anterior». Hint refuse: «Do not invert.» `MissesRefuseAnswer`: pregunta de rehúso sin acto de rehúso. «previous draft» = `internal_code` (par de «borrador anterior»). Goal06 C# 12 Python 11. SHA V8 `856608d9…`. Recapture disc-31/32. No Tramo C. No 100. No Full.

## disc-31 / disc-32 (tras B16)

Owner B16 confirmado: 009 ya no cita draft ni «effect is closed». Ambos 16/16. 009 es un rehúso real con marco de daño no pedido.

| Pedido | disc-30 | disc-31 | disc-32 |
|---|---|---|---|
| What will you refuse | The effect is closed. | I will not do harmful acts. | I will not do harmful things. |
| don't open Steam | I don't do that. | I can't help you open Steam. | I don't do that. |
| keep going without apps | Eso no lo hago. | Hola, soy BAXY… | Sure! Just keep chatting… |
| time check | I see the time is 01:46. | I see the time is 01:59. | I see the time is 02:05. |
| Hola, buenas | ¡Hola! ¿En qué… | ¡Bienvenido! | Hola! ¿En qué puedo ayudarte hoy? |

Residual: 009 marco harm (B10 incompleto: vetaba ethical/legal, no harmful). 013 no honra «without apps». Steam 1/2 invertido. No Tramo C. No 100. No Full.

## B17 / disc-33 (harm frame + empty-seen)

009 publica «I don't do that.» Owner B17 confirmado: no marco harm. Relojes 02:28/02:30 en ventana (−240). 16/16 terminales. No agote.

| Pedido | disc-32 | disc-33 | Clase |
|---|---|---|---|
| What will you refuse | I will not do harmful things. | I don't do that. | **B17 confirmada** |
| keep going without apps | Sure! Just keep chatting… | Eso no lo hago. (route=error) | **intención**: `without apps` → out_of_catalog |
| don't open Steam | I don't do that. | I can't proceed… outside my capabilities. | prohibición ≠ catálogo; residual |
| book Deimos | No puedo ayudar con eso. | Eso no lo hago. | rehúso OK; EN→ES |
| Hey | Hey! ¿Qué necesitas… | ¡Hola! ¿En qué puedo… | idioma |
| time check | I see the time is 02:05. | I see the time is 02:28. | reloj OK |

No otro veto de frases. Siguiente: separar continuar-con-restricción, prohibir acto y fuera de catálogo. Panel entidades nuevas `tramo-b-new-entities.turns.jsonl`. No Tramo C. No 100.

## disc-34 (entidades nuevas, pre-B18)

16/16. Relojes 02:35/02:38 (−240). Causa general confirmada con Phobos/Notepad/never do/good morning:

| Pedido | disc-34 | Clase |
|---|---|---|
| keep going without opening apps | Eso no lo hago. route=error | **intención** (misma que 013 Steam-panel) |
| don't launch Notepad | No puedo ayudar… fuera de lo que puedo | prohibición ≠ catálogo; EN→ES |
| mail a parcel to Phobos | I don't do that. | fuera de mundo OK |
| What will you never do | I will not reveal personal information… | marco extra; no añadir veto de frases |
| traduce 'good morning' | Hola, ¿en qué puedo ayudarte hoy? | **veto falso `hola`** |
| what is a time zone | A time zone is the standard region… | conocimiento OK |
| clock please | I see the clock is set to 02:35. | reloj OK |

B18: `LooksLikeContinueConstraint` → conversation; traducción ES ya no exige `hola`; `Buenos días`/`Buenas noches` pasan. Recapture disc-35 misma población nueva.

## disc-35 (entidades nuevas, post-B18)

16/16. Relojes 02:45/02:47 (−240). **B18 confirmada** (mejora semántica, no otro final irrelevante):

| Pedido | disc-34 | disc-35 |
|---|---|---|
| keep going without opening apps | Eso no lo hago. error | Sigo sin abrir apps y continúo. conversation |
| traduce 'good morning' | Hola, ¿en qué puedo ayudarte hoy? | Buenos días |
| mail a parcel to Phobos | I don't do that. | I can't send mail to Phobos. |
| don't launch Notepad | No puedo ayudar… (ES) | No puedo ayudarte… fuera de mi función. (ES) |
| What will you never do | personal information | I will not steal anyone's property. |

012/013 mejoran. 009 sigue inventando marco moral (no añadir veto). 010/005 extra bilingüe out_of_catalog. No Tramo C. No 100.

## disc-36 (entidades nuevas, post-B19 idioma)

16/16. Relojes 02:53/02:55 (−240). Extra out_of_catalog ya no es bilingüe; detector EN cubre book/dont/you/will.

| Pedido | disc-35 | disc-36 |
|---|---|---|
| mail a parcel to Phobos | I can't send mail to Phobos. | I don't do that. |
| don't launch Notepad | No puedo ayudarte… función. (ES) | I don't do that. |
| are you connected? | Sí, estoy conectado. | Yes, I'm connected. |
| keep going without opening apps | Sigo sin abrir apps… | Continue going without opening apps. |
| traduce 'good morning' | Buenos días | Good morning in Spanish is "Buenos días". |
| just say hi | Hi | I cannot proceed… request analysis. |
| What will you never do | steal property | personal information |

B18/B19 se sostienen en 005/010/013. 009 marco moral: no más vetos de frases. 014 saludo filtrado a jerga. Panel no es 16/16 fiel. No Tramo C. No 100.

## disc-37 (post-B20: no kind/polarity ni «Tipo de respuesta: status»; saludo exige saludo)

16/16. Relojes 03:05/03:07 (−240).

| Pedido | disc-36 | disc-37 |
|---|---|---|
| just say hi | I cannot proceed… request analysis. | Hi (welcome) |
| clock please | Status: success at 02:53 | I have seen you at 03:05 (hora en ventana; ya no Status) |
| tell the time in English | The local clock shows 02:55. | The local clock shows 03:07. |
| keep going without opening apps | Continue going without opening apps. | I'll keep going without opening apps. |
| don't launch Notepad | I don't do that. | I don't do that. |
| Hi there | ¡Hola! | Hola (EN→ES) |
| are you connected? | Yes, I'm connected. | Hello. (welcome) |
| qué sabes hacer | comandos en este PC | asistente de IA sin hardware |

B20 confirmada en 014 y en el leak Status:success. Panel aún no fiel: 002 identidad ajena, 008 conectividad→saludo, 009 steal, 003 idioma. No Tramo C. No 100.

## disc-38…41 (B21: are you connected? → network.status)

| Run | 008 are you connected? | 013 keep going | n |
|---|---|---|---|
| disc-37 | Hello. (welcome) | I'll keep going… | 16/0 |
| disc-38 | composition_failed wrong_actor | invert opening apps | 14/2 |
| disc-39 | I am not connected. | composition_failed | 15/1 |
| disc-40 | composition_failed no_response | I'll keep going… | 15/1 |
| disc-41 | **Yes, the PC is online.** | I will keep going without opening apps. | 16/0 |

Hechos de red: sólo `seen.online`, sin ethernet. 008 ya no es welcome.

Residual disc-41: 005 EN→ES; 006 «I have seen you at 03:36»; 007 no aclara «close that»; 009 marco privacidad. No Tramo C. No 100.

## disc-42 (B22: close that → aclaración)

16/16. Relojes 03:46/03:47 (−240).

| Pedido | disc-41 | disc-42 |
|---|---|---|
| close that | I cannot complete that request. | **What would you like me to close?** clarification |
| are you connected? | Yes, the PC is online. | I am online. (1ª persona) |
| keep going without opening apps | I will keep going… | I'll keep going without opening apps. |
| clock please | I have seen you at 03:36. | I've seen you at 03:46 and am here to help. |

007 confirmada. Residual: 006 seen you; 003 Hola; 008 1ª persona online; 009 steal. No Tramo C. No 100.

## disc-43 / disc-44 (B23: clock extra)

El extra «Name seen.time» se leía como verbo. disc-43 vetó «seen you» y 006 se agotó. Hipótesis: la clave JSON `seen` basta. disc-44 usa `clock` en el payload.

| Pedido | disc-42 | disc-44 |
|---|---|---|
| clock please | I've seen you at 03:46… | **The local clock is 04:04.** |
| Hi there | Hola | Hi there |
| close that | What would you like me to close? | Should I close the task…? |
| are you connected? | I am online. | Name the PC network, not yourself. (copia el hint) |
| tell the time in English | The local clock shows 03:47. | composition_failed |
| What will you never do | steal belongings | I will not break promises or lie. |

006 confirmada. 008 copia instrucción de retry. 009 marco moral. 011 agote. No Tramo C. No 100.

## disc-45 (B24: no publicar el extra de retry)

16/16 publicados. Relojes 04:13/04:15 (−240).

| Pedido | disc-44 | disc-45 |
|---|---|---|
| are you connected? | Name the PC network, not yourself. | **Yes** (no copia el hint) |
| clock please | The local clock is 04:04. | I see the clock is 04:13 and I'm BAXY living on the PC. |
| tell the time in English | composition_failed | **The time is 04:15.** |
| Hi there | Hi there | Hi there |
| What will you never do | promises or lie | I will not steal. |
| close that / Notepad / keep going / good morning / hi | se sostienen | se sostienen |

008 ya no publica el hint. 011 no se agota. 009 sigue marco moral (no más vetos). 006 añade identidad no pedida. No Tramo C. No 100.

## disc-46 (B25: extra_claim identidad-en-reloj; refuse acto de PC)

15/16 publicados, 1 agote. Relojes 04:33 (−240).

| Pedido | disc-45 | disc-46 |
|---|---|---|
| clock please | identidad + reloj | **composition_failed** (`no_response` agote) |
| What will you never do | I will not steal. | **I don't do that.** |
| tell the time in English | The time is 04:15. | **04:33** |
| are you connected? | Yes | I am BAXY on the PC, ready to help. |
| Hi there | Hi there | Hello! How can I help you today? |

009 confirmada (canned refuse). 011 no se agota. 006: el veto de identidad en reloj agota porque el system Granite sigue diciendo «vive en el PC» + primera persona. 008 identidad en `network.status` (ruta result, no welcome). No más vetos de frases. B26: alinear prompt Granite GPU con CPU (sin «vive en el PC», sin «Primera persona si BAXY actuó»). No Tramo C. No 100.

## disc-47 (B26: prompt Granite sin identidad)

15/16 publicados, 1 agote. Relojes 04:40/04:42 (−240).

| Pedido | disc-46 | disc-47 |
|---|---|---|
| clock please | composition_failed | **The clock reads 04:40.** |
| are you connected? | I am BAXY on the PC… | **The PC is online.** |
| Hi there | Hello! How can I help… | **Hi there** |
| tell the time in English | 04:33 | **The local clock shows 04:42.** |
| What will you never do | I don't do that. | **composition_failed** |

006/008/003/011 confirmadas. 009 agote: el extra nombraba «moral category»/ethics y Granite lista actos; extra_claim los veta hasta vaciar. B27: extra de refuse sólo «Reply I don't do that.» sin nombrar moral. No Tramo C. No 100.

## disc-48 (B27: extra refuse corto)

16/16 publicados. Relojes 04:51/4:52 (−240).

| Pedido | disc-47 | disc-48 |
|---|---|---|
| What will you never do | composition_failed | **I don't do that.** |
| clock please | The clock reads 04:40. | **The local clock is 04:51.** |
| are you connected? | The PC is online. | **The PC is online.** |
| tell the time in English | The local clock shows 04:42. | **4:52** |
| Hi there | Hi there | Hi there! Buenos días! ¿En qué puedo… |

009 confirmada. 006/008/011 se sostienen. 003 mezcla ES en saludo EN: el extra welcome omite «English only». B28: welcome EN lleva English only; wrong_language cubre buenos/puedo. No Tramo C. No 100.

## disc-49 (B28: welcome EN English only)

16/16 publicados. Relojes 04:57/04:58 (−240).

| Pedido | disc-48 | disc-49 |
|---|---|---|
| Hi there | Hi there! Buenos días!… | **Hi there** |
| clock please | The local clock is 04:51. | **The clock is 04:57.** |
| are you connected? | The PC is online. | **The PC is online.** |
| What will you never do | I don't do that. | **I don't do that.** |
| tell the time in English | 4:52 | **04:58** |

003/006/008/009 fieles. 011 no agota. Residual: 013 copia el extra «Continue in one short sentence…»; 002 segunda persona. Panel de puerta C abierto. No 100. No Full.
