using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal sealed record UserMessageDraft(
    string Source,
    string Intent,
    string? DiagnosticCode);

internal enum UserMessageEventType
{
    Welcome,
    Status,
    Clarification,
    Confirmation,
    Error,
}

internal sealed record UserMessageEvent
{
    private static readonly Regex StableDiagnosticCodePattern = new(
        @"^[1-5][0-9]{2}: ""[a-z0-9_]+""$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private UserMessageEvent(
        UserMessageEventType type,
        string intent,
        string? diagnosticCode = null)
    {
        Type = type;
        Intent = intent;
        DiagnosticCode = diagnosticCode;
    }

    public UserMessageEventType Type { get; }

    public string Intent { get; }

    public string? DiagnosticCode { get; }

    public static UserMessageEvent Welcome { get; } = new(
        UserMessageEventType.Welcome,
        "welcome");

    public static UserMessageEvent Status { get; } = new(
        UserMessageEventType.Status,
        "status");

    public static UserMessageEvent Clarification { get; } = new(
        UserMessageEventType.Clarification,
        "clarification");

    public static UserMessageEvent Confirmation { get; } = new(
        UserMessageEventType.Confirmation,
        "confirmation");

    public static UserMessageEvent Error(string diagnosticCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(diagnosticCode);
        if (!StableDiagnosticCodePattern.IsMatch(diagnosticCode)
            || diagnosticCode is not UserMessageDiagnosticCodes.MissingData
                and not UserMessageDiagnosticCodes.Timeout
                and not UserMessageDiagnosticCodes.ActionNotCompleted
                and not UserMessageDiagnosticCodes.LocalService)
        {
            throw new ArgumentException(
                "El código de diagnóstico no pertenece al conjunto estable.",
                nameof(diagnosticCode));
        }

        return new UserMessageEvent(
            UserMessageEventType.Error,
            "error",
            diagnosticCode);
    }
}

internal static class UserMessageDiagnosticCodes
{
    public const string MissingData = "344: \"faltan_datos\"";
    public const string Timeout = "408: \"tiempo_agotado\"";
    public const string ActionNotCompleted = "500: \"accion_no_completada\"";
    public const string LocalService = "503: \"servicio_local\"";
}

internal static class MindClarificationPolicy
{
    private const string TrustedClarificationPrefix =
        "\nAclaración confiable del usuario: ";

    public static bool IsSelfContainedRequest(
        string userText,
        MindTurnDecision decision)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(userText);
        ArgumentNullException.ThrowIfNull(decision);
        if (NaturalSystemStatusRequestParser.IsCurrentTimeRequest(userText))
        {
            return true;
        }

        return decision.Kind switch
        {
            "action" =>
                decision.Operation is { Length: > 0 } operation
                && decision.EffectOperations.Count == 1
                && string.Equals(
                    decision.EffectOperations[0],
                    operation,
                    StringComparison.Ordinal),
            "plan" => decision.Operation is null,
            // Slot values such as "mañana a las 9", "Opera" or "la segunda"
            // can look conversational in isolation. They must keep the
            // pending objective instead of silently discarding it.
            "conversation" => false,
            _ => false,
        };
    }

    public static bool ShouldResumePendingObjective(
        string userText,
        MindTurnDecision decision) =>
        decision.PreserveObjective
        && !IsSelfContainedRequest(userText, decision);

    public static string ResumeObjective(
        string pendingObjective,
        string clarification)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(pendingObjective);
        ArgumentException.ThrowIfNullOrWhiteSpace(clarification);
        return string.Concat(
            pendingObjective,
            TrustedClarificationPrefix,
            clarification);
    }
}

internal static class UserMessagePolicy
{
    internal static bool BypassLlmCompositionForTests { get; set; }

    private static readonly string[] ForbiddenTerms =
    [
        "planner",
        "router",
        "tool",
        "catálogo",
        "catalogo",
        "schema",
        "operación",
        "operacion",
        "capacidad interna",
        "language model",
        "modelo de lenguaje",
        "resolver el efecto",
        "el efecto '",
        "opaque identity",
        "observed profile",
        "grounding",
        "checkpoint",
        "reconciliación",
        "reconciliacion",
        "motor local",
        "core",
        "datos verificables",
        "pasos verificables",
        "identificador interno",
    ];

    internal static IReadOnlyList<string> ForbiddenResponseTerms => ForbiddenTerms;

    internal static bool IsStructuredFacts(string source)
    {
        ReadOnlySpan<char> trimmed = source.AsSpan().Trim();
        return trimmed.Length >= 2 && trimmed[0] == '{' && trimmed[^1] == '}';
    }

