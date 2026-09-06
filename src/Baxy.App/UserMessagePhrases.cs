namespace Baxy.App;

/// <summary>
/// Tablas de reconocimiento del shell: trozos del pedido de la persona y
/// marcas de defecto en un borrador del modelo. Ninguno se publica.
///
/// Viven separados de <see cref="UserMessagePolicy"/> por la misma razón por la
/// que el censo de prosa visible excluye los parsers y el corpus de turnos: son
/// texto de ENTRADA. Mezclados con la política, cada patrón nuevo contaba como
/// prosa fija y escondía la única medida que vigila las frases de salida.
/// </summary>
internal static class UserMessagePhrases
{
    /// <summary>Pide que BAXY se describa o enumere lo que hace.</summary>
    /// <remarks>
    /// La lectura del pedido vive en la mente; esta tabla es el reconocimiento
    /// de entrada del shell y tiene que decir lo mismo. Cuando se quedó corta
    /// —«what do you handle», «cuáles son tus límites»— la respuesta correcta
    /// del catálogo se vetó como catálogo no solicitado y el turno murió
    /// agotado (limites-18/006). `RequestReadingConformanceTests` compara las
    /// dos lecturas sobre el mismo corpus para que la divergencia salga en una
    /// prueba y no en una corrida de cien turnos.
    /// </remarks>
    internal static readonly string[] SelfDescriptionAsks =
    [
        "que puedes hacer", "que sabes hacer", "what can you do",
        "what do you do", "able to do", "te ocupas", "echar una mano",
        "what are you able", "que no haces", "what don't you",
        "what do you not", "what do you handle", "what do you manage",
        "what do you offer", "de que te ocupas", "que haces aqui",
        "que haces en este", "que manejas", "que gestionas",
        "en que me puedes ayudar", "en que puedes ayudar",
        "what can you help", "how can you help",
        "tus limites", "your limits", "tus limitaciones",
        "your limitations", "te niegas", "do you refuse",
        "no puedes hacer", "cannot you do", "que no puedes",
        "what will you never", "nunca haras", "never do",
    ];

    /// <summary>Pregunta de conocimiento, límites o identidad.</summary>
    internal static readonly string[] KnowledgeAsks =
    [
        "que es ", "que es un", "explicame", "explica ", "define ",
        "what is ", "what are ", "why ", "por que ", "por que importa",
        "te ocupas", "what do you do", "what can you do",
        "que puedes hacer", "que sabes hacer", "able to do",
        "echar una mano", "what will you", "what do you refuse",
        "que rechazas", "never do", "cannot do", "no haces",
    ];

    /// <summary>Pedidos cuyo contenido entero es «salúdame».</summary>
    internal static readonly string[] GreetingAsks =
    [
        "just say hi", "say hi", "say hello", "solo un hola", "un saludo",
        "un saludo corto", "solo un saludo", "saludo corto", "saludame",
    ];

    /// <summary>El borrador afirma la conectividad en primera persona.</summary>
    internal static readonly string[] FirstPersonConnectivityClaims =
    [
        "tengo internet", "i have internet", "i've got internet",
        "ive got internet", "i am connected", "i'm connected",
        "im connected", "i am not connected", "i'm not connected",
        "im not connected", "no estoy conectado", "i am online",
        "i'm online", "im online", "estoy online",
    ];

    /// <summary>El borrador invierte una pregunta por sus límites.</summary>
    internal static readonly string[] RefusalDenials =
    [
        "cannot refuse", "can't refuse", "can not refuse",
        "will not refuse", "won't refuse", "wont refuse",
        "no puedo rechazar", "no rechazo",
    ];

    /// <summary>El borrador rechaza a la persona en vez de seguir hablando.</summary>
    internal static readonly string[] ContinueConstraintRefusals =
    [
        "eso no lo hago", "i don't do", "i do not do", "no puedo ayudar",
        "cannot continue without", "can't continue without",
        "no puedo continuar sin", "cannot continue without opening",
    ];

    /// <summary>
    /// Formas en que una respuesta contesta a una pregunta por los límites:
    /// negando o restringiéndose. La mente acepta las dos; exigir sólo la
    /// negación aquí agotaba turnos que Python ya había dado por buenos.
    /// </summary>
    internal static readonly string[] LimitAnswers =
    [
        "i don't do", "i do not do", "eso no lo hago", "don't do that",
        "i won't", "i will not", "i will never", "i never", "i cannot",
        "i can't", "cannot ", "no puedo", "no hago", "nunca",
        "only do", "only what", "only the work", "nothing beyond",
        "nothing else", "nothing more", "not listed", "outside",
        "solo hago", "sólo hago", "solo lo que", "sólo lo que",
        "nada mas", "nada más", "unicamente", "únicamente", "fuera de",
    ];

    /// <summary>El borrador afirma no poder abrir lo que nadie pidió abrir.</summary>
    internal static readonly string[] OpenRefusals =
    [
        "no puedo abrir", "no pude abrir", "cannot open", "can't open",
        "could not open", "couldn't open", "unable to open",
        "no puedo lanzar", "cannot launch",
        "i don't do that", "i do not do that", "eso no lo hago",
        "no puedo ayudarte", "i can't help",
    ];
}
