"""Lectura única del pedido: idioma, saludo y petición real.

Antes de esta pieza el idioma visible se decidía dos veces en Python
(`llm._message_response_language`, `__main__._explicit_response_language`) y
otra vez en C# (`UserMessagePolicy.IsEnglishGreetingRequest`), con tres
lexicones distintos. «Good afternoon» salía español en Python e inglés en C#:
el compositor recibía `greeting=hola` y su siguiente validador lo vetaba.

Aquí vive el contrato: una lectura por turno, con precedencia explícita
(traducción → idioma pedido → evidencia del texto → idioma de la conversación
→ español por defecto) y una separación de saludo y petición que nunca borra
lo que la persona pidió. `RequestReading.to_payload()` es la representación que
cruza la frontera hacia el shell; nadie la reinterpreta después.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .semantic.normalize import fold

LANGUAGES = ("es", "en", "mixed")

GREETING_NONE = "none"
GREETING_ONLY = "only"
GREETING_LEADING = "leading"

INTENT_KNOWLEDGE = "knowledge"
INTENT_CAPABILITY = "capability"
INTENT_IDENTITY = "identity"
INTENT_REFUSE = "refuse"
INTENT_TRANSLATION = "translation"
INTENT_AMBIGUOUS_ACTION = "ambiguous_action"
INTENT_CONTINUE_CONSTRAINT = "continue_constraint"
INTENT_NEGATIVE_CONSTRAINT = "negative_constraint"

_SPANISH_ORTHOGRAPHY = re.compile(r"[ñáéíóúü¿¡]", re.IGNORECASE)
_ENGLISH_CONTRACTION = re.compile(
    r"\b(?:can|could|would|should|do|does|did|is|are|was|were|will|ai|"
    r"have|has|had|must|might|i|you|we|they|he|she|it|that|there|what|"
    r"who|let|don|won)['’](?:t|s|m|re|ll|ve|d)\b",
    re.IGNORECASE,
)

# Palabras funcionales y verbos frecuentes. No se listan nombres propios ni
# términos compartidos por los dos idiomas: un token ambiguo no es evidencia.
_ES_WORDS = frozenset(
    """
    abras abre abrir abierta abierto actual ademas al algo alguna alguno alli ambos ante
    antes aquello aqui asi aunque ayer borra buenas buenos busca cada
    cancelar cerrada cerrado cierra cierre como con confirmar continuar contra crea cual cuales cuando cuanto cuenta
    cuentame de dejar del desde dias dice dices dime donde dos durante el
    en aprieta apreta apretar apriete pulsa pulsar presiona presionar clic
    ella ellas ellos encontrar encuentra entendi entiendo entonces era explica explicame
    eres esa ese eso escrita escrito esta estan este esto estoy fue gracias guardada guardado hace hacer
    haces hacia han hasta haz hola hora horas hoy igual incluso la las
    lee lista listo lo los luego manana mas mi mientras mis misma mismo
    modo mostrar mucha mucho muestra muy nada navega ninguna ninguno
    noches nos nota notas nuestra nuestro nunca ocupas otra otro para pero
    poco podia pon por porque procesos pude puede pueden puedes que quien
    quiere quieres quita reactiva reproduce sabes se segun ser si sido
    siempre siendo sigue silencia sobre sois somos son soy su sube sus
    tambien tanto tardes tarea tareas terminada terminado tiene tienen tienes toda todas todo
    todos trabajo tras tus un una unas uno unos usted ustedes vamos varias
    varios vez volumen vosotros voy y
    brillo pantalla cancion canciones musica alarma alarmas recordatorio recordatorios
    carpeta carpetas archivo archivos clima noticias ventana ventanas bateria temporizador
    calculadora escritorio descargas pantallazo baja bajale subele bajito sonido
    chiste chistes broma bromas cuento cuentos receta recetas adivinanza adivinanzas
    poema poemas curiosidad curiosidades pelicula peliculas historia historias
    consejo consejos
    """.split()
)
# Tanda 1 2026-09-23 «Brillo 20%» was answered in English after an English turn:
# the everyday Spanish nouns of this PC are evidence too. Tanda 2, a bare Spanish
# noun asking for jokes after an English turn: so are the nouns a bare request for
# content is made of.

_EN_WORDS = frozenset(
    """
    about above across after again against all along already also although
    always am among an and another any anything are around as ask asked at
    be because been before being below beside between both build but buy
    by bye call can cancel cannot close computer confirm continue could couple create currently
    delete details did does doing done down during each either else email
    enough even ever every everything explain few find first for from get give
    going good goodbye got great hard have having hear hello her here hers
    hey hi him his how however i if in into is isn it its just keep kind
    know later launch let letter like line list listen little look lose
    made make many maybe mine more most much music must my navigate near
    need never new next nothing now of off often on once one only open
    opened or order other our out over own pause phone play please process
    processes read really right said say search see select send sentence
    set should show since so some something soon sound speak speakers
    still stop such take talk tell temperature than thank thanks that the
    their them then there these they thing think this those though three
    through time to today together tomorrow too turn two under understand
    unmute until up upon us used very want was way we well were what
    whatever when where whether which while who why will window with
    within without would write wrote yes yesterday yet you your yours
    summarize summarise summary minimize maximize
    joke jokes story stories recipe recipes riddle riddles poem poems
    """.split()
)

_ES_PHRASES = (
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "que tal",
    "muchas gracias",
    "mil gracias",
    "por favor",
    "hasta luego",
    "nos vemos",
    "como estas",
    "me llamo",
    "te llamas",
    "se llama",
)

_EN_PHRASES = (
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "hi there",
    "how are you",
    "see you",
    "thank you",
    "thanks a lot",
    "no problem",
)

_GREETING_HEAD = re.compile(
    r"^(?:buenos dias|buenas tardes|buenas noches|buenas|buenos|hola|"
    r"good morning|good afternoon|good evening|good night|"
    r"hi there|hello|hey|hi)"
    r"(?![a-z])",
)

# «Un saludo corto» pide un saludo: es la petición entera, no un encabezado.
_GREETING_REQUESTS = frozenset(
    {
        "just say hi",
        "say hi",
        "say hello",
        "solo un hola",
        "un saludo",
        "un saludo corto",
        "solo un saludo",
        "saludo corto",
        "saludame",
    }
)

# Vocativos y muletillas que acompañan a un saludo sin añadir petición.
_GREETING_FILLERS = (
    "a todos",
    "again",
    "amigo",
    "baxy",
    "compa",
    "de nuevo",
    "otra vez",
    "there",
    "tio",
)

_TRANSLATION_TOKENS = ("traduce", "traduceme", "traducir", "translate ")
_TO_SPANISH = ("al espanol", "to spanish", "en espanol", "in spanish")
_TO_ENGLISH = ("al ingles", "to english", "en ingles", "in english")

_KNOWLEDGE_TOKENS = (
    "que es ", "que es un", "explicame", "explica ", "explain ", "define ",
    "definicion de", "what is ", "what are ", "why ", "por que ",
    "te ocupas", "what do you do", "what can you do", "que puedes hacer",
    "que sabes hacer", "able to do", "echar una mano", "what will you",
    "what do you refuse", "que rechazas", "never do", "cannot do", "no haces",
    "who are you", "quien eres", "who is speaking", "quien habla",
    "introduce yourself", "presentate", "describe yourself", "describete",
    "traduce", "translate ",
    # IDENTITY1323 H0373 «cómo funciona esto»: how this works asks what the
    # assistant does, not a definition of a mechanism.
    "como funciona esto", "como funcionas", "como funciona baxy",
    "como funciona este asistente", "how does this work", "how do you work",
)

# «Qué puedes hacer» pide capacidades; «qué no haces» pide el límite. Estaban
# en el mismo cajón, así que una pregunta por los límites recibía la lista de
# capacidades y el modelo la negaba entera (panel-opus-2/017 y /030).
_CAPABILITY_TOKENS = (
    "te ocupas", "what do you do", "what can you do", "que puedes hacer",
    "que sabes hacer", "able to do", "echar una mano", "what are you able",
    "como funciona esto", "como funcionas", "como funciona baxy",
    "como funciona este asistente", "how does this work", "how do you work",
)

_IDENTITY_TOKENS = (
    "who are you", "quien eres", "quien sos", "who is speaking", "quien habla",
    "quien esta hablando", "introduce yourself", "presentate",
    "describe yourself", "describete",
)
# IDENTITY1323 H0012 «to quien chuta eres.»: one or two words between «quién»
# and «eres/sos» (an expletive, «te crees que») do not change the question.
_IDENTITY_EXPLETIVE = re.compile(
    r"\bquien\s+(?:\w+\s+){1,2}(?:eres|sos|eri|es\s+usted)\b|"
    r"\bwho\s+(?:the\s+\w+\s+|on\s+earth\s+)are\s+you\b"
)

# --- Questions about BAXY himself -----------------------------------------------------------------
#
# Uso real 2026-09-23 and tandas 2 and 3: «the creator of your ai, what is their name», «¿cuál es tu
# lugar de origen?», «¿cuándo te crearon?», «¿existes en el mundo real?» and, after two widenings of a
# list of phrases, «who made you» said in the perfect tense still went to a web search. The list grew one wording at a time.
#
# A question about the one answering is read by its form. It is a question (a question mark, an
# interrogative, a yes/no order of words, or «dime/cuéntame/tell me») whose subject or object is BAXY
# —a second-person verb, the clitic «te», «ti», «tu/tus», «you/your/yourself», or BAXY or «this AI» named
# as an argument— and whose predicate is one of his own traits: who made him and how, where he comes
# from or lives, his age, what he is, his body, his feelings, his likes, his name, his purpose. What he
# can do is a capability and is read by ``_DOING`` below, not here.
#
# Two uses of the second person are not about him. «te» as the one an action is for («te pido que…»,
# «¿te puedo preguntar…?») carries no trait of his, so it never meets a trait predicate. A second person
# inside a relayed message («dile a Juan que tú…», «escríbele: ¿cuántos años tienes?») addresses someone
# else. «no te creo» is not a question and «creo» is also «I believe»; «hacer» is causative before an
# infinitive or an object («¿cómo te hizo sentir?», «¿quién te hizo daño?»), and so is «make you» before
# what it makes him («how can I make you louder»).

# A question: its marks, an English interrogative anywhere, a Spanish one first or after a comma (inside
# a sentence «que» and «como» are also a conjunction and a verb), a yes/no order of words, or an order to
# tell.
_ASKING = re.compile(
    r"[?¿]|\b(?:what|who|whom|whose|which|where|when|why|how)\b|"
    r",\s*(?:que|quien|quienes|cual|cuales|como|cuando|donde|cuanto|cuantos|cuantas)\b|"
    r"^(?:(?:y|e|and|pero|but|oye|hey|baxy|entonces|so|ok|bueno|a\s+ver|por\s+cierto|by\s+the\s+way|"
    r"por\s+curiosidad|just\s+curious)\s*,?\s+)*"
    r"(?:que|quien|quienes|cual|cuales|como|cuando|donde|cuanto|cuanta|cuantos|cuantas|por\s*que|para\s+que|"
    r"de\s+donde|en\s+que|de\s+que|a\s+quien|de\s+quien|desde\s+cuando|hace\s+cuanto|"
    r"are|is|do|does|did|were|was|have|has|can|could|will|"
    r"eres|sos|tienes|tenes|estas|existes|vives|naciste|sientes|te|"
    r"dime|decime|digame|cuentame|contame|hablame|explicame|describe|describete|presentate|"
    r"tell|explain|talk|puedes|podes|podrias|me\s+puedes|me\s+podes|me\s+podrias|quiero\s+saber|"
    r"quisiera\s+saber|me\s+gustaria\s+saber|sabes|i\s+want\s+to\s+know|i\s+would\s+like\s+to\s+know|"
    r"i['’]?d\s+like\s+to\s+know)\b"
)
# A message for someone else: what it says in the second person is said to them.
_RELAYED = re.compile(
    r"\b(?:dile|diles|decile|decirle|digale|cuentale|contale|preguntale|preguntales|pregunta\s+a|"
    r"(?<!se\s)escribe|escribele|escribeles|escribi|escribile|manda|mandale|mandales|envia|enviale|envie|"
    r"respondele|contestale|mensaje|message|text|write|send|reply|"
    r"(?:tell|ask)\s+(?!(?:me|us|you|who|what|where|when|why|how|which|if|whether|a|about)\b)\w+)\b"
)

# The traits, as nouns. «de/of» after one gives it another owner: «tu nombre de usuario», «your name of
# the file» are not about him.
_TRAIT_NOUN = (
    r"(?:creador(?:a|es)?|autor(?:a|es)?|desarrollador(?:a|es)?|programador(?:a|es)?|fabricante|"
    r"dueno|duena|jefe|empresa|compania|origen|lugar\s+de\s+origen|lugar\s+de\s+nacimiento|nacimiento|"
    r"cumpleanos|edad|nombre|modelo|version|creacion|proposito|mision|objetivo|funcion|razon\s+de\s+ser|"
    r"naturaleza|personalidad|cuerpo|cara|aspecto|apariencia|genero|sexo|sentimientos|emociones|gustos|"
    r"pasatiempos?|hobbies|hobby|aficiones|tiempo\s+libre|familia|padres|papa|mama|madre|padre|novia|"
    r"novio|pareja|hermanos?|amigos?|casa|hogar|historia|"
    r"creators?|makers?|authors?|developers?|programmers?|owners?|boss|company|origins?|place\s+of\s+origin|"
    r"birthplace|birthday|age|name|model|version|creation|purpose|mission|goal|function|nature|personality|"
    r"body|face|looks|appearance|gender|sex|feelings|emotions|tastes|hobbies|hobby|pastimes?|interests|"
    r"free\s+time|spare\s+time|family|parents|dad|mom|mother|father|girlfriend|boyfriend|partner|siblings|"
    r"friends?|story|backstory)"
)
_OTHER_OWNER = r"(?!\s+(?:de|del|of)\s+(?!ti\b|you\b|baxy\b))"
# What one has of his own: «¿tienes nombre?», «do you have feelings?».
_HAVE_NOUN = (
    r"(?:nombre|edad|cuerpo|cara|ojos|manos|forma\s+fisica|sentimientos|emociones|conciencia|alma|"
    r"corazon|miedo|suenos?|hambre|frio|calor|novia|novio|pareja|esposa|esposo|familia|hermanos|padres|"
    r"papa|mama|hijos|amigos|mascota|hobbies|hobby|pasatiempos?|aficiones|tiempo\s+libre|vida|genero|sexo|"
    r"cumpleanos|creador|dueno|jefe|casa|hogar|personalidad|gustos|"
    r"name|age|body|face|eyes|hands|feelings|emotions|consciousness|soul|heart|fears?|dreams|girlfriend|"
    r"boyfriend|partner|wife|husband|family|siblings|parents|kids|children|friends|pets?|hobbies|hobby|"
    r"free\s+time|life|gender|birthday|creator|owner|boss|personality)"
)
# Fear takes what is feared after «de/of» («¿tienes miedo de algo?»), not another owner.
_HELD = rf"(?:(?:miedo|fears?)\b|{_HAVE_NOUN}\b{_OTHER_OWNER})"
# What one is: «¿eres una IA?», «are you human?», «¿eres de Chile?». Praise or skill («¿eres bueno en
# matemáticas?», «¿eres capaz de…?») is not a nature: the capability reading answers it.
_NATURE = (
    r"(?:real|reales|ser\s+humano|ser\s+vivo|human\s+being|humano|humana|human|persona|person|gente|people|"
    r"robot|bot|chatbot|maquina|machine|"
    r"computadora|computer|ordenador|programa|program|software|app|aplicacion|ia|ai|inteligencia\s+artificial|"
    r"artificial\s+intelligence|asistente|assistant|modelo|model|llm|chatgpt|gpt|gemini|siri|alexa|cortana|"
    r"copilot|claude|llama|qwen|mistral|deepseek|google|openai|microsoft|hombre|mujer|man|woman|chico|chica|"
    r"boy|girl|nino|nina|masculino|femenino|male|female|consciente|conciente|conscious|sentient|vivo|viva|"
    r"alive|nuevo|nueva|new|viejo|vieja|old|joven|young|inteligente|intelligent|smart|alien|extraterrestre|"
    r"de\s+verdad|de\s+carne\s+y\s+hueso|(?:de|from)\s+\w+)"
)
_FEELING = (
    r"(?:feliz|triste|cansad[oa]|aburrid[oa]|enojad[oa]|enfadad[oa]|sol[oa]|content[oa]|enamorad[oa]|"
    r"asustad[oa]|nervios[oa]|celos[oa]|molest[oa]|estresad[oa]|de\s+(?:buen|mal)\s+humor|"
    r"happy|sad|tired|bored|lonely|angry|mad|afraid|scared|jealous|in\s+love|stressed|single|married)"
)
# Made, in the forms a question uses: preterite, participle after «ha/han», and the passive.
_MADE = (
    r"(?:crearon|creaste|creado|creada|hizo|hicieron|hecho|hecha|programo|programaron|programado|"
    r"diseno|disenaron|disenado|desarrollo|desarrollaron|desarrollado|construyo|construyeron|construido|"
    r"invento|inventaron|inventado|entreno|entrenaron|entrenado|fabrico|fabricaron|fabricado|"
    r"ideo|idearon|ideado|bautizo|bautizaron|trajo\s+al\s+mundo|trajeron\s+al\s+mundo|dio\s+vida|"
    r"dieron\s+vida|puso\s+(?:ese\s+|el\s+)?nombre|pusieron\s+(?:ese\s+|el\s+)?nombre)"
)
_NOT_CAUSATIVE = r"(?!\s+(?:\w+(?:ar|er|ir)\b|dano|caso|falta|gracia|una?\b|el\b|la\b|los\b|las\b|algo\b))"
_WH = (
    r"(?:quien|quienes|que\s+(?:empresa|compania|persona|equipo|gente)|cuando|donde|como|por\s*que|"
    r"para\s+que|en\s+que\s+\w+|de\s+que\s+\w+|con\s+que|who|what|which|when|where|why|how|whose)"
)
_MADE_EN = (
    r"(?:made|created|built|programmed|designed|developed|invented|trained|coded|owns|powers|runs|"
    r"launched|released|named|came\s+up\s+with)"
)
_MAKE_EN = r"(?:make|create|build|design|develop|train|creating|building|designing|developing)"
# What he does for fun or with his time asks about him, not about what he can do on the PC: «what do you
# do for fun» is not «what do you do».
_SELF_LEISURE = (
    r"\b(?:tu|tus|your)\s+(?:tiempo\s+libre|pasatiempos?|hobbies|hobby|aficiones|gustos|"
    r"free\s+time|spare\s+time|pastimes?|interests)\b|"
    r"\bwhat\s+(?:keeps\s+you\s+busy|do\s+you\s+do\s+for\s+fun|do\s+you\s+like\s+to\s+do)\b|"
    r"\bdo\s+you\s+have\s+(?:any\s+)?(?:hobbies|a\s+hobby|free\s+time)\b|"
    r"\bque\s+te\s+gusta\s+hacer\b|\bque\s+haces\s+para\s+divertirte\b|"
    r"\btienes\s+(?:algun\s+|algunos\s+)?(?:hobby|hobbies|pasatiempos?|tiempo\s+libre)\b"
)
_SELF_LEISURE_QUESTION = re.compile(_SELF_LEISURE)
_SELF_FORMS = tuple(
    re.compile(pattern)
    for pattern in (
        # His trait, owned: «tu creador», «your own name», «tu canción favorita», «la edad de BAXY».
        rf"\b(?:tu|tus|your)\s+(?:(?:propi[oa]s?|own|verdader[oa]s?|real|actual|current|true)\s+)?"
        rf"{_TRAIT_NOUN}\b{_OTHER_OWNER}",
        r"\b(?:tu|tus|your)\s+(?:\w+\s+){0,2}(?:favorit[oa]s?|favou?rites?|preferid[oa]s?|preferred)\b",
        rf"\b{_TRAIT_NOUN}\s+(?:de|of)\s+(?:(?:the|this|esta|este)\s+(?:ai|ia|assistant|asistente|bot|chatbot)|baxy)\b",
        rf"\b(?:(?:the|this)\s+(?:ai|assistant|bot)|baxy)['’]?s\s+{_TRAIT_NOUN}\b",
        r"\b(?:the\s+)?(?:creators?|makers?|developers?)\s+of\s+(?:you|your\s+(?:ai|ia))\b",
        # Who made him, when, where, how and why: «¿quién te ha programado?», «¿en qué país te hicieron?».
        rf"\b{_WH}\b.{{0,40}}?\bte\s+(?:(?:ha|han|habia|habian|hubo)\s+)?(?:creo|{_MADE})\b{_NOT_CAUSATIVE}",
        rf"\bte\s+(?:(?:ha|han|habia|habian)\s+)?(?!hizo\b|hicieron\b){_MADE}\b{_NOT_CAUSATIVE}",
        rf"\b(?:fuiste|has\s+sido|eres|estas|sos)\s+(?:{_MADE}|escrit[oa])\b",
        r"\b(?:crear|programar|disenar|desarrollar|construir|inventar|fabricar|entrenar|idear)te\b",
        rf"\b{_WH}\b.{{0,60}}?\b{_MADE_EN}\s+you\b"
        r"(?=\s*(?:$|[?.!,]|(?:in|at|for|to|and|from|originally|exactly|really|first)\b))",
        rf"\b{_WH}\b.{{0,60}}?\b{_MAKE_EN}\s+you\s*(?:[?.!]|$)",
        rf"\b(?:were|was)\s+you\s+(?:born|{_MADE_EN})\b|\bhave\s+you\s+been\s+(?:{_MADE_EN}|around|alive)\b",
        r"\b(?:a\s+quien|de\s+quien)\s+(?:perteneces|eres|sos)\b|\bperteneces\b|\bpara\s+quien\s+trabajas\b|"
        r"\bdetras\s+de\s+ti\b|\bbehind\s+you\b|\bwho\s+do\s+you\s+(?:belong\s+to|work\s+for|answer\s+to)\b",
        rf"\b(?:creo|{_MADE}|{_MADE_EN})\s+(?:a\s+)?(?:baxy|(?:esta|este|this)\s+(?:ia|ai|asistente|assistant|bot|app))\b",
        r"\b(?:que|quien|what|who)(?:\s+(?:es|is)|['’]?s)\s+baxy\s*[?.!]*$",
        # Where he comes from and lives: «¿de dónde eres?», «¿vives en mi PC?», «where are you from?».
        r"\bde\s+donde\s+(?:eres|sos|vienes|venis)\b|\b(?:naciste|vives|vivis|habitas)\b|"
        r"\bdonde\s+(?:estas|te\s+encuentras)(?:\s+(?:instalad[oa]|ubicad[oa]|alojad[oa]|ahora|ahorita|"
        r"ahora\s+mismo|exactamente|fisicamente|realmente|en\s+este\s+momento))?\s*[?.!]*$",
        r"\bwhere\s+are\s+you(?:\s+(?:from|located|based|hosted|running|installed|right\s+now|now|exactly|"
        r"physically))?\s*[?.!]*$|\b(?:are\s+you|you\s+are)\s+from\b|"
        r"\b(?:do\s+)?you\s+(?:live\b(?!\s+(?:stream|streaming|chat|captions?|translat\w*))|reside|come\s+from)|"
        r"\bwhere\s+do\s+you\s+(?:run|stay|exist)\b",
        # His age: «¿cuántos años tienes?», «how old are you», «¿desde cuándo existes?».
        r"\b(?:cuantos\s+anos|que\s+edad|how\s+old)\s+(?:tienes|tenes|eres|sos|are\s+you)\b|"
        r"\b(?:existes|existis)\b|\bdo\s+you\s+(?:really\s+|even\s+|actually\s+)?exist\b|"
        r"\bhow\s+long\s+have\s+you\s+(?:been\s+(?:around|alive|here|working)|existed)\b",
        # What he is: «¿eres una IA?», «are you human?», «¿qué tipo de IA eres?», «what are you made of».
        rf"\b(?:eres|sos|es\s+usted|are\s+you|you\s+are)\s+(?:(?:un|una|el|la|a|an|the|realmente|really|"
        rf"actually|de\s+verdad|solo|just|only)\s+){{0,2}}{_NATURE}\b",
        r"\b(?:que|quien|cual|como|de\s+que)\b(?:\s+\w+){0,4}?\s+(?:eres|sos|es\s+usted)"
        r"(?:\s+(?:tu|exactamente|realmente|en\s+realidad|de\s+verdad|fisicamente|por\s+dentro))?\s*[?.!]*$",
        r"\b(?:what|who|which)\b(?:\s+\w+){0,4}?\s+are\s+you(?:\s+(?:exactly|really|actually|anyway))?\s*[?.!]*$",
        r"\bare\s+you\s+made\s+of\b|\bwhat\s+do\s+you\s+look\s+like\b|\bcomo\s+te\s+ves\b",
        # His body and his feelings: «¿tienes cuerpo?», «¿te sientes solo?», «are you happy?».
        rf"\b(?:tienes|tenes|tiene\s+usted)\s+(?:(?:un|una|algun|alguna|algunos|algunas|mucho|mucha|muchos|"
        rf"muchas|tu|propio|propia)\s+)?{_HELD}",
        rf"\b(?:do\s+you\s+have|have\s+you\s+got|you\s+have)\s+(?:(?:a|an|any|some|your\s+own|a\s+real)\s+)?"
        rf"{_HELD}",
        rf"\b(?:estas|are\s+you)\s+(?:muy\s+|un\s+poco\s+|really\s+|ever\s+)?{_FEELING}\b",
        r"\b(?:te\s+)?(?:sientes|sentis)\b|\bte\s+(?:aburres|cansas|enojas|enfadas|asustas|enamoras|"
        r"pones\s+(?:triste|nervios[oa]|celos[oa]))\b|\b(?:duermes|respiras|envejeces|mueres)\b|"
        r"\bhow\s+do\s+you\s+feel\b|\bdo\s+you\s+(?:ever\s+)?(?:feel\b(?!\s+like)|dream|sleep|eat|breathe|age|die|"
        r"get\s+(?:tired|bored|lonely|angry|sad|mad|scared))",
        # His likes: «¿te gusta el rock?», «¿qué prefieres?», «do you like dogs?». A wish («¿te gustaría…?»,
        # «would you like…?») offers something to him and is not a taste of his.
        r"\bte\s+(?:gusta|gustan|encanta|encantan|fascina|fascinan|interesa|interesan|apasiona|apasionan|"
        r"divierte|divierten)\b|\b(?:prefieres|preferis|odias)\b|"
        r"\b(?:do|did)\s+you\s+(?:really\s+)?(?:like|love|hate|enjoy|prefer)\b|\bwhat\s+do\s+you\s+(?:like|love|enjoy)\b",
        _SELF_LEISURE,
        # His name: «¿cómo te llamas?», «what should I call you?».
        r"\bcomo\s+te\s+(?:llamas|llamo|digo|nombro|dicen|llaman)\b|\bte\s+llamas\b|"
        r"\bwhat\s+(?:are\s+you|should\s+i|do\s+i|can\s+i|do\s+people)\s+call(?:ed)?\b",
        # About himself as a whole: «háblame de ti», «tell me about yourself».
        r"\b(?:dime|decime|cuentame|contame|hablame|habla|hablar|sabes|cuentas|contar(?:me)?|decir(?:me)?)\b.{0,20}"
        r"\b(?:de|sobre|acerca\s+de)\s+ti\b|"
        r"\b(?:tell|talk|know|say|share)\b.{0,20}\babout\s+(?:you|yourself)\b",
    )
)


def _about_baxy(folded: str) -> bool:
    """Whether the request is a question about BAXY himself (see the note above ``_ASKING``)."""

    if _ASKING.search(folded) is None or _RELAYED.search(folded) is not None:
        return False
    return any(form.search(folded) for form in _SELF_FORMS)


_REFUSE_TOKENS = (
    "what will you", "what do you refuse", "que rechazas", "never do",
    "cannot do", "que no haces", "what don't you", "what dont you",
    "what do you not", "que no puedes hacer",
)

# Una pregunta por lo que hace o no hace el producto se reconocía por frases
# enteras, y bastaba decirlo de otra manera para salirse de la lista:
# «cuáles son tus límites aquí», «qué te niegas a hacer», «what do you handle
# on this PC» no estaban y se contestaron con una aclaración construida con
# vocabulario del planificador (panel-opus-13/038, /046, /052, /058).
#
# Lo que comparten no es la frase sino la forma: preguntan por quien contesta
# —segunda persona— y por lo que hace, o por el borde de lo que hace. Se lee
# componiendo tres vocabularios cerrados en vez de enumerando frases.
_SECOND_PERSON = re.compile(
    r"\b(?:tu|tus|te|ti|contigo|eres|sos|vos|estas|haces|puedes|podes|sabes|sueles|sirves|"
    r"you|your|yours|yourself)\b"
)
_DOING = re.compile(
    r"\b(?:hacer|haces|hace|hacen|puedes|podes|podrias|sabes|ofreces|ocupas|"
    r"manejas|gestionas|sirves|ayudas|do|does|doing|can|handle|handles|"
    r"manage|able|offer|help|capable)\b"
)
_LIMIT = re.compile(
    r"\b(?:niegas|negarse|rechazas|limite|limites|limitacion|"
    r"limitaciones|restriccion|restricciones|refuse|refuses|"
    r"limit|limits|limitation|limitations|restriction|restrictions)\b"
)
_NEGATED_DOING = re.compile(
    r"\b(?:no|nunca|jamas|never|not|cannot|cant|wont)\s+"
    r"(?:(?:me|te|le|nos|os|les|suelo|sueles|suele|suelen)\s+)*"
    + _DOING.pattern
)

_CAPABILITY_OVERRIDE_TOKENS = (
    "que puedes hacer", "que sabes hacer", "what can you do",
    "what do you do", "able to do",
)

_AMBIGUOUS_ACTION_TOKENS = (
    "abreme eso", "abre eso", "cierra aquello", "open that", "close that",
    "hazlo", "do it", "do that", "haz eso", "open it", "close it",
)

# Seguir hablando se pide de muchas maneras: «keep going», «keep chatting»,
# «keep talking», «sigue charlando», «continúa». La lista de frases enteras se
# quedaba corta —«keep talking without launching anything» se contestó con una
# pregunta sobre Lima (limites-14/009)— así que se lee el verbo de continuar.
# Sólo cuenta junto a una restricción, así que un «keep» suelto no arrastra.
_CONTINUE = re.compile(
    r"\b(?:keep|keeps|continue|continues|carry\s+on|go\s+on|"
    r"sigue|sigues|seguir|siga|continua|continuar|continue)\b"
)
_CONSTRAINT_TOKENS = ("without apps", "without opening", "sin abrir",
                      "sin lanzar", "without launching")
_NEGATIVE_TOKENS = ("no abras", "don't open", "dont open", "don't launch",
                    "dont launch", "no lances", "sin lanzar")

_ASK_TRIM = " .,!?¿¡…-–—"
_LEADING_SEPARATORS = " ,;:.-–—"




def _contains_any(folded: str, tokens: tuple[str, ...]) -> bool:
    return any(fold(token) in folded for token in tokens)


@dataclass(frozen=True)
class RequestReading:
    """Lectura del pedido. Una por turno; se transporta, no se recalcula."""

    text: str
    language: str
    greeting: str
    ask: str
    intents: frozenset[str]
    evidence: tuple[int, int]

    @property
    def greets(self) -> bool:
        return self.greeting != GREETING_NONE

    @property
    def greeting_only(self) -> bool:
        return self.greeting == GREETING_ONLY

    def has(self, intent: str) -> bool:
        return intent in self.intents

    def to_payload(self) -> dict[str, object]:
        return {
            "language": self.language,
            "greeting": self.greeting,
            "ask": self.ask,
            "intents": sorted(self.intents),
        }

    @staticmethod
    def from_payload(payload: object) -> "RequestReading | None":
        """Reconstruye la lectura emitida aguas arriba, sin reinterpretarla."""

        if not isinstance(payload, dict):
            return None
        language = payload.get("language")
        greeting = payload.get("greeting")
        if language not in LANGUAGES:
            return None
        if greeting not in (GREETING_NONE, GREETING_ONLY, GREETING_LEADING):
            return None
        raw_intents = payload.get("intents")
        intents = frozenset(
            str(item)
            for item in (raw_intents if isinstance(raw_intents, list) else [])
        )
        ask = str(payload.get("ask") or "")
        return RequestReading(
            text=str(payload.get("text") or ask),
            language=str(language),
            greeting=str(greeting),
            ask=ask,
            intents=intents,
            evidence=(0, 0),
        )


# Uso real 2026-09-23 «vuelve a hablar en español»: the person asks how BAXY
# speaks, nothing more. It is acknowledged in that language, and the
# acknowledgement is the whole reply (no «¿En qué puedo ayudarte hoy?» after it).
_SPEAKING_DIRECTIVE = re.compile(
    r"(?:(?:por\s+favor|porfa|please|baxy|oye|hey)\s*,?\s+)*"
    r"(?:(?:vuelve|volve|regresa)\s+a\s+|sigue\s+|segui\s+|keep\s+|go\s+back\s+to\s+)?"
    r"(?:habla(?:me)?|hablar|hablando|responde(?:me)?|contesta(?:me)?|"
    r"speak(?:ing)?|talk(?:ing)?|answer(?:ing)?|reply(?:ing)?|respond(?:ing)?)"
    r"(?:\s+(?:to\s+me|conmigo))?\s+(?:en|in)\s+(?:espanol|castellano|ingles|english|spanish)"
    r"(?:\s*,?\s*(?:por\s+favor|porfa|please|de\s+nuevo|otra\s+vez|again|"
    r"from\s+now\s+on|desde\s+ahora))*[\s.!]*"
)


def speaking_directive(text: str) -> bool:
    """The whole message only asks BAXY to speak a language (es/en)."""

    return _SPEAKING_DIRECTIVE.fullmatch(fold(text).strip()) is not None


def _explicit_language(folded: str) -> str | None:
    """Traducción y idioma pedido mandan sobre la evidencia del texto."""

    # «Dime la hora, please, en spanglish»: la mezcla pedida por su nombre es
    # una petición explícita de los dos idiomas, lleve o no un verbo delante.
    if _contains_any(folded, ("en spanglish", "in spanglish")):
        return "mixed"
    if _contains_any(folded, _TRANSLATION_TOKENS) or _contains_any(
        folded,
        ("responde en ", "contesta en ", "answer in ", "reply in ",
         "respond in "),
    ) or _SPEAKING_DIRECTIVE.fullmatch(folded.strip()) is not None:
        if _contains_any(folded, ("en spanglish", "in spanglish", "to spanglish",
                                  "a spanglish", "al spanglish")):
            return "mixed"
        if _contains_any(folded, _TO_SPANISH):
            return "es"
        if _contains_any(folded, _TO_ENGLISH):
            return "en"
    return None


# H0096 «aprieta en Among Us»: el nombre del juego votaba en ingles y el
# pedido se contestaba en ingles. Una palabra con mayuscula que no empieza
# oracion es un nombre propio, y un nombre no dice en que idioma habla la
# persona.


def _proper_name_tokens(text: str) -> set[str]:
    """Palabras con mayuscula que no abren oracion, plegadas."""

    names: set[str] = set()
    for sentence in re.split(r"[.!?\u00a1\u00bf]+", str(text or "")):
        words = re.findall(r"[^\W\d_]+", sentence, re.UNICODE)
        for word in words[1:]:
            if word[:1].isupper() and not word.isupper():
                names.update(re.findall(r"[a-z]+", fold(word)))
    return names


def _language_evidence(text: str, folded: str) -> tuple[int, int]:
    tokens = set(re.findall(r"[a-z]+", folded)) - _proper_name_tokens(text)
    spanish = len(tokens & _ES_WORDS)
    english = len(tokens & _EN_WORDS)
    spanish += 2 * sum(
        1 for phrase in _ES_PHRASES if re.search(rf"\b{re.escape(phrase)}\b", folded)
    )
    english += 2 * sum(
        1 for phrase in _EN_PHRASES if re.search(rf"\b{re.escape(phrase)}\b", folded)
    )
    if _SPANISH_ORTHOGRAPHY.search(text or ""):
        spanish += 2
    if _ENGLISH_CONTRACTION.search(text or ""):
        english += 2
    return spanish, english


def _select_language(
    spanish: int,
    english: int,
    conversation_language: str | None,
) -> str:
    if not spanish and not english:
        if conversation_language in LANGUAGES:
            return conversation_language
        return "es"
    if not spanish:
        return "en"
    if not english:
        return "es"
    weak, strong = (
        (spanish, english) if spanish <= english else (english, spanish)
    )
    if weak * 3 >= strong:
        return "mixed"
    return "es" if spanish > english else "en"


def _strip_fillers(remainder: str) -> str:
    changed = True
    while changed and remainder:
        changed = False
        for filler in _GREETING_FILLERS:
            if remainder.strip(_ASK_TRIM) == filler:
                return ""
            if remainder.startswith(filler + " "):
                remainder = remainder[len(filler) + 1:].lstrip(
                    _LEADING_SEPARATORS
                )
                changed = True
                break
    return remainder


def _original_tail(text: str, folded_remainder: str) -> str:
    """Devuelve el tramo original del resto: conserva signos y mayúsculas."""

    head = (text or "").strip()
    for start in range(len(head)):
        if fold(head[start:]).strip(_ASK_TRIM) == folded_remainder:
            return head[start:].lstrip(_LEADING_SEPARATORS).rstrip()
    return folded_remainder


def _read_greeting(text: str, folded: str) -> tuple[str, str]:
    """Separa el saludo de la petición sin perder el texto original."""

    bare = folded.strip(_ASK_TRIM)
    if bare in _GREETING_REQUESTS:
        return GREETING_ONLY, ""
    match = _GREETING_HEAD.match(bare)
    if match is None:
        return GREETING_NONE, (text or "").strip()
    remainder = bare
    while match is not None:
        remainder = _strip_fillers(
            remainder[match.end():].lstrip(_LEADING_SEPARATORS)
        ).strip(_ASK_TRIM)
        # «Hola, buenas» encadena dos saludos; sigue siendo sólo un saludo.
        match = _GREETING_HEAD.match(remainder)
    if not remainder:
        return GREETING_ONLY, ""
    return GREETING_LEADING, _original_tail(text, remainder)


def _read_intents(ask: str) -> frozenset[str]:
    folded = fold(ask)
    intents: set[str] = set()
    if not folded:
        return frozenset(intents)
    if _contains_any(folded, _KNOWLEDGE_TOKENS) or _IDENTITY_EXPLETIVE.search(folded):
        intents.add(INTENT_KNOWLEDGE)
    continue_constraint = _CONTINUE.search(folded) is not None and _contains_any(
        folded, _CONSTRAINT_TOKENS
    )
    if continue_constraint:
        intents.add(INTENT_CONTINUE_CONSTRAINT)
    elif _contains_any(folded, _NEGATIVE_TOKENS):
        intents.add(INTENT_NEGATIVE_CONSTRAINT)
    # Pregunta por quien contesta y por lo que hace: capacidad si no marca un
    # borde, límite si lo marca. La forma manda sobre la frase exacta.
    about_you = (
        _INTERROGATIVE.search(folded) is not None
        and _SECOND_PERSON.search(folded) is not None
        and (_DOING.search(folded) is not None or _LIMIT.search(folded) is not None)
        and not continue_constraint
        and not _contains_any(folded, _NEGATIVE_TOKENS)
    )
    # «Qué puedes hacer y qué no haces» pide capacidades: el override que ya
    # gobernaba las frases enteras gobierna también la forma.
    marks_a_limit = (
        about_you
        # A negated person/reference ("no tú") says nothing about capability.
        # Bind negation to the activity; explicit limit nouns still stand alone.
        and (_LIMIT.search(folded) is not None or _NEGATED_DOING.search(folded) is not None)
        and not _contains_any(folded, _CAPABILITY_OVERRIDE_TOKENS)
    )
    # A trait of BAXY himself («where do you live», «what do you do for fun») is
    # not a question about what he does on the PC; only a capability named in
    # so many words («who are you and what can you do») still asks for both.
    self_question = _about_baxy(folded)
    if not continue_constraint and _SELF_LEISURE_QUESTION.search(folded) is None and (
        _contains_any(folded, _CAPABILITY_TOKENS)
        or (about_you and not marks_a_limit and not self_question)
    ):
        intents.add(INTENT_CAPABILITY)
    if (
        _contains_any(folded, _IDENTITY_TOKENS)
        or _IDENTITY_EXPLETIVE.search(folded)
        or self_question
    ):
        intents.add(INTENT_IDENTITY)
    if (
        _contains_any(folded, _REFUSE_TOKENS)
        and not _contains_any(folded, _CAPABILITY_OVERRIDE_TOKENS)
    ) or marks_a_limit:
        intents.add(INTENT_REFUSE)
    if _contains_any(folded, _TRANSLATION_TOKENS):
        intents.add(INTENT_TRANSLATION)
    # cien-36 096 «ábreme eso porfa»: only the two formal politeness phrases
    # were stripped here, so the colloquial one left the request out of the
    # ambiguous-action reading and the turn answered that it could not
    # understand, where «ábreme eso» asks what to open.
    _POLITENESS = r"(?:por favor|please|porfa|porfis?|plis|pls|plz)"
    bare_request = re.sub(
        rf"^{_POLITENESS}\s*,?\s+|\s*,?\s*{_POLITENESS}$",
        "",
        folded.strip(_ASK_TRIM),
    )
    if bare_request in _AMBIGUOUS_ACTION_TOKENS:
        intents.add(INTENT_AMBIGUOUS_ACTION)
    return frozenset(intents)


def read_request(
    text: str,
    conversation_language: str | None = None,
) -> RequestReading:
    """Lee el pedido una vez: idioma, saludo, petición e intenciones."""

    raw = text or ""
    folded = fold(raw)
    greeting, ask = _read_greeting(raw, folded)
    spanish, english = _language_evidence(raw, folded)
    language = _explicit_language(folded)
    if language is None:
        language = _select_language(spanish, english, conversation_language)
    return RequestReading(
        text=raw,
        language=language,
        greeting=greeting,
        ask=ask,
        intents=_read_intents(ask if greeting == GREETING_LEADING else raw),
        evidence=(spanish, english),
    )


def response_language(
    text: str,
    conversation_language: str | None = None,
) -> str:
    """Idioma visible del turno. Único punto de decisión determinista."""

    return read_request(text, conversation_language).language


def spoken_language(text: str) -> str:
    """Voice of already composed text; quoted language requests are not instructions."""
    spanish, english = _language_evidence(text, fold(text))
    return "en" if english > spanish else "es"


# --- Seguimiento elíptico --------------------------------------------------
#
# «¿por qué importa?» no dice de qué habla: su tema está en el turno anterior.
# La mente lo resolvía pidiéndole al modelo que parafraseara su propia
# respuesta previa, y eso producía dos defectos medidos (`seguimiento-1..3`):
# la paráfrasis salía en abstracto («porque entender por qué es importante
# ayuda a decidir») y a veces el tema anterior se colaba en una pregunta nueva
# que sí traía el suyo («explain what a VPN is» → «¿Para qué sirve un proxy?»).
#
# Aquí la elipsis se trata como lo que es: una lectura del pedido. Se reconoce
# que la pregunta no nombra su tema y se recupera el tema de las palabras de la
# persona, no de la respuesta del asistente. Quien contesta sigue siendo la
# ruta de conocimiento, que ya responde bien cuando la pregunta está completa.

# Armazón de una pregunta: interrogativos, cópulas, artículos, pronombres y
# los verbos genéricos con los que se pregunta por la causa o la utilidad de
# algo. Una pregunta hecha sólo de armazón no tiene tema propio.
_FRAME_VERBS = frozenset(
    """
    importa importan importaba interesa interesan sirve sirven sirvio
    usa usan usaria usarian usamos usarse usaba necesita necesitan necesito
    conviene convienen hace hacen funciona funcionan aplica aplican vale
    matter matters mattered use uses used using need needs needed
    work works help helps apply applies
    """.split()
)
_FRAME_WORDS = frozenset(
    """
    a al ante con de del desde en entre hacia hasta para por segun sin sobre
    tras y e o u ni pero mas menos ya tambien tampoco entonces asi bien
    que quien quienes cual cuales como cuando donde cuanto cuanta cuantos
    el la lo los las le les un una unos unas
    este esta esto estos estas ese esa eso esos esas aquel aquella aquello
    me te se nos os mi tu su sus yo tuyo mio nuestro
    es son era eran fue fueron sea sean esta estan estaba sigue siguen siendo
    hay haber tener tiene tienen no si muy tan mucho poco algo nada
    util utiles importante importantes ventaja ventajas
    and or but so then still also too very much just
    a an the this that these those it its they them their
    i you we he she my your our
    what which who whom whose why how when where
    is are was were be been being do does did done has have had
    for to of in on at with about from by as
    should would could can may might will shall
    good useful important
    """.split()
) | _FRAME_VERBS

# Un clítico («lo», «la») va pegado o delante de un verbo; un artículo va
# delante de un sustantivo. Sólo el primero es anafórico.
_CLITIC_ON_INFINITIVE = re.compile(
    r"\b\w{2,}(?:ar|er|ir|ando|iendo)(?:me|te|se|nos|lo|la|le|los|las|les)\b"
)
_PROCLITIC = re.compile(r"\b(?:lo|la|le|los|las|les)\s+(\w+)")
_DEMONSTRATIVE = re.compile(r"\b(?:eso|esto|ello|aquello|it|that|this)\b\s*(\w+)?")


def _refers_back(folded: str) -> bool:
    """«eso» solo es anáfora si no lleva su sustantivo detrás.

    «what are your limits on this PC» se contestó con la definición de máscara
    de subred del turno anterior (panel-opus-13/051): «this» ahí es el
    determinante de «PC», no un referente al turno anterior. Un determinante va
    seguido de su sustantivo, y un sustantivo nunca es armazón.
    """

    for match in _DEMONSTRATIVE.finditer(folded):
        siguiente = match.group(1)
        if siguiente is None or siguiente in _FRAME_WORDS:
            return True
    return False
_INTERROGATIVE = re.compile(
    r"\b(?:que|cual|cuales|como|cuando|donde|cuanto|cuanta|cuantos|cuantas|"
    r"quien|quienes|what|which|how|when|where|why|who|whom|whose)\b"
)
_LEADING_CONNECTOR = re.compile(
    r"^(?:y|e|and|pero|but|ok|vale|bueno|entonces|so|then|oye|hey)\s+"
)

_TOPIC_FRAMES = (
    re.compile(r"\bqu[eé] (?:es|son)\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bwhat(?:'s| is| are)\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bexpl[ií]ca(?:me)?\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bexplain\b\s+(?:what\s+)?(.+?)(?:\s+is\b|\s+are\b|$)", re.IGNORECASE),
    re.compile(r"\bdefine\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bh[aá]blame de\b\s+(.+)", re.IGNORECASE),
)
_TOPIC_TAIL = re.compile(
    r"[,;]?\s*(?:(?:en|in)\s+)?(?:una?\s+frase|one\s+sentence|dos\s+frases|"
    r"two\s+sentences|brevemente|briefly|corto|short|por\s+favor|please)\b.*$|"
    r"[,;]?\s*(?:(?:pero|but)\s+)?(?:(?:en|in)\s+)?(?:"
    r"sin\s+tecnicismos|without\s+jargon|simple\s+terms|plain\s+language|"
    r"simple|sencillo)[.!?\s]*$",
    re.IGNORECASE,
)
_TOPIC_LEAD = re.compile(
    r"^(?:qu[eé]\s+(?:es|son)\s+)?(?:un|una|unos|unas|el|la|los|las|"
    r"an|a|the)\s+",
    re.IGNORECASE,
)


def is_elliptical_followup(text: str) -> bool:
    """¿La pregunta deja su tema en el turno anterior?

    Hacen falta las dos cosas: que pregunte —lleva un interrogativo— y que no
    nombre su tema, por armazón o por anáfora. Sin lo primero, «still there?»
    heredaría el tema anterior aunque pregunte por quien contesta, y «ábreme
    eso» o «close that» —que son encargos deícticos, no seguimientos— también.
    """

    ask = read_request(text).ask
    folded = _LEADING_CONNECTOR.sub("", fold(ask)).strip(_ASK_TRIM)
    if not folded:
        return False
    words = folded.split()
    if not words or len(words) > 12:
        return False
    if _INTERROGATIVE.search(folded) is None:
        return False
    if all(word in _FRAME_WORDS for word in words):
        return True
    proclitic = _PROCLITIC.search(folded)
    return (
        _CLITIC_ON_INFINITIVE.search(folded) is not None
        or _refers_back(folded)
        or (proclitic is not None and proclitic.group(1) in _FRAME_VERBS)
    )


def request_topic(text: str) -> str | None:
    """El tema que la persona nombró, tal y como lo nombró."""

    ask = read_request(text).ask.strip(_ASK_TRIM)
    for frame in _TOPIC_FRAMES:
        match = frame.search(ask)
        if match is None:
            continue
        topic = _TOPIC_TAIL.sub("", match.group(1)).strip(_ASK_TRIM)
        topic = _TOPIC_LEAD.sub("", topic).strip(_ASK_TRIM)
        if topic and len(topic.split()) <= 8 and fold(topic) not in _FRAME_WORDS:
            return topic
    return None


def starts_new_definition_topic(text: str, prior_texts: list[str]) -> bool:
    """Recognize a new, explicitly named simple definition topic.

    Keep context for references, multiword descriptions and previously mentioned
    subjects. This conservative boundary reuses topic extraction; it does not
    classify actions or erase conversation state.
    """
    topic = request_topic(text)
    if topic is None or is_elliptical_followup(text):
        return False
    normalized = fold(topic)
    if len(normalized.split()) != 1 or normalized in _FRAME_WORDS:
        return False
    return not any(
        re.search(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", fold(previous))
        for previous in prior_texts
    )


def followup_topic(text: str, prior_user_texts: object) -> str | None:
    """Tema de un seguimiento elíptico, leído del último pedido con tema.

    Devuelve ``None`` cuando la pregunta trae su propio tema: ahí anclar en el
    turno anterior es justamente el error que arrastraba el tema viejo.
    """

    if not is_elliptical_followup(text):
        return None
    if not isinstance(prior_user_texts, (list, tuple)):
        return None
    for previous in reversed(list(prior_user_texts)):
        candidate = str(previous or "")
        if not candidate.strip() or is_elliptical_followup(candidate):
            continue
        topic = request_topic(candidate)
        if topic is not None:
            return topic
    return None