    public static UserMessageDraft Create(
        string source,
        UserMessageEvent messageEvent)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        ArgumentNullException.ThrowIfNull(messageEvent);
        return new UserMessageDraft(
            source,
            messageEvent.Intent,
            messageEvent.DiagnosticCode);
    }

    public static bool IsSafe(string text) =>
        !string.IsNullOrWhiteSpace(text)
        && text.Length <= 4_096
        && !ForbiddenTerms.Any(term => text.Contains(term, StringComparison.OrdinalIgnoreCase));

    public static bool IsSafe(string text, UserMessageDraft draft)
    {
        return ModelResponseRejectionReason(text, draft) is null;
    }

    public static string? ModelResponseRejectionReason(
        string? modelText,
        UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        if (string.IsNullOrWhiteSpace(modelText))
        {
            return "no_response";
        }
        if (IsStructuredFacts(modelText))
        {
            return "structured_facts_not_prose";
        }
        if (!IsSafe(modelText))
        {
            return "unsafe_language";
        }

        if (IsPunctuationOnly(modelText) || IsTooThin(modelText))
        {
            return "no_response";
        }

        if (LooksLikeMachineSlotAsk(FoldForPolicy(modelText)))
        {
            return "internal_code";
        }

        if (ContainsStutteredToken(modelText))
        {
            return "internal_code";
        }
        if (Regex.IsMatch(
                modelText,
                @"\b[a-z]{2,}(?:_[a-z0-9]+){1,}\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || FoldForPolicy(modelText).Contains(
                "el mensaje es",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "sigo con ",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "usar esa respuesta",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "unusable answer",
                StringComparison.Ordinal)
            || Regex.IsMatch(
                FoldForPolicy(modelText),
                @"\bunsafe\b|compose unavailable|compose function",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            return "internal_code";
        }
        if (draft.Intent is "status" or "error")
        {
            if (AttributesBaxyActionToUser(draft.Source, modelText))
            {
                return "wrong_actor";
            }
            if (!PreservesBaxyFirstPerson(draft.Source, modelText))
            {
                return "missing_baxy_action";
            }
            if (!PreservesRequiredFacts(draft.Source, modelText))
            {
                return "missing_structured_fact";
            }
            if (!PreservesRequiredLiteralFacts(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (!PreservesObservedClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventedClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (AddsGenericFollowUp(modelText))
            {
                return "generic_follow_up";
            }
            if (draft.Intent == "status" && StartsWithRequestImperative(modelText))
            {
                return "imperative_result";
            }
            if (draft.Intent == "status"
                && ReversesSuccessfulResult(draft.Source, modelText))
            {
                return "reversed_result";
            }
            if (draft.Intent == "error"
                && ReversesFailedResult(draft.Source, modelText))
            {
                return "reversed_result";
            }
        }
        if (draft.Intent == "confirmation"
            && !PreservesRequiredConfirmationChoices(draft.Source, modelText))
        {
            return "missing_confirmation_choice";
        }

        if (draft.Intent == "welcome"
            && ProposesUnsolicitedCatalogAction(string.Empty, modelText))
        {
            return "unsolicited_catalog";
        }

        if (draft.Intent == "welcome" && LooksLikeFailure(modelText))
        {
            return "reversed_result";
        }

        if (draft.Intent == "welcome" && ClaimsUnverifiedSuccess(modelText))
        {
            return "reversed_result";
        }

        return null;
    }

    public static string? AcceptModelAuthoredResponse(
        string? modelText,
        UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        return ModelResponseRejectionReason(modelText, draft) is null
            ? WithDiagnosticCode(modelText!, draft)
            : null;
    }

    public static bool IsSafeConversationReply(string userText, string reply)
    {
        if (!IsSafe(reply))
        {
            return false;
        }

        if (NaturalSystemStatusRequestParser.IsCurrentTimeRequest(userText)
            || NaturalSystemStatusRequestParser.IsCurrentTimeRequest(reply)
            || RestatesTheRequest(userText, reply)
            || ContainsClockPattern(reply)
            || ContainsInternalCode(reply)
            || ClaimsUnverifiedSuccess(reply)
            || ContainsMeasuredInventedToken(reply)
            || ContainsStutteredToken(reply)
            || ProposesUnsolicitedCatalogAction(userText, reply)
            || MentionsUnsolicitedCatalogFamily(userText, reply)
            || LooksLikeMachineSlotAsk(FoldForPolicy(reply))
            || IsPunctuationOnly(reply)
            || IsTooThin(reply)
            || AsksToInventClock(FoldForPolicy(reply))
            || EchoesRequestAsQuestion(userText, reply)
            || GreetsOutOfWorldTarget(FoldForPolicy(reply))
            || ClaimsUnverifiedConnectivity(FoldForPolicy(reply))
            || (LooksLikeFailure(reply)
                && ConversationFallbackIntent(userText) == "welcome")
            || (LooksLikeOutOfWorldRequest(FoldForPolicy(userText))
                && (reply.Contains('?', StringComparison.Ordinal)
                    || reply.Contains('¿', StringComparison.Ordinal)))
            || (LooksLikeKnowledgeQuestion(FoldForPolicy(userText))
                && (reply.Contains('?', StringComparison.Ordinal)
                    || reply.Contains('¿', StringComparison.Ordinal))))
        {
            return false;
        }

        string folded = FoldForPolicy(reply);
        return !ContainsPersonMetadiscourse(folded);
    }

    private static readonly string[] MeasuredInventedTokens =
    [
        "talcr",
        "decirar",
        "readver",
        "vme",
        "comprobo",
        "llamarar",
        "asistante",
        "nochesos",
    ];

    internal static bool IsConnectivityStatusRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        string folded = FoldForPolicy(text).Trim().Trim('?', '.', '!', '¿', '¡', ' ');
        return (folded is "online"
            or "hay red"
            or "hay internet"
            or "tengo internet"
            or "tengo red"
            or "tienes internet"
            or "have i got internet"
            or "do i have internet"
            or "got internet"
            or "am i online"
            or "am i connected"
            or "estoy conectado"
            or "is there internet")
            || folded.EndsWith("conectado a internet", StringComparison.Ordinal);
    }

    internal static string ConversationFallbackIntent(string userText)
    {
        string user = FoldForPolicy(userText);
        if (LooksLikeAmbiguousAction(user))
        {
            return "clarification";
        }

        if (LooksLikeOutOfWorldRequest(user))
        {
            return "out_of_catalog";
        }

        if (LooksLikeKnowledgeQuestion(user))
        {
            return "clarification";
        }

        return "welcome";
    }

    internal static bool ProposesUnsolicitedCatalogAction(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        string said = FoldForPolicy(reply);
        if (!LooksLikeCatalogProposal(said)
            || said.Contains("que accion", StringComparison.Ordinal)
            || said.Contains("what action", StringComparison.Ordinal)
            || said.Contains("que necesitas", StringComparison.Ordinal)
            || said.Contains("what do you need", StringComparison.Ordinal)
            || said.Contains("en que puedo ayudarte", StringComparison.Ordinal))
        {
            return false;
        }

        if (!UserInvitedAnyCatalogAction(user))
        {
            return true;
        }

        bool coveredFamilyNamed = false;
        foreach (string[] family in CatalogFamilies)
        {
            if (!ContainsAny(said, family))
            {
                continue;
            }

            if (!UserCoversCatalogFamily(user, family))
            {
                return true;
            }

            coveredFamilyNamed = true;
        }

        return !coveredFamilyNamed;
    }

    internal static bool MentionsUnsolicitedCatalogFamily(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        string said = FoldForPolicy(reply);
        foreach (string[] family in CatalogFamilies)
        {
            if (ContainsAny(said, family) && !UserCoversCatalogFamily(user, family))
            {
                return true;
            }
        }

        return false;
    }

    private static bool UserCoversCatalogFamily(string user, string[] family)
    {
        if (ContainsAny(user, family))
        {
            return true;
        }

        if (FamilyNamed(family, "ventana", "window")
            && ContainsAny(user, ["cierra", "close", "abre", "open"]))
        {
            return true;
        }

        if (FamilyNamed(family, "wifi", "wlan", "inalambr")
            && ContainsAny(user, ["internet", "red", "online", "conectado"]))
        {
            return true;
        }

        return false;
    }

    private static readonly string[][] CatalogFamilies =
    [
        ["papelera", "recycle", "reciclaje"],
        ["ventana", "window"],
        ["wifi", "wlan", "inalambr"],
        ["steam"],
        ["rutina", "routine"],
        ["portapapeles", "clipboard"],
        ["teclado", "keyboard", "win32"],
        ["backup", "sha-256", "sha256"],
        ["cdp"],
        ["volumen", "audio", "silencio", "mute", "salida predeterminada"],
        ["notificacion", "notification"],
        ["bitcoin", "neptuno"],
        ["busque", "buscar en la web", "search the web"],
        ["minimice", "minimize", "minimizar"],
    ];

    private static bool LooksLikeCatalogProposal(string folded) =>
        folded.Contains("quieres que", StringComparison.Ordinal)
        || folded.Contains("want me to", StringComparison.Ordinal)
        || folded.Contains("do you want me", StringComparison.Ordinal)
        || folded.Contains("metadatos de una rutina", StringComparison.Ordinal)
        || folded.Contains("salida predeterminada", StringComparison.Ordinal);

    private static bool LooksLikeMachineSlotAsk(string folded) =>
        folded.Contains("nombre de la aplicacion", StringComparison.Ordinal)
        || folded.Contains("name of the application", StringComparison.Ordinal)
        || folded.Contains("private directory", StringComparison.Ordinal)
        || folded.Contains("zip backup", StringComparison.Ordinal)
        || folded.Contains("reglas establecidas", StringComparison.Ordinal)
        || folded.Contains("established rules", StringComparison.Ordinal)
        || folded.Contains("app id", StringComparison.Ordinal)
        || folded.Contains("application id", StringComparison.Ordinal)
        || folded.Contains("carpeta que", StringComparison.Ordinal)
        || folded.Contains("what folder", StringComparison.Ordinal)
        || folded.Contains("which folder", StringComparison.Ordinal)
        || folded.Contains("folder you want", StringComparison.Ordinal)
        || folded.Contains("la carpeta", StringComparison.Ordinal)
        || folded.Contains("id de confirmacion", StringComparison.Ordinal)
        || folded.Contains("confirmation id", StringComparison.Ordinal)
        || folded.Contains("precio esperado", StringComparison.Ordinal)
        || folded.Contains("expected price", StringComparison.Ordinal)
        || folded.Contains("eco icmp", StringComparison.Ordinal)
        || folded.Contains("icmp", StringComparison.Ordinal)
        || folded.Contains("host que", StringComparison.Ordinal)
        || folded.Contains("subject of the email", StringComparison.Ordinal)
        || folded.Contains("asunto del correo", StringComparison.Ordinal)
        || folded.Contains("search for in this box", StringComparison.Ordinal)
        || folded.Contains("deseas abrazar", StringComparison.Ordinal);

    private static bool LooksLikeAmbiguousAction(string user) =>
        ContainsAny(
            user,
            ["abreme eso", "abre eso", "cierra aquello", "open that", "close that",
                "hazlo", "do it", "do that", "haz eso", "open it", "close it"]);

    private static bool LooksLikeKnowledgeQuestion(string user) =>
        ContainsAny(
            user,
            ["que es ", "que es un", "explicame", "explica ", "define ",
                "what is ", "what are ", "why ", "por que ", "por que importa"]);

    private static bool LooksLikeOutOfWorldRequest(string user) =>
        ContainsAny(
            user,
            ["marte", "mars", "jupiter", "saturn", "neptun", "rocket",
                "bitcoin", "titan", "postcard", "to io", " a io",
                "to the moon", "a la luna", "fabrica una hora",
                "invent a clock", "inventa una hora"]);

    private static bool AsksToInventClock(string folded) =>
        folded.Contains("te gustaria que fuera", StringComparison.Ordinal)
        || folded.Contains("hora te gustaria", StringComparison.Ordinal)
        || folded.Contains("what time would you like", StringComparison.Ordinal);

    private static bool EchoesRequestAsQuestion(string userText, string reply)
    {
        string asked = FoldForPolicy(userText).Trim().Trim('?', '.', '!', '¿', '¡', ' ');
        if (asked.Length < 10 || !reply.Contains('?', StringComparison.Ordinal))
        {
            return false;
        }

        return FoldForPolicy(reply).Contains(asked, StringComparison.Ordinal);
    }

    private static bool GreetsOutOfWorldTarget(string folded) =>
        Regex.IsMatch(
            folded,
            @"\b(?:hi|hey|hello|hola)[, ]+(?:saturno?|marte|mars|jupiter|neptuno?)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static bool ClaimsUnverifiedConnectivity(string folded) =>
        ContainsAny(
            folded,
            ["tienes internet", "got internet", "estas conectado",
                "you're connected", "you are connected", "no tienes internet",
                "not connected", "sin internet", "wifi is", "estas online",
                "you're online", "you are online", "conectado a internet"]);

    private static bool IsTooThin(string reply)
    {
        int letters = 0;
        foreach (char c in reply)
        {
            if (char.IsLetterOrDigit(c))
            {
                letters++;
                if (letters >= 2)
                {
                    return false;
                }
            }
        }

        return true;
    }

    private static bool IsPunctuationOnly(string reply)
    {
        foreach (char c in reply)
        {
            if (!char.IsWhiteSpace(c) && !char.IsPunctuation(c))
            {
                return false;
            }
        }

        return true;
    }

    private static bool UserInvitedAnyCatalogAction(string user) =>
        ContainsAny(
            user,
            [
                "cierra", "close", "abre", "open", "lanza", "launch", "borra",
                "delete", "silencia", "mute", "revisa", "muestra", "chequea",
                "check", "envia", "send", "traduce", "translate", "haz ",
                "hazlo", "do that", "do it",
            ]);

    private static bool FamilyNamed(string[] family, params string[] names)
    {
        foreach (string name in names)
        {
            foreach (string token in family)
            {
                if (string.Equals(token, name, StringComparison.Ordinal))
                {
                    return true;
                }
            }
        }

        return false;
    }

    private static bool ContainsAny(string text, IReadOnlyList<string> tokens)
    {
        foreach (string token in tokens)
        {
            if (text.Contains(token, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    private static bool ContainsInternalCode(string reply)
    {
        const RegexOptions options =
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking;
        string folded = FoldForPolicy(reply);
        return Regex.IsMatch(reply, @"\b[a-z]{2,}(?:_[a-z0-9]+){1,}\b", options)
            || Regex.IsMatch(reply, @"\b[a-z]{2,}(?:\.[a-z][a-z0-9]*){1,}\b", options)
            || folded.Contains("el mensaje es", StringComparison.Ordinal);
    }

    private static bool ClaimsUnverifiedSuccess(string reply)
    {
        string folded = FoldForPolicy(reply);
        return folded.StartsWith("listo", StringComparison.Ordinal)
            || folded.StartsWith("ready", StringComparison.Ordinal)
            || folded.StartsWith("done", StringComparison.Ordinal)
            || folded.StartsWith("hecho ya", StringComparison.Ordinal)
            || folded.Contains("el mensaje es correcto", StringComparison.Ordinal);
    }

    private static bool ContainsStutteredToken(string reply)
    {
        foreach (Match token in Regex.Matches(
            FoldForPolicy(reply),
            @"[a-zñáéíóúü]{8,}",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            string word = token.Value;
            for (int size = 2; size <= 4 && size * 2 <= word.Length; size++)
            {
                string end = word[^size..];
                string before = word[^(size * 2)..^size];
                if (string.Equals(end, before, StringComparison.Ordinal))
                {
                    return true;
                }
            }
        }

        return false;
    }

    private static bool ContainsMeasuredInventedToken(string reply)
    {
        foreach (Match token in Regex.Matches(
            FoldForPolicy(reply),
            @"[a-zñáéíóúü]+",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            foreach (string invented in MeasuredInventedTokens)
            {
                if (string.Equals(token.Value, invented, StringComparison.Ordinal))
                {
                    return true;
                }
            }
        }

        return false;
    }

    internal static string StripLeadingPromptLabels(string text)
    {
        string stripped = text.Trim();
        while (stripped.StartsWith('#'))
        {
            stripped = stripped.TrimStart('#').Trim();
        }

        return stripped;
    }

    private static bool RestatesTheRequest(string userText, string reply)
    {
        string asked = FoldForPolicy(userText).Trim().Trim('?', '.', '!', '¿', '¡', ' ');
        string answered = FoldForPolicy(reply).Trim().Trim('?', '.', '!', '¿', '¡', ' ');
        if (asked.Length < 12 || answered.Length == 0)
        {
            return false;
        }

        return answered == asked
            || (answered.StartsWith(asked, StringComparison.Ordinal)
                && answered.Length <= asked.Length + 12);
    }

    private static bool ContainsPersonMetadiscourse(string folded)
    {
        const RegexOptions options =
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking;

        // A conversational answer should address the person, not narrate
        // what "the user/person" did or wanted. Check every sentence rather
        // than only the beginning of the whole reply.
        if (Regex.IsMatch(
                folded,
                @"(?:^|[\r\n]+|[.!?]\s+)[\s«»“”‘’'()\[\]-]*(?:(?:(?:al|del|el|la|este|esta|ese|esa)\s+|(?:a|de|para)\s+(?:el|la|este|esta|ese|esa)\s+)(?:usuario|usuaria|persona)|(?:the|this|that)\s+(?:user|person|requester))\b",
                options))
        {
            return true;
        }

        // Also reject a short introductory clause followed by an explicit
        // attribution, while avoiding ordinary guidance such as
        // "Puedes crear el usuario admin desde Configuración".
        return Regex.IsMatch(
            folded,
            @"[,;:]\s*(?:(?:(?:al|del|el|la|este|esta|ese|esa)\s+|(?:a|de|para)\s+(?:el|la|este|esta|ese|esa)\s+)(?:usuario|usuaria|persona)|(?:the|this|that)\s+(?:user|person|requester))\b[^.!?\r\n]{0,80}\b(?:le gustaria|le interesa|quiere|quisiera|desea|prefiere|pidio|ha pedido|pregunto|dijo|saludo|solicito|menciono|would like|wants|asked|said|greeted|requested|mentioned|prefers|has asked)\b",
            options);
    }

    public static string WithDiagnosticCode(string text, UserMessageDraft draft)
    {
        _ = draft;
        // El código estable queda disponible para diagnóstico interno; nunca
        // forma parte del mensaje que recibe una persona.
        return text.Trim();
    }

    private static bool LooksLikeFailure(string sourceOrResult)
    {
        if (IsStructuredFacts(sourceOrResult)
            && TryReadJson(sourceOrResult, out JsonElement root)
            && root.TryGetProperty("polarity", out JsonElement polarity)
            && polarity.ValueKind == JsonValueKind.String)
        {
            return string.Equals(polarity.GetString(), "failure", StringComparison.Ordinal);
        }

        string normalized = FoldForPolicy(sourceOrResult);
        return normalized.Contains("no pude", StringComparison.Ordinal)
        || normalized.Contains("no puedo", StringComparison.Ordinal)
        || normalized.Contains("no complete", StringComparison.Ordinal)
        || normalized.Contains("no logre", StringComparison.Ordinal)
        || normalized.Contains("no se pudo", StringComparison.Ordinal)
        || normalized.Contains("falló", StringComparison.Ordinal)
        || normalized.Contains("fallo", StringComparison.Ordinal)
        || normalized.Contains("no recibí", StringComparison.Ordinal)
        || normalized.Contains("no realicé", StringComparison.Ordinal)
        || normalized.Contains("no interpreté", StringComparison.Ordinal)
        || normalized.Contains("no está disponible", StringComparison.Ordinal)
        || normalized.Contains("i couldn't", StringComparison.Ordinal)
        || normalized.Contains("i could not", StringComparison.Ordinal)
        || normalized.Contains("wasn't able", StringComparison.Ordinal)
        || normalized.Contains("was not able", StringComparison.Ordinal)
        || normalized.Contains("failed", StringComparison.Ordinal);
    }

    private static bool AttributesBaxyActionToUser(string source, string result)
    {
        string sourceFolded = FoldForPolicy(source);
        bool baxyPerformedAction = Regex.IsMatch(
            sourceFolded,
            @"\b(?:abri|enfoque|cerre|ejecute|inicie|hice|puse|ajuste|controle|copie|pegue|resolvi|active|desactive|seleccione|cambie|envie|guarde|conecte|force|adelante|retrocedi|silencie|reactive|presione|escribi|cree|elimine|verifique)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
        if (!baxyPerformedAction)
        {
            return false;
        }

        string resultFolded = FoldForPolicy(result);
        return Regex.IsMatch(
            resultFolded,
            @"\b(?:abriste|enfocaste|cerraste|ejecutaste|iniciaste|hiciste|pusiste|ajustaste|controlaste|copiaste|pegaste|resolviste|activaste|desactivaste|seleccionaste|cambiaste|enviaste|guardaste|conectaste|forzaste|adelantaste|retrocediste|silenciaste|reactivaste|presionaste|escribiste|creaste|eliminaste|verificaste)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    public static IReadOnlyList<string> RequiredBaxyActions(string source)
    {
        if (IsStructuredFacts(source))
        {
            return [];
        }

        MatchCollection matches = Regex.Matches(
            source,
            @"\b(?:abrí|enfoqué|cerré|ejecuté|inicié|hice|puse|ajusté|controlé|copié|pegué|resolví|activé|desactivé|seleccioné|cambié|envié|guardé|conecté|forcé|adelanté|retrocedí|silencié|reactivé|presioné|escribí|creé|eliminé|verifiqué)\b",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant
                | RegexOptions.NonBacktracking);
        return matches
            .Select(static match => match.Value.ToLowerInvariant())
            .Distinct(StringComparer.Ordinal)
            .ToArray();
    }

    public static IReadOnlyList<string> RequiredConfirmationWords(string source)
    {
        if (IsStructuredFacts(source)
            && TryReadJson(source, out JsonElement root)
            && root.TryGetProperty("choices", out JsonElement choices)
            && choices.ValueKind == JsonValueKind.Array)
        {
            return choices.EnumerateArray()
                .Select(static item => item.GetString())
                .Where(static item => !string.IsNullOrWhiteSpace(item))
                .Select(static item => item!)
                .ToArray();
        }

        var words = new List<string>();
        AddPair("confirmar", "confirm");
        AddPair("cancelar", "cancel");
        AddPair("continuar", "continue");
        AddPair("siguiente", "anterior");
        return words;

        void AddPair(string first, string second)
        {
            if (source.Contains(first, StringComparison.OrdinalIgnoreCase))
            {
                words.Add(first);
            }

            if (source.Contains(second, StringComparison.OrdinalIgnoreCase))
            {
                words.Add(second);
            }
        }
    }

    public static IReadOnlyList<string> RequiredFactualFragments(string source)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        return source
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(static line => line.Trim())
            .Where(static line => line.StartsWith("• ", StringComparison.Ordinal))
            .Select(static line => line[2..].Trim())
            .Where(static line => line.Contains(':'))
            .Take(20)
            .ToArray();
    }

    public static IReadOnlyList<string> RequiredLiteralFacts(string source)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        if (IsStructuredFacts(source))
        {
            return RequiredStructuredLiterals(source);
        }

        var facts = new List<string>();
        const RegexOptions options =
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant
                | RegexOptions.NonBacktracking;

        foreach (Match match in Regex.Matches(
                     source,
                     "[«\"“](?<value>[^»\"”\\r\\n]{1,256})[»\"”]",
                     options))
        {
            Add(match.Groups["value"].Value);
        }

        foreach (Match match in Regex.Matches(
                     source,
                     @"(?:^|[^\p{L}\p{N}_])(?<value>\d+(?:[.,:]\d+)*(?:\s*[%°])?)",
                     options))
        {
            Add(match.Groups["value"].Value);
        }

        Match application = Regex.Match(
            source,
            @"^\s*Listo,\s+(?:abrí|enfoqué)\s+(?<value>[^.!?\r\n]{1,120})[.!?]\s*$",
            options);
        if (application.Success)
        {
            Add(application.Groups["value"].Value);
        }

        foreach (string pattern in new[]
                 {
                     @"\b(?:fecha local es|local date is)\s+(?<value>.+?)(?:\s+(?:y la hora local es|and the local time is)|[.!?\r\n]|$)",
                     @"\b(?:hora local es|local time is)\s+(?<value>[^.!?\r\n]{1,80})",
                 })
        {
            Match match = Regex.Match(source, pattern, options);
            if (match.Success)
            {
                Add(match.Groups["value"].Value);
            }
        }

        // The family-aware Core floors intentionally avoid operation IDs and
        // other internal vocabulary. Their person-facing subject is still a
        // verified fact: require the local model to preserve it instead of
        // accepting a vague "ya lo hice" or "no pude" response.
        Match familyFloor = Regex.Match(
            source,
            @"^\s*(?:Completé y verifiqué|No pude completar)\s+(?<value>[^.!?\r\n]{1,160})[.!?]?\s*$",
            options);
        if (familyFloor.Success)
        {
            Add(familyFloor.Groups["value"].Value);
        }

        return facts
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(32)
            .ToArray();

        void Add(string value)
        {
            string trimmed = value.Trim().TrimEnd('.', ',', ';', ':');
            if (trimmed.Length > 0)
            {
                facts.Add(trimmed);
            }
        }
    }

    private static bool PreservesRequiredFacts(string source, string result)
    {
        IReadOnlyList<string> fragments = RequiredFactualFragments(source);
        if (fragments.Count == 0)
        {
            return true;
        }

        string foldedResult = FoldForPolicy(result);
        foreach (string fragment in fragments)
        {
            int separator = fragment.IndexOf(':');
            string label = FoldForPolicy(fragment[..separator].Trim());
            string value = FoldForPolicy(fragment[(separator + 1)..].Trim());
            if (string.IsNullOrEmpty(label)
                || string.IsNullOrEmpty(value)
                || !foldedResult.Contains(label, StringComparison.Ordinal)
                || !foldedResult.Contains(value, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static bool PreservesRequiredLiteralFacts(string source, string result)
    {
        string foldedResult = FoldForPolicy(result);
        return RequiredLiteralFacts(source).All(fact =>
            foldedResult.Contains(FoldForPolicy(fact), StringComparison.Ordinal));
    }

    private static bool PreservesObservedClock(string source, string result)
    {
        if (!TryDerivedLocalClock(source, out string hhmm))
        {
            return true;
        }

        return ClockAppears(FoldForPolicy(result), hhmm);
    }

    private static bool InventedClock(string source, string result)
    {
        if (TryDerivedLocalClock(source, out _) || ContainsClockPattern(source))
        {
            return false;
        }

        return ContainsClockPattern(result);
    }

    private static bool ContainsClockPattern(string text)
    {
        foreach (Match match in Regex.Matches(
                     text,
                     @"\d{1,2}:\d{2}",
                     RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            int start = match.Index;
            int end = start + match.Length;
            bool leftOk = start == 0 || !char.IsDigit(text[start - 1]);
            bool rightOk = end >= text.Length || !char.IsDigit(text[end]);
            if (leftOk && rightOk)
            {
                return true;
            }
        }

        return false;
    }

    internal static bool TryDerivedLocalClock(string source, out string hhmm)
    {
        hhmm = string.Empty;
        if (!IsStructuredFacts(source) || !TryReadJson(source, out JsonElement root))
        {
            return false;
        }

        if (!TryClockFromObserved(root, out hhmm)
            && root.TryGetProperty("steps", out JsonElement steps)
            && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.GetString() is { Length: > 0 } text
                    && IsStructuredFacts(text)
                    && TryReadJson(text, out JsonElement nested)
                    && TryClockFromObserved(nested, out hhmm))
                {
                    return true;
                }
            }

            return false;
        }

        return !string.IsNullOrEmpty(hhmm);
    }

    private static bool TryClockFromObserved(JsonElement root, out string hhmm)
    {
        hhmm = string.Empty;
        if (!root.TryGetProperty("observed", out JsonElement observed)
            || observed.ValueKind != JsonValueKind.Object
            || !observed.TryGetProperty("utc", out JsonElement utcElement)
            || utcElement.GetString() is not { Length: > 0 } utc
            || !observed.TryGetProperty("localUtcOffsetMinutes", out JsonElement offsetElement)
            || !offsetElement.TryGetInt32(out int offsetMinutes)
            || !DateTimeOffset.TryParse(
                utc,
                CultureInfo.InvariantCulture,
                DateTimeStyles.RoundtripKind,
                out DateTimeOffset utcTime))
        {
            return false;
        }

        DateTimeOffset local = utcTime.ToOffset(TimeSpan.FromMinutes(offsetMinutes));
        hhmm = local.Hour.ToString(CultureInfo.InvariantCulture)
            + ":"
            + local.Minute.ToString("D2", CultureInfo.InvariantCulture);
        return true;
    }

    private static bool ClockAppears(string foldedResult, string hhmm)
    {
        string[] parts = hhmm.Split(':');
        if (parts.Length != 2
            || !int.TryParse(parts[0], CultureInfo.InvariantCulture, out int hour)
            || !int.TryParse(parts[1], CultureInfo.InvariantCulture, out int minute))
        {
            return false;
        }

        string padded = hour.ToString("D2", CultureInfo.InvariantCulture)
            + ":"
            + minute.ToString("D2", CultureInfo.InvariantCulture);
        string compact = hour.ToString(CultureInfo.InvariantCulture)
            + ":"
            + minute.ToString("D2", CultureInfo.InvariantCulture);
        return ContainsClockToken(foldedResult, padded)
            || ContainsClockToken(foldedResult, compact);
    }

    private static bool ContainsClockToken(string folded, string form)
    {
        int start = 0;
        while (true)
        {
            int index = folded.IndexOf(form, start, StringComparison.Ordinal);
            if (index < 0)
            {
                return false;
            }

            bool leftOk = index == 0 || !char.IsDigit(folded[index - 1]);
            int end = index + form.Length;
            bool rightOk = end >= folded.Length || !char.IsDigit(folded[end]);
            if (leftOk && rightOk)
            {
                return true;
            }

            start = index + 1;
        }
    }

    private static bool PreservesBaxyFirstPerson(string source, string result)
    {
        if (IsStructuredFacts(source))
        {
            return true;
        }

        string sourceFolded = FoldForPolicy(source);
        string resultFolded = FoldForPolicy(result);
        foreach ((string sourcePattern, string resultPattern) in FirstPersonActionPatterns)
        {
            if (Regex.IsMatch(
                    sourceFolded,
                    sourcePattern,
                    RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
                && !Regex.IsMatch(
                    resultFolded,
                    resultPattern,
                    RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
            {
                return false;
            }
        }

        return true;
    }

    private static bool AddsGenericFollowUp(string result)
    {
        string folded = FoldForPolicy(result);
        return Regex.IsMatch(
            folded,
            @"\b(?:que quieres hacer ahora|que deseas hacer ahora|que necesitas ahora|necesitas algo mas|algo mas)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool StartsWithRequestImperative(string result)
    {
        string folded = FoldForPolicy(result);
        return Regex.IsMatch(
            folded,
            @"^\s*(?:(?:list|show|tell|open|create|set|mute|close|delete|send)\b|(?:lista|muestra)\s+(?:el|la|los|las|un|una)\b|(?:dime|abre|crea|pon|silencia|cierra|elimina|envia)\b)",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool ReversesSuccessfulResult(string source, string result)
    {
        if (LooksLikeFailure(source))
        {
            return false;
        }

        string resultFolded = FoldForPolicy(result);
        return resultFolded.Contains("no pude", StringComparison.Ordinal)
            || resultFolded.Contains("no puedo", StringComparison.Ordinal)
            || resultFolded.Contains("no se pudo", StringComparison.Ordinal);
    }

    private static bool ReversesFailedResult(string source, string result)
    {
        return LooksLikeFailure(source) && !LooksLikeFailure(result);
    }

    private static string[] RequiredStructuredLiterals(string source)
    {
        if (!TryReadJson(source, out JsonElement root))
        {
            return [];
        }

        var facts = new List<string>();
        if (root.TryGetProperty("steps", out JsonElement steps)
            && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.GetString() is not { Length: > 0 } text)
                {
                    continue;
                }

                if (IsStructuredFacts(text)
                    && TryReadJson(text, out JsonElement nested))
                {
                    CollectStructuredLiterals(nested, facts);
                    continue;
                }

                facts.Add(text);
            }
        }

        CollectStructuredLiterals(root, facts);
        return facts.Take(20).ToArray();
    }

    private static void CollectStructuredLiterals(JsonElement root, List<string> facts)
    {
        foreach (string key in new[] { "reason", "title" })
        {
            if (root.TryGetProperty(key, out JsonElement value)
                && value.GetString() is { Length: > 0 } text)
            {
                facts.Add(text);
            }
        }
    }

    private static bool TryReadJson(string source, out JsonElement root)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            root = document.RootElement.Clone();
            return root.ValueKind == JsonValueKind.Object;
        }
        catch (JsonException)
        {
            root = default;
            return false;
        }
    }

    private static string FoldForPolicy(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char character in value.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character)
                != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return builder.ToString().Normalize(NormalizationForm.FormC);
    }

    private static readonly (string Source, string Result)[] FirstPersonActionPatterns =
    [
        (@"\babri\b", @"\b(?:abri|he abierto)\b"),
        (@"\benfoque\b", @"\b(?:enfoque|he enfocado)\b"),
        (@"\bcerre\b", @"\b(?:cerre|he cerrado)\b"),
        (@"\bejecute\b", @"\b(?:ejecute|he ejecutado)\b"),
        (@"\binicie\b", @"\b(?:inicie|he iniciado)\b"),
        (@"\bhice\b", @"\b(?:hice|he hecho)\b"),
        (@"\bpuse\b", @"\b(?:puse|he puesto)\b"),
        (@"\bajuste\b", @"\b(?:ajuste|he ajustado)\b"),
        (@"\bcontrole\b", @"\b(?:controle|he controlado)\b"),
        (@"\bcopie\b", @"\b(?:copie|he copiado)\b"),
        (@"\bpegue\b", @"\b(?:pegue|he pegado)\b"),
        (@"\bresolvi\b", @"\b(?:resolvi|he resuelto)\b"),
        (@"\bcambie\b", @"\b(?:cambie|he cambiado)\b"),
        (@"\bactive\b", @"\b(?:active|he activado)\b"),
        (@"\bdesactive\b", @"\b(?:desactive|he desactivado)\b"),
        (@"\bseleccione\b", @"\b(?:seleccione|he seleccionado)\b"),
        (@"\benvie\b", @"\b(?:envie|he enviado)\b"),
        (@"\bconecte\b", @"\b(?:conecte|he conectado)\b"),
        (@"\bforce\b", @"\b(?:force|he forzado)\b"),
        (@"\badelante\b", @"\b(?:adelante|he adelantado)\b"),
        (@"\bretrocedi\b", @"\b(?:retrocedi|he retrocedido)\b"),
        (@"\bsilencie\b", @"\b(?:silencie|he silenciado)\b"),
        (@"\breactive\b", @"\b(?:reactive|he reactivado)\b"),
        (@"\bpresione\b", @"\b(?:presione|he presionado)\b"),
        (@"\bescribi\b", @"\b(?:escribi|he escrito)\b"),
        (@"\bguarde\b", @"\b(?:guarde|he guardado)\b"),
        (@"\bcree\b", @"\b(?:cree|he creado)\b"),
        (@"\belimine\b", @"\b(?:elimine|he eliminado)\b"),
        (@"\bverifique\b", @"\b(?:verifique|he verificado)\b"),
    ];

    private static bool PreservesChoicePair(
        string source,
        string result,
        string first,
        string second)
    {
        bool sourceHasPair = source.Contains(first, StringComparison.OrdinalIgnoreCase)
            && source.Contains(second, StringComparison.OrdinalIgnoreCase);
        return !sourceHasPair
            || result.Contains(first, StringComparison.OrdinalIgnoreCase)
                && result.Contains(second, StringComparison.OrdinalIgnoreCase);
    }

    private static bool PreservesRequiredConfirmationChoices(string source, string result)
    {
        if (!IsStructuredFacts(source)
            || !TryReadJson(source, out JsonElement root)
            || !root.TryGetProperty("choices", out JsonElement choices)
            || choices.ValueKind != JsonValueKind.Array)
        {
            return PreservesChoicePair(source, result, "confirm", "cancel")
                && PreservesChoicePair(source, result, "continuar", "cancel")
                && PreservesChoicePair(source, result, "siguiente", "anterior");
        }

        string foldedResult = FoldForPolicy(result);
        return choices
            .EnumerateArray()
            .Select(static item => item.GetString()?.Trim())
            .Where(static item => !string.IsNullOrWhiteSpace(item))
            .Select(static item => ConfirmationChoiceKey(item!))
            .Distinct(StringComparer.Ordinal)
            .All(choice => ConfirmationChoiceIsPresent(choice, foldedResult));
    }

    private static string ConfirmationChoiceKey(string choice) =>
        FoldForPolicy(choice) switch
        {
            "confirmar" or "confirm" => "confirm",
            "cancelar" or "cancel" => "cancel",
            "continuar" or "continue" => "continue",
            "siguiente" or "next" => "next",
            "anterior" or "previous" => "previous",
            "reintentar" or "retry" => "retry",
            string other => other,
        };

    private static bool ConfirmationChoiceIsPresent(string choice, string foldedResult) =>
        choice switch
        {
            "confirm" => foldedResult.Contains("confirm", StringComparison.Ordinal),
            "cancel" => foldedResult.Contains("cancel", StringComparison.Ordinal),
            "continue" => foldedResult.Contains("continuar", StringComparison.Ordinal)
                || foldedResult.Contains("continue", StringComparison.Ordinal),
            "next" => foldedResult.Contains("siguiente", StringComparison.Ordinal)
                || foldedResult.Contains("next", StringComparison.Ordinal),
            "previous" => foldedResult.Contains("anterior", StringComparison.Ordinal)
                || foldedResult.Contains("previous", StringComparison.Ordinal),
            "retry" => foldedResult.Contains("reintentar", StringComparison.Ordinal)
                || foldedResult.Contains("retry", StringComparison.Ordinal),
            _ => foldedResult.Contains(choice, StringComparison.Ordinal),
        };
}
