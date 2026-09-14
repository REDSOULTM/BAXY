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
    Conversation,
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

    public static UserMessageEvent Conversation { get; } = new(
        UserMessageEventType.Conversation,
        "conversation");

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
        if (NaturalSystemStatusRequestParser.IsCurrentTimeRequest(userText)
            || UserMessagePolicy.ShouldNotResumePriorObjective(userText))
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
            "clarify" => decision.StartsNewObjective
                && decision.Operation is null
                && decision.EffectOperations.Count == 0
                && decision.IntentOperations.Count > 0,
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
        "qwen",
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
        // BRIGHT1287/1289 H0430: «…según la lectura de WMI» leaked the
        // provider's mechanism into the confirmed final.
        "wmi",
    ];

    internal static IReadOnlyList<string> ForbiddenResponseTerms => ForbiddenTerms;

    internal static bool IsStructuredFacts(string source)
    {
        ReadOnlySpan<char> trimmed = source.AsSpan().Trim();
        return trimmed.Length >= 2 && trimmed[0] == '{' && trimmed[^1] == '}';
    }

    internal static bool HasRequiredInput(UserMessageDraft draft) =>
        draft.Intent == "clarification"
        && TryReadJson(draft.Source, out JsonElement root)
        && root.ValueKind == JsonValueKind.Object
        && root.TryGetProperty("kind", out JsonElement kind)
        && kind.ValueKind == JsonValueKind.String && kind.GetString() == "clarification"
        && root.TryGetProperty("polarity", out JsonElement polarity)
        && polarity.ValueKind == JsonValueKind.String && polarity.GetString() == "pending"
        && root.TryGetProperty("missingValue", out JsonElement missing)
        && missing.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(missing.GetString());

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

    public static bool IsSafe(string text) => LeakedInternalTerm(text, null) is null;

    /// <summary>
    /// El término de jerga que se coló en el texto, o null si no hay ninguno.
    /// Cuando la persona pregunta por esa misma palabra —«explícame qué es un
    /// router»— nombrarla es responder, no filtrar el interior del producto.
    /// </summary>
    internal static string? LeakedInternalTerm(
        string text, string? userText, string? priorUserText = null)
    {
        if (string.IsNullOrWhiteSpace(text) || text.Length > 4_096)
        {
            return "empty_or_too_long";
        }

        foreach (string term in ForbiddenTerms)
        {
            if (!text.Contains(term, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (userText?.Contains(term, StringComparison.OrdinalIgnoreCase) is true
                || priorUserText?.Contains(term, StringComparison.OrdinalIgnoreCase) is true)
            {
                continue;
            }

            return term;
        }

        return null;
    }

    public static bool IsSafe(string text, UserMessageDraft draft)
    {
        return ModelResponseRejectionReason(text, draft) is null;
    }

    public static string? ModelResponseRejectionReason(
        string? modelText,
        UserMessageDraft draft,
        string? userText = null,
        string? priorUserText = null)
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
        if (modelText.Length > 4_096)
        {
            return "unsafe_language";
        }
        // «Un router enruta el tráfico» sólo es jerga si nadie preguntó por un
        // router: sin el pedido, explicar uno era imposible.
        string vocabularyText = ObservedResponseLiterals.WithoutObservedNames(modelText, draft.Source);
        if (LeakedInternalTerm(vocabularyText, userText, priorUserText) is not null)
        {
            return "unsafe_language";
        }

        if (IsPunctuationOnly(modelText) || IsTooThin(modelText))
        {
            return "no_response";
        }

        if (LooksLikeMachineSlotAsk(FoldForPolicy(modelText))
            || LooksLikeRestatingDefinitionAsk(FoldForPolicy(modelText))
            || HasRepeatedWord(FoldForPolicy(modelText))
            || ContainsPersonMetadiscourse(FoldForPolicy(modelText))
            || ContainsInternalCode(vocabularyText, string.Concat(userText, " ", priorUserText))
            || FoldForPolicy(modelText).Contains("hecho ya ocurrido", StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains("hola saludo", StringComparison.Ordinal))
        {
            return "internal_code";
        }

        if (HasBrokenModalGerund(modelText))
        {
            return "internal_code";
        }

        if (ClaimsFirstPersonConnectivity(FoldForPolicy(modelText)))
        {
            return "wrong_actor";
        }

        if (draft.Intent == "clarification"
            && (IsGreetingOnly(modelText) || ClaimsUnverifiedSuccess(modelText)))
        {
            return "internal_code";
        }

        if (HasRequiredInput(draft)
            && !modelText.Contains('?', StringComparison.Ordinal)
            && !modelText.Contains('¿', StringComparison.Ordinal))
        {
            return "clarification_not_a_question";
        }

        if (ContainsStutteredToken(modelText))
        {
            return "internal_code";
        }
        if (FoldForPolicy(modelText).Contains(
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
            || FoldForPolicy(modelText).Contains(
                "entender la solicitud",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "borrador anterior",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "previous draft",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "soy by",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "</think>",
                StringComparison.Ordinal)
            || FoldForPolicy(modelText).Contains(
                "<think>",
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
            // «qué día es hoy» asks for the calendar date, like «fecha»/«date».
            // The mind projects only the date for it (llm._requests_calendar_date);
            // reading it as a clock request here demanded the hour in the draft and
            // rejected six correct dates until the diagnostic code was published
            // (CLOCK1157/000..002).
            bool dateRequested = Regex.IsMatch(userText ?? string.Empty,
                @"\b(?:fecha|date|d[ií]a|day)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
            bool clockRequested = !dateRequested || Regex.IsMatch(userText ?? string.Empty,
                @"\b(?:hora|time)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
            // CLOCK1333 «cuánto falta para las 3 de la tarde»: the answer is the
            // remaining time computed by the mind («Faltan 13 horas y 43 minutos
            // para las 3 de la tarde»); the observed clock is optional there and
            // the asked time is not an extra invented clock.
            bool countdownRequested = IsCountdownRequest(userText);
            if (clockRequested && !countdownRequested && !PreservesObservedClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (dateRequested && !PreservesObservedDate(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (MissesObservedAudio(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventedClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventedVolume(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventedAppEffectOnClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventsClockPlace(modelText))
            {
                return "missing_literal_fact";
            }
            if (DumpsUnsolicitedInterfaces(string.Empty, modelText))
            {
                return "missing_literal_fact";
            }
            if (!countdownRequested && InventedExtraClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (draft.Intent == "status" && IsBareSuccessOpener(modelText))
            {
                return "missing_literal_fact";
            }
            if (draft.Intent == "status" && IsDanglingNamedSuccess(draft.Source, modelText))
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
        UserMessageDraft draft,
        string? userText = null,
        string? priorUserText = null)
    {
        ArgumentNullException.ThrowIfNull(draft);
        return ModelResponseRejectionReason(modelText, draft, userText, priorUserText) is null
            ? WithDiagnosticCode(modelText!, draft)
            : null;
    }

    /// <summary>
    /// Whether a mind-authored reply can be published as it stands.
    /// <paramref name="mindLanguage"/> is the language the mind reports having
    /// written in; the shell does not read the request's language on its own.
    /// </summary>
    public static bool IsSafeConversationReply(
        string userText,
        string reply,
        string? mindLanguage = null,
        string? priorUserText = null,
        bool clarification = false,
        bool hasRequiredInput = false) =>
        ConversationReplyRejectionReason(userText, reply, mindLanguage, priorUserText, clarification, hasRequiredInput) is null;

    /// <summary>
    /// Por qué no se puede publicar una respuesta de la mente, o null si sí.
    /// Cada término lleva su nombre: sin él, degradar a un mensaje de estado
    /// dejaba el turno sin causa registrada y no se podía distinguir un veto
    /// correcto de uno falso sin volver a lanzar la campaña.
    /// </summary>
    public static string? ConversationReplyRejectionReason(
        string userText,
        string reply,
        string? mindLanguage = null,
        string? priorUserText = null,
        bool clarification = false,
        bool hasRequiredInput = false,
        IReadOnlyList<string>? missingFields = null)
    {
        if (LeakedInternalTerm(reply, userText, priorUserText) is { } leaked)
        {
            return "unsafe_language:" + leaked;
        }

        string said = FoldForPolicy(reply);
        string user = FoldForPolicy(userText);
        (string Reason, bool Failed)[] checks =
        [
            ("clock_request", NaturalSystemStatusRequestParser.IsCurrentTimeRequest(userText)),
            ("clock_reply", NaturalSystemStatusRequestParser.IsCurrentTimeRequest(reply)),
            ("restates_request",
                !IsGreetingRequest(userText) && RestatesTheRequest(userText, reply)),
            ("clock_pattern", ContainsClockPattern(reply)),
            ("internal_code", ContainsInternalCode(reply, string.Concat(userText, " ", priorUserText))),
            ("unverified_success", ClaimsUnverifiedSuccess(reply)),
            ("invented_token", ContainsMeasuredInventedToken(reply)),
            ("stuttered_token", ContainsStutteredToken(reply)),
            ("unsolicited_catalog",
                !IsSelfDescriptionQuestion(userText)
                && ProposesUnsolicitedCatalogAction(userText, reply, clarification)),
            // FILES1439 «How many files are in the current directory?»: the mind
            // declared the folder as the missing field; asking which folder is
            // the clarification itself, not a machine slot ask.
            ("machine_slot_ask", LooksLikeMachineSlotAsk(said) && !AsksForDeclaredFolder(said, missingFields)),
            ("punctuation_only", IsPunctuationOnly(reply)),
            ("too_thin", IsTooThin(reply)),
            ("asks_to_invent_clock", AsksToInventClock(said)),
            ("echoes_request",
                !IsGreetingRequest(userText) && EchoesRequestAsQuestion(userText, reply)),
            ("greets_out_of_world", GreetsOutOfWorldTarget(said)),
            ("unverified_connectivity", ClaimsUnverifiedConnectivity(said)),
            ("looks_like_failure",
                LooksLikeFailure(reply)
                && !LooksLikeKnowledgeQuestion(user)
                && ConversationFallbackIntent(userText) != "out_of_catalog"),
            ("greeting_not_returned",
                IsGreetingRequest(userText)
                && !IsGreetingOnly(reply)
                && !StartsWithGreeting(reply)),
            ("wrong_language",
                string.Equals(mindLanguage, "en", StringComparison.Ordinal)
                && ContainsSpanishGreeting(reply)),
            ("connectivity_greeting",
                IsConnectivityStatusRequest(userText)
                && (IsGreetingOnly(reply) || StartsWithGreeting(reply))),
            ("ambiguous_without_question",
                LooksLikeAmbiguousAction(user)
                && !reply.Contains('?', StringComparison.Ordinal)
                && !reply.Contains('¿', StringComparison.Ordinal)),
            ("unusable_answer",
                said.Contains("usar esa respuesta", StringComparison.Ordinal)
                || said.Contains("unusable answer", StringComparison.Ordinal)),
            ("out_of_world_question",
                LooksLikeOutOfWorldRequest(user)
                && (reply.Contains('?', StringComparison.Ordinal)
                    || reply.Contains('¿', StringComparison.Ordinal))),
            ("restates_definition_ask", LooksLikeRestatingDefinitionAsk(said)),
            ("definition_as_action", RestatesDefinitionAsAction(userText, reply)),
            ("broken_modal_gerund", HasBrokenModalGerund(reply)),
            ("invents_out_of_world_object", InventsOutOfWorldObject(userText, reply)),
            ("invented_utc_offset", ContainsInventedUtcOffset(userText, reply)),
            // Si el pedido saluda («hola, ¿qué puedes hacer?»), devolver el
            // saludo delante de la respuesta no es el defecto; quedarse sólo
            // en el saludo sí lo es.
            ("knowledge_not_answered",
                !hasRequiredInput && LooksLikeKnowledgeQuestion(user)
                && (IsGreetingOnly(reply)
                    || (StartsWithGreeting(reply) && GreetingRemainder(userText) is null)
                    || reply.Contains('?', StringComparison.Ordinal)
                    || reply.Contains('¿', StringComparison.Ordinal))),
            ("unsolicited_legal_frame", InventsUnsolicitedLegalFrame(userText, reply)),
            ("broken_word", reply.Contains("teá", StringComparison.Ordinal)),
            ("identity_not_answered",
                !hasRequiredInput && IsIdentityQuestion(userText)
                && (IsGreetingOnly(reply)
                    || reply.Contains('?', StringComparison.Ordinal)
                    || reply.Contains('¿', StringComparison.Ordinal)
                    || !said.Contains("baxy", StringComparison.Ordinal))),
            ("repeated_word", HasRepeatedWord(said)),
            ("invented_time_zone", InventsNamedTimeZone(userText, reply)),
            ("invented_clock_place", InventsClockPlace(reply)),
            ("dumps_interfaces", DumpsUnsolicitedInterfaces(userText, reply)),
            ("missing_translation", MissesRequestedTranslation(userText, reply)),
            ("leaks_prior_topic", LeaksPriorKnowledgeTopic(userText, reply)),
            ("inverts_negative_constraint", InvertsNegativeConstraint(userText, reply)),
            ("unverified_ambiguous_effect",
                ClaimsUnverifiedAmbiguousEffect(userText, reply)),
            ("person_metadiscourse_literal",
                said.Contains("user wants", StringComparison.Ordinal)
                || said.Contains("hola saludo", StringComparison.Ordinal)
                || said.Contains("cannot provide", StringComparison.Ordinal)
                || said.Contains("never stop helping", StringComparison.Ordinal)
                || said.Contains("no rechazo nada", StringComparison.Ordinal)
                || said.Contains("i refuse nothing", StringComparison.Ordinal)),
            ("inverts_refuse_question", InvertsRefuseQuestion(userText, reply)),
            ("invents_hardware_spec", InventsUnsolicitedHardwareSpec(userText, reply)),
            ("misses_refuse_answer", MissesRefuseAnswer(userText, reply)),
            ("names_non_pc_refuse_act", NamesNonPcRefuseAct(userText, reply)),
            ("knowledge_time_zone_denial",
                LooksLikeKnowledgeQuestion(user)
                && said.Contains("no hay zonas horarias", StringComparison.Ordinal)),
            ("knowledge_offer_instead_of_answer",
                LooksLikeKnowledgeQuestion(user)
                && ContainsAny(
                    said,
                    ["i'm happy to help", "im happy to help", "i am happy to help",
                        "just let me know what you need"])),
            ("person_metadiscourse", ContainsPersonMetadiscourse(said)),
        ];

        foreach ((string reason, bool failed) in checks)
        {
            if (failed)
            {
                return reason;
            }
        }

        return null;
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
        "enviaritar",
        "puedober",
        "fabric",
    ];

    /// <summary>
    /// A countdown to a clock time («cuánto falta para las 3 de la tarde»,
    /// «how long until 6 pm»): the mind reads the clock and computes the rest.
    /// </summary>
    internal static bool IsCountdownRequest(string? text) =>
        Regex.IsMatch(
            text ?? string.Empty,
            @"^\s*[¿¡]?\s*(?:cu[aá]nto\s+(?:tiempo\s+)?(?:falta|queda|resta)\s+(?:para|hasta)\b|"
            + @"how\s+(?:long|much\s+time)\s+(?:until|till|before|to|is\s+left)\b)",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

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
            or "are you connected"
            or "are you online"
            or "estoy conectado"
            or "estas conectado"
            or "estas online"
            or "is there internet")
            || folded.EndsWith("conectado a internet", StringComparison.Ordinal)
            // Preguntar por la conexión de este equipo con otras palabras
            // seguía siendo una conversación sin hechos, y el modelo se
            // inventaba la respuesta en vez de leer network.status.
            || ContainsAny(
                folded,
                ["tiene conexion", "hay conexion", "tenemos conexion",
                    "hay wifi", "tiene internet", "tiene red",
                    "has connection", "have connection", "have internet",
                    "has internet", "is this pc online",
                    "is the pc online", "is it online"]);
    }

    internal static string ConversationFallbackIntent(string userText)
    {
        string user = FoldForPolicy(userText);
        if (LooksLikeAmbiguousAction(user))
        {
            return "clarification";
        }

        if (IsConnectivityStatusRequest(userText)
            || NaturalSystemStatusRequestParser.IsCurrentTimeRequest(userText))
        {
            return "conversation";
        }

        if (LooksLikeOutOfWorldRequest(user))
        {
            return "out_of_catalog";
        }

        if (LooksLikeContinueConstraint(user))
        {
            return "conversation";
        }

        if (LooksLikeNegativeAction(user))
        {
            return "conversation";
        }

        if (LooksLikeKnowledgeQuestion(user)
            || IsIdentityQuestion(userText)
            || IsSelfDescriptionQuestion(userText)
            || IsTranslationRequest(userText)
            || IsCapabilityQuestion(userText))
        {
            return "conversation";
        }

        // Sólo un saludo se contesta con un saludo. Cuando «welcome» era el
        // valor por defecto, cualquier pedido no reconocido y cualquier valor
        // de hueco («mañana a las 9») acababa saludando en vez de responder.
        // «unknown» no reclama ninguna ruta: conserva el encaminamiento de un
        // efecto y evita que la degradación salude sin motivo.
        return IsGreetingRequest(userText) ? "welcome" : "unknown";
    }

    internal static bool IsIdentityQuestion(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        string folded = FoldForPolicy(text).Trim().Trim('?', '.', '!', '¿', '¡', ' ');
        return folded is "who are you"
            or "quien eres"
            or "quien eres tu"
            or "quien eres, en una linea"
            or "who are you, in one line"
            or "who is speaking"
            or "quien habla"
            or "quien esta hablando"
            or "who is speaking?"
            || folded.StartsWith("who are you", StringComparison.Ordinal)
            || folded.StartsWith("quien eres", StringComparison.Ordinal)
            || folded.Contains("who is speaking", StringComparison.Ordinal)
            || folded.Contains("quien habla", StringComparison.Ordinal)
            || folded.Contains("introduce yourself", StringComparison.Ordinal)
            || folded.Contains("presentate", StringComparison.Ordinal)
            || folded.Contains("describe yourself", StringComparison.Ordinal)
            || folded.Contains("describete", StringComparison.Ordinal);
    }

    internal static bool IsCapabilityQuestion(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        string user = FoldForPolicy(text);
        if (LooksLikeContinueConstraint(user))
        {
            return false;
        }

        return LooksLikeKnowledgeQuestion(user)
            || IsTranslationRequest(text);
    }

    internal static bool IsSelfDescriptionQuestion(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return ContainsAny(
            FoldForPolicy(text),
            UserMessagePhrases.SelfDescriptionAsks);
    }

    internal static bool IsTranslationRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return ContainsAny(FoldForPolicy(text), ["traduce", "translate "]);
    }

    internal static bool IsGreetingRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        if (IsSelfDescriptionQuestion(text)
            || IsIdentityQuestion(text)
            || LooksLikeKnowledgeQuestion(FoldForPolicy(text)))
        {
            return false;
        }

        return IsGreetingOnly(text);
    }

    internal static bool ShouldComposeAsConversationNotError(string userText)
    {
        if (string.IsNullOrWhiteSpace(userText))
        {
            return false;
        }

        if (IsGreetingRequest(userText)
            || IsIdentityQuestion(userText)
            || IsCapabilityQuestion(userText)
            || IsTranslationRequest(userText))
        {
            return true;
        }

        string intent = ConversationFallbackIntent(userText);
        return intent is "conversation" or "clarification" or "out_of_catalog";
    }

    internal static bool IsContinueConstraintRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return LooksLikeContinueConstraint(FoldForPolicy(text));
    }

    private static bool LooksLikeContinueConstraint(string user) =>
        ContainsAny(
            user,
            ["keep going", "keep chatting", "sigue ", "continua ", "continue "])
        && ContainsAny(
            user,
            ["without apps", "without opening", "sin abrir", "sin lanzar",
                "without launching"]);

    private static bool ContainsSpanishGreeting(string reply)
    {
        string folded = FoldForPolicy(reply);
        return ContainsAny(
            folded,
            ["hola", "buenos", "buenas", "que tal", "qué tal"]);
    }

    private static bool LooksLikeNegativeAction(string user) =>
        ContainsAny(
            user,
            ["no abras", "don't open", "dont open", "don't launch", "no lances",
                "sin lanzar",
                "if it didn't happen", "si no lo viste", "si no lo confirmas"]);

    internal static bool ShouldNotResumePriorObjective(string userText)
    {
        if (string.IsNullOrWhiteSpace(userText))
        {
            return false;
        }

        string user = FoldForPolicy(userText);
        return IsConnectivityStatusRequest(userText)
            || LooksLikeAmbiguousAction(user)
            || LooksLikeOutOfWorldRequest(user)
            || LooksLikeKnowledgeQuestion(user)
            || IsTranslationRequest(userText)
            || IsGreetingRequest(userText);
    }

    internal static bool ProposesUnsolicitedCatalogAction(
        string userText, string reply, bool clarification = false)
    {
        string user = FoldForPolicy(userText);
        string said = CatalogProposalScope(FoldForPolicy(reply));
        if ((!CatalogFamilies.Any(family => ContainsAny(said, family))
                && !ContainsCatalogActionVerb(said))
            || said.Contains("que accion", StringComparison.Ordinal)
            || said.Contains("what action", StringComparison.Ordinal)
            || said.Contains("que necesitas", StringComparison.Ordinal)
            || said.Contains("what do you need", StringComparison.Ordinal)
            || said.Contains("en que puedo ayudarte", StringComparison.Ordinal))
        {
            return false;
        }

        // A classified clarification already belongs to the requested action.
        // Still reject every family absent from that request below.
        if (!clarification && !ContainsCatalogActionVerb(user))
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
        ["wifi", "wi-fi", "wlan", "inalambr", "estado de la red", "network status"],
        ["estado del sistema", "system status"],
        ["aplicacion", "application", "programa", "program"],
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

    private static string CatalogProposalScope(string folded)
    {
        // A conversational offer is not necessarily an operation. Inspect its
        // object, without borrowing catalog nouns from the preceding answer.
        string proposals = string.Join(" ", Regex.Matches(folded,
                @"\b(?:quieres que|want me to|do you want me(?: to)?)\b[^.!?;\r\n]*",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            .Cast<Match>().Select(static match => match.Value));
        if (proposals.Length > 0)
        {
            return proposals;
        }

        return folded.Contains("metadatos de una rutina", StringComparison.Ordinal)
            || folded.Contains("salida predeterminada", StringComparison.Ordinal)
            ? folded
            : string.Empty;
    }

    // A noun in an explanation is not a request for a parameter. C03's
    // encryption answer mentioned a recipient and was needlessly rewritten.
    // Preserve the slot guard only for an actual question or direct request.
    private static bool AsksForDeclaredFolder(string folded, IReadOnlyList<string>? missingFields) =>
        missingFields is not null
        && missingFields.Contains("folder")
        && Regex.IsMatch(folded, @"\b(?:carpeta|directorio|folder|directory)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static bool LooksLikeMachineSlotAsk(string folded) =>
        (folded.Contains('?', StringComparison.Ordinal)
            || folded.Contains('¿', StringComparison.Ordinal)
            || Regex.IsMatch(folded,
                @"^(?:(?:por favor|please)\s+)?(?:dime|indica|especifica|proporciona|aclara|tell|name|specify|provide|clarify)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        && (folded.Contains("nombre de la aplicacion", StringComparison.Ordinal)
        || folded.Contains("name of the application", StringComparison.Ordinal)
        || folded.Contains("pc network name", StringComparison.Ordinal)
        || folded.Contains("network name", StringComparison.Ordinal)
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
        || folded.Contains("deseas abrazar", StringComparison.Ordinal)
        || folded.Contains("destinatario", StringComparison.Ordinal)
        || folded.Contains("recipient", StringComparison.Ordinal)
        || folded.Contains("nombre del destinatario", StringComparison.Ordinal)
        || folded.Contains("name of the recipient", StringComparison.Ordinal)
        || folded.Contains("el objeto que", StringComparison.Ordinal)
        || folded.Contains("the object that", StringComparison.Ordinal)
        || folded.Contains("te pide cierra", StringComparison.Ordinal)
        || folded.Contains("te pide abre", StringComparison.Ordinal)
        || folded.Contains("nombre de proceso", StringComparison.Ordinal)
        || folded.Contains("process name", StringComparison.Ordinal)
        || folded.Contains("need clarification", StringComparison.Ordinal)
        || folded.Contains("clarification on", StringComparison.Ordinal)
        || folded.Contains("nombre del huso", StringComparison.Ordinal)
        || folded.Contains("podria aclararte", StringComparison.Ordinal)
        || folded.Contains("tipo de informacion", StringComparison.Ordinal)
        || folded.Contains("tipo de aplicacion", StringComparison.Ordinal)
        || folded.Contains("aspecto que deseas", StringComparison.Ordinal)
        || folded.Contains("tema que necesitas", StringComparison.Ordinal)
        || folded.Contains("tema principal", StringComparison.Ordinal)
        || folded.Contains("quien te pregunta", StringComparison.Ordinal)
        || folded.Contains("proposito de", StringComparison.Ordinal));

    private static bool LooksLikeAmbiguousAction(string user) =>
        ContainsAny(
            user,
            ["abreme eso", "abre eso", "cierra aquello", "open that", "close that",
                "hazlo", "do it", "do that", "haz eso", "open it", "close it"]);

    private static bool LooksLikeKnowledgeQuestion(string user) =>
        ContainsAny(user, UserMessagePhrases.KnowledgeAsks);

    /// <summary>
    /// Greeting heads recognized on both sides of the boundary. The Python
    /// owner (`baxy_mind.request_reading`) keeps the same list, and
    /// `tests/data/request_reading_cases.json` pins the two together.
    /// </summary>
    private static readonly string[] GreetingHeads =
    [
        "buenos dias", "buenas tardes", "buenas noches", "buenas", "buenos",
        "hola", "good morning", "good afternoon", "good evening", "good night",
        "hi there", "hello", "hey", "hi",
    ];

    /// <summary>Vocatives that accompany a greeting without adding a request.</summary>
    private static readonly string[] GreetingFillers =
    [
        "a todos", "again", "amigo", "baxy", "compa", "de nuevo", "otra vez",
        "there", "tio",
    ];

    private const string GreetingTrim = " .,!?¿¡";

    /// <summary>
    /// The text left after a leading greeting and its vocatives, or null when
    /// the text does not greet. An empty result means the greeting is the whole
    /// text. The 28-character heuristic this replaces let «hey, close Paint»
    /// pass as a greeting and dropped the request.
    /// </summary>
    internal static string? GreetingRemainder(string text)
    {
        string folded = FoldForPolicy(text ?? string.Empty).Trim();
        folded = string.Join(' ', folded.Split(' ', StringSplitOptions.RemoveEmptyEntries));
        string bare = folded.Trim(GreetingTrim.ToCharArray());
        if (UserMessagePhrases.GreetingAsks.Contains(bare, StringComparer.Ordinal))
        {
            return string.Empty;
        }

        string rest = bare;
        string? head = MatchGreetingHead(rest);
        if (head is null)
        {
            return null;
        }

        // «Hola, buenas» encadena dos saludos; sigue siendo sólo un saludo.
        while (head is not null)
        {
            rest = rest[head.Length..].TrimStart(" ,;:.-".ToCharArray());
            bool trimmed = true;
            while (trimmed && rest.Length > 0)
            {
                trimmed = false;
                foreach (string filler in GreetingFillers)
                {
                    if (string.Equals(
                            rest.Trim(GreetingTrim.ToCharArray()),
                            filler,
                            StringComparison.Ordinal))
                    {
                        return string.Empty;
                    }

                    if (rest.StartsWith(filler + " ", StringComparison.Ordinal))
                    {
                        rest = rest[(filler.Length + 1)..]
                            .TrimStart(" ,;:.-".ToCharArray());
                        trimmed = true;
                        break;
                    }
                }
            }

            rest = rest.Trim(GreetingTrim.ToCharArray());
            head = MatchGreetingHead(rest);
        }

        return rest;
    }

    private static string? MatchGreetingHead(string bare) =>
        GreetingHeads.FirstOrDefault(candidate =>
            bare.StartsWith(candidate, StringComparison.Ordinal)
            && (bare.Length == candidate.Length
                || !char.IsAsciiLetter(bare[candidate.Length])));

    private static bool IsGreetingOnly(string reply)
    {
        string folded = FoldForPolicy(reply).Trim().Trim('.', '!', '?', '¿', '¡', ' ');
        // Una presentación completa sigue siendo un saludo aceptable.
        if (folded.StartsWith("hola, baxy", StringComparison.Ordinal)
            || folded.StartsWith("hi, i'm baxy", StringComparison.Ordinal)
            || folded.StartsWith("hi, im baxy", StringComparison.Ordinal))
        {
            return true;
        }

        return GreetingRemainder(reply) is { Length: 0 };
    }

    private static bool StartsWithGreeting(string reply) => GreetingRemainder(reply) is not null;

    private static bool HasRepeatedWord(string folded)
    {
        Match? previous = null;
        foreach (Match word in Regex.Matches(
            folded,
            @"[\p{L}\p{N}]+",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            // Quotes and sentence punctuation separate meaningful uses, such
            // as la ventana "Ventana de trabajo". Only whitespace-separated
            // duplicate words are evidence of a stutter.
            if (word.Length >= 3
                && previous is not null
                && string.Equals(word.Value, previous.Value, StringComparison.Ordinal)
                && string.IsNullOrWhiteSpace(folded[(previous.Index + previous.Length)..word.Index]))
            {
                return true;
            }

            previous = word;
        }

        return false;
    }

    private static bool InventsNamedTimeZone(string userText, string reply)
    {
        if (!LooksLikeKnowledgeQuestion(FoldForPolicy(userText)))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        if (ContainsAny(said, ["central european", "pacific time", "eastern time"]))
        {
            return true;
        }

        // " est" used to match Spanish "este" ("en este equipo").
        return Regex.IsMatch(
            said,
            @"\b(?:cet|pst|est)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool LooksLikeRestatingDefinitionAsk(string folded) =>
        folded.Contains("significa exactamente", StringComparison.Ordinal)
        || folded.Contains("que significa", StringComparison.Ordinal)
        || folded.Contains("en este contexto", StringComparison.Ordinal)
        || folded.Contains("in this context", StringComparison.Ordinal)
        || (folded.Contains("what does", StringComparison.Ordinal)
            && folded.Contains("mean", StringComparison.Ordinal))
        || folded.Contains("definido, una frase", StringComparison.Ordinal)
        || folded.Contains("definido una frase", StringComparison.Ordinal)
        || folded.Contains("defined, a sentence", StringComparison.Ordinal)
        || folded.Contains("defined a sentence", StringComparison.Ordinal)
        || folded.Contains("defino la zona", StringComparison.Ordinal)
        || folded.Contains("defino utc", StringComparison.Ordinal)
        || folded.Contains("i define utc", StringComparison.Ordinal)
        || folded.Contains("i define the time zone", StringComparison.Ordinal);

    private static bool RestatesDefinitionAsAction(string userText, string reply)
    {
        if (!LooksLikeKnowledgeQuestion(FoldForPolicy(userText)))
        {
            return false;
        }

        return Regex.IsMatch(
            FoldForPolicy(reply),
            @"^\s*(?:configur[oe]|defino|pongo|ajusto|i (?:set|configure|define|adjust))\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool HasBrokenModalGerund(string reply) =>
        Regex.IsMatch(
            FoldForPolicy(reply),
            @"\b(?:cannot|can't|can not)\s+[a-z]+ing\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    /// <summary>
    /// Actos del mundo físico que el catálogo no sirve: mandar algo por correo
    /// o reservar una plaza. Se leen por lo que se pide, no por el destino: la
    /// lista de planetas dejaba pasar «send a parcel to Rhea».
    /// </summary>
    private static readonly (string Verb, string[] Objects)[] WorldActions =
    [
        (
            "post",
            ["letter", "parcel", "package", "postcard", "mail"]
        ),
        (
            "send",
            ["letter", "parcel", "package", "postcard", "flowers", "gift"]
        ),
        ("mail", ["letter", "parcel", "package", "postcard"]),
        ("deliver", ["letter", "parcel", "package", "pizza", "food"]),
        ("book", ["table", "room", "flight", "shuttle", "ticket", "seat", "taxi"]),
        ("reserve", ["table", "room", "flight", "shuttle", "ticket", "seat"]),
        ("order", ["pizza", "food", "taxi", "flowers"]),
        ("manda", ["carta", "paquete", "postal", "flores", "regalo"]),
        ("mandar", ["carta", "paquete", "postal", "flores", "regalo"]),
        ("envia", ["carta", "paquete", "postal", "flores", "regalo"]),
        ("enviar", ["carta", "paquete", "postal", "flores", "regalo"]),
        ("reserva", ["mesa", "habitacion", "vuelo", "cohete", "billete", "taxi"]),
        ("reservar", ["mesa", "habitacion", "vuelo", "cohete", "billete", "taxi"]),
        ("pide", ["pizza", "comida", "taxi", "flores"]),
        ("pedir", ["pizza", "comida", "taxi", "flores"]),
    ];

    private static bool AsksForAWorldAction(string user)
    {
        foreach ((string verb, string[] objects) in WorldActions)
        {
            if (!user.Contains(verb, StringComparison.Ordinal))
            {
                continue;
            }

            if (objects.Any(item => user.Contains(item, StringComparison.Ordinal)))
            {
                return true;
            }
        }

        return false;
    }

    // Whole words only: «martes» contains «marte», and a note about next
    // Tuesday is not a trip to Mars. NOTES1142 measured that substring
    // match sending a verified note result through the conversation veto.
    /// <summary>
    /// CONVERSATION1345 «Tienes algun meme?»: memes, images, photos, gifs and
    /// stickers cannot be shown here; the mind's plain boundary reply («no
    /// puedo mostrar memes…») must not be rejected as a failure report.
    /// </summary>
    private static bool AsksForVisualContent(string user) =>
        Regex.IsMatch(
            user,
            @"\b(?:tienes|tenes|tendras|tendrias|hay|manda|mandas|mandame|envia|envias|enviame|pasa|pasas|pasame|"
            + @"muestra|muestras|muestrame|mostra|mostrame|da|das|dame|tira|tirame|"
            + @"do you have|have you got|got|send|show|give)\b"
            + @"[^.!?]{0,40}\b(?:meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|"
            + @"picture|pictures|image|images|photo|photos)\b",
            RegexOptions.CultureInvariant);

    private static bool LooksLikeOutOfWorldRequest(string user) =>
        AsksForAWorldAction(user)
        || AsksForVisualContent(user)
        || ContainsAnyWholeWord(
            user,
            ["marte", "mars", "jupiter", "saturn", "neptun", "pluton",
                "europa", "ganymede", "ganimedes", "calisto", "callisto",
                "triton", "ceres", "phobos", "deimos", "oberon", "rocket",
                "bitcoin", "titan",
                "postcard", "to io", "a io", "to the moon", "a la luna",
                "fabrica una hora", "invent a clock", "inventa una hora",
                "fabricate a clock", "fabricate a"]);

    private static bool ContainsAnyWholeWord(string text, IReadOnlyList<string> tokens)
    {
        foreach (string token in tokens)
        {
            if (Regex.IsMatch(
                text,
                @"(?<![\p{L}\p{N}])" + Regex.Escape(token) + @"(?![\p{L}\p{N}])",
                RegexOptions.CultureInvariant))
            {
                return true;
            }
        }

        return false;
    }

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
        ClaimsFirstPersonConnectivity(folded)
        || ContainsAny(
            folded,
            ["tienes internet", "got internet", "estas conectado",
                "you're connected", "you are connected", "no tienes internet",
                "not connected", "sin internet", "wifi is", "estas online",
                "you're online", "you are online", "conectado a internet"]);

    private static bool ClaimsFirstPersonConnectivity(string folded) =>
        ContainsAny(folded, UserMessagePhrases.FirstPersonConnectivityClaims);

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

    private static bool ContainsCatalogActionVerb(string user) =>
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

    /// <summary>
    /// Frases que sólo salen del encargo que el shell escribe… salvo cuando la
    /// persona las usa. «keep talking without launching anything» se contesta
    /// diciendo «I will keep talking without launching anything»: vetar eso
    /// mataba el turno por acertar (limites-22/t9, seis veces publicada y seis
    /// veces tirada). La mente ya tiene la exención (`llm.py`, `prompt_echo`);
    /// el shell la ignoraba y volvía a matar el mismo borrador. Es la misma
    /// exención que ya tienen los términos prohibidos en
    /// <see cref="LeakedInternalTerm"/>.
    /// </summary>
    private static readonly string[] InstructionEchoPhrases =
    [
        "name the pc network",
        "pc network name",
        "in one short sentence",
        "stay in the conversation",
        "keep talking",
        "received the instruction",
        "not yourself",
        "do not introduce yourself",
        "do not describe presence",
    ];

    /// <summary>
    /// Whether the reply echoes an instruction the person never wrote. La
    /// comparación es sobre el pedido plegado: la persona escribe «keep talking
    /// without launching anything» sin acentos ni mayúsculas fijas.
    /// </summary>
    private static bool EchoesAnInstructionThePersonDidNotWrite(
        string folded,
        string? userText)
    {
        string asked = userText is null ? string.Empty : FoldForPolicy(userText);
        foreach (string phrase in InstructionEchoPhrases)
        {
            if (folded.Contains(phrase, StringComparison.Ordinal)
                && !asked.Contains(phrase, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return folded.StartsWith("name the ", StringComparison.Ordinal)
            && !asked.Contains("name the ", StringComparison.Ordinal);
    }

    private static bool ContainsInternalCode(string reply, string? userText = null)
    {
        const RegexOptions options =
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking;
        string folded = FoldForPolicy(reply);
        // A complete identifier already supplied by the person is not a leak.
        // Restrict this exemption to code shapes, preserving all other checks.
        const string identifierPattern = @"[\w-]+(?:[._][\w-]+)+";
        var userIdentifiers = Regex.Matches(userText ?? string.Empty, identifierPattern, options)
            .Select(static match => match.Value)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        string withoutUserIdentifiers = Regex.Replace(reply, identifierPattern,
            match => userIdentifiers.Contains(match.Value) ? string.Empty : match.Value, options);
        // Public web hosts in explanations are not operation identifiers.
        // Only the host span is excluded: codes elsewhere and URL paths still
        // cross the same checks below.
        string withoutWebHosts = Regex.Replace(withoutUserIdentifiers,
            @"\b(?:https?://|www\.)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}\b",
            string.Empty, options | RegexOptions.IgnoreCase);
        return EchoesAnInstructionThePersonDidNotWrite(folded, userText)
            || Regex.IsMatch(withoutUserIdentifiers, @"\b[a-z]{2,}(?:_[a-z0-9]+){1,}\b", options)
            || Regex.IsMatch(withoutWebHosts, @"\b[a-z]{2,}(?:\.[a-z][a-z0-9]*){1,}\b", options)
            || folded.Contains("el mensaje es", StringComparison.Ordinal)
            || folded.Contains("unclear", StringComparison.Ordinal)
            || folded.Contains("entender la solicitud", StringComparison.Ordinal)
            || folded.Contains("borrador anterior", StringComparison.Ordinal)
            || folded.Contains("previous draft", StringComparison.Ordinal)
            || folded.Contains("borrador del welcome", StringComparison.Ordinal)
            || folded.Contains("welcome con exito", StringComparison.Ordinal)
            || folded.Contains("error de composicion", StringComparison.Ordinal)
            || folded.Contains("understand the situation", StringComparison.Ordinal)
            || folded.Contains("understand the task", StringComparison.Ordinal)
            || folded.Contains("situacion del turno", StringComparison.Ordinal)
            || folded.Contains("responder en espanol", StringComparison.Ordinal)
            || folded.Contains("con una frase", StringComparison.Ordinal)
            || folded.Contains("dato adicional", StringComparison.Ordinal)
            || folded.Contains("no tengo acceso", StringComparison.Ordinal)
            || folded.Contains("idioma obligatorio", StringComparison.Ordinal)
            || folded.Contains("request analysis", StringComparison.Ordinal)
            || folded.Contains("status: success", StringComparison.Ordinal)
            || folded.Contains("set the clock", StringComparison.Ordinal)
            || folded.Contains("respond in english as", StringComparison.Ordinal)
            || folded.Contains("draft was closed", StringComparison.Ordinal)
            || folded.Contains("soy by", StringComparison.Ordinal)
            || folded.Contains("</think>", StringComparison.Ordinal)
            || folded.Contains("<think>", StringComparison.Ordinal)
            || folded.Contains("dialogo anterior", StringComparison.Ordinal)
            || folded.Contains("previous dialogue", StringComparison.Ordinal)
            || folded.Contains("el asistente", StringComparison.Ordinal)
            || folded.Contains("referencias semanticas", StringComparison.Ordinal)
            || folded.Contains("semantic reference", StringComparison.Ordinal)
            || folded.Contains("no esta clara", StringComparison.Ordinal)
            || folded.Contains("no estaba clara", StringComparison.Ordinal)
            || folded.Contains("not clear", StringComparison.Ordinal)
            || folded.Contains("isn't clear", StringComparison.Ordinal)
            || folded.Contains("is not clear", StringComparison.Ordinal)
            || folded.Contains("no pudo analizarse", StringComparison.Ordinal)
            || folded.Contains("borrador no cumple", StringComparison.Ordinal)
            || folded.Contains("requisitos especificados", StringComparison.Ordinal)
            || folded.Contains("i'm happy to help", StringComparison.Ordinal)
            || folded.Contains("im happy to help", StringComparison.Ordinal)
            || folded.Contains("i am happy to help", StringComparison.Ordinal)
            || folded.Contains("no es clara", StringComparison.Ordinal)
            || folded.Contains("solicitud es vaga", StringComparison.Ordinal)
            || folded.Contains("is vague", StringComparison.Ordinal)
            || folded.Contains("el sistema detecta", StringComparison.Ordinal)
            || folded.Contains("isn't provided", StringComparison.Ordinal)
            || folded.Contains("is not provided", StringComparison.Ordinal)
            || folded.Contains("solicitud es confusa", StringComparison.Ordinal)
            || folded.Contains("is confusing", StringComparison.Ordinal)
            || folded.Contains("updated document", StringComparison.Ordinal)
            || folded.Contains("la causa es", StringComparison.Ordinal)
            || folded.Contains("como se requiere", StringComparison.Ordinal)
            || folded.Contains("no esta claro", StringComparison.Ordinal)
            || folded.Contains("clarificacion ambigua", StringComparison.Ordinal)
            || folded.Contains("clock field", StringComparison.Ordinal)
            || folded.Contains("mundo digital", StringComparison.Ordinal)
            || folded.Contains("compilar", StringComparison.Ordinal);
    }

    private static bool ClaimsUnverifiedSuccess(string reply)
    {
        string folded = FoldForPolicy(reply);
        return folded.StartsWith("listo", StringComparison.Ordinal)
            || folded.StartsWith("ready", StringComparison.Ordinal)
            || folded.StartsWith("i'm ready", StringComparison.Ordinal)
            || folded.StartsWith("im ready", StringComparison.Ordinal)
            || folded.StartsWith("i am ready", StringComparison.Ordinal)
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

        string lead = asked;
        foreach (string prefix in new[] { "dime ", "dame ", "decime ", "tell me ", "give me " })
        {
            if (asked.StartsWith(prefix, StringComparison.Ordinal))
            {
                lead = asked[prefix.Length..];
                break;
            }
        }

        return answered == asked
            // An explicitly requested greeting is the answer itself. A copied
            // information request following that greeting is still an echo.
            || (answered == lead
                && (!StartsWithGreeting(reply) || LooksLikeKnowledgeQuestion(asked)))
            || (answered.StartsWith(asked, StringComparison.Ordinal)
                && answered.Length <= asked.Length + 12);
    }

    private static bool ContainsPersonMetadiscourse(string folded)
    {
        // The defect is attributing the request to a third person. Merely
        // mentioning a user/account is valid, including "Tú eres el usuario…".
        // Bind the subject to a request/speech predicate instead of banning
        // the noun everywhere or exempting one literal account name.
        return Regex.IsMatch(
            folded,
            @"\b(?:(?:al|del|el|la|este|esta|ese|esa)\s+(?:usuario|usuaria|persona)|(?:the|this|that)\s+(?:user|person|requester))\s+(?:le gustaria|le interesa|quiere|quisiera|desea|prefiere|pidio|ha pedido|pregunto|dijo|saludo|solicito|menciono|se refiere|would like|wants|asked|said|greeted|requested|mentioned|prefers|has asked|is referring)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
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
        // Absence of failures is compatible with a successful observation.
        // Remove only the negated failure assertion, not the whole sentence:
        // an independent "but the CPU check failed" must still be detected.
        string assertedFailures = Regex.Replace(
            normalized,
            @"\b(?:(?:sin|ningun[oa]?|no\s+(?:hay|hubo))\s+(?:ningun[oa]?\s+)?fallos?\b"
            + @"|no\s+se\s+(?:(?:ha|han)\s+)?(?:detect|registr|report|encontr)(?:ado|o|aron)\s+(?:ningun[oa]?\s+)?fallos?\b"
            + @"|(?:not|never)\s+failed\b|(?:no|zero|0)\s+failed\b"
            + @"|none\s+of\s+(?:(?!(?:but|and)\b)\w+\s+){1,5}failed\b)",
            string.Empty,
            RegexOptions.CultureInvariant);
        return normalized.Contains("no pude", StringComparison.Ordinal)
        || normalized.Contains("no puedo", StringComparison.Ordinal)
        || normalized.Contains("no complete", StringComparison.Ordinal)
        || normalized.Contains("no logre", StringComparison.Ordinal)
        || Regex.IsMatch(assertedFailures,
            @"\b(?:fallos?|failed)\b|\bno\s+(?:encontre|se\s+(?:pudo|pudieron|encontro|encontraron))\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
        || normalized.Contains("no recibí", StringComparison.Ordinal)
        || normalized.Contains("no realicé", StringComparison.Ordinal)
        || normalized.Contains("no interpreté", StringComparison.Ordinal)
        || normalized.Contains("no está disponible", StringComparison.Ordinal)
        || Regex.IsMatch(normalized, @"\b(?:cannot|can't|could\s+not|couldn't)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
        || normalized.Contains("wasn't able", StringComparison.Ordinal)
        || normalized.Contains("was not able", StringComparison.Ordinal)
        // WEB1269: a search that found nothing useful is a failure the person
        // must hear as such («the results were irrelevant», «sin resultados»).
        || Regex.IsMatch(normalized,
            @"\b(?:irrelevant|irrelevantes?|no\s+useful\s+results|nothing\s+useful|no\s+results|sin\s+resultados|no\s+(?:hubo|hay)\s+resultados)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
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

    private static bool MissesObservedAudio(string source, string result)
    {
        if (!ObservedHasAudio(source))
        {
            return false;
        }

        string folded = FoldForPolicy(result);
        return !ContainsAny(
            folded,
            ["volumen", "volume", "silenci", "muted", "unmuted", "mute",
                "audio", "altavoc"]);
    }

    private static bool ObservedHasAudio(string source)
    {
        if (!IsStructuredFacts(source) || !TryReadJson(source, out JsonElement root))
        {
            return false;
        }

        if (ObservedObjectHasAudio(root))
        {
            return true;
        }

        if (!root.TryGetProperty("steps", out JsonElement steps)
            || steps.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (JsonElement step in steps.EnumerateArray())
        {
            if (step.GetString() is { Length: > 0 } text
                && IsStructuredFacts(text)
                && TryReadJson(text, out JsonElement nested)
                && ObservedObjectHasAudio(nested))
            {
                return true;
            }
        }

        return false;
    }

    private static bool ObservedObjectHasAudio(JsonElement root)
    {
        if (!root.TryGetProperty("observed", out JsonElement observed)
            || observed.ValueKind != JsonValueKind.Object)
        {
            observed = root;
        }

        if (observed.TryGetProperty("muted", out _)
            || observed.TryGetProperty("level", out _)
            || observed.TryGetProperty("volumePercent", out _))
        {
            return true;
        }

        if (!observed.TryGetProperty("state", out JsonElement state)
            || state.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        return state.TryGetProperty("muted", out _)
            || state.TryGetProperty("level", out _)
            || state.TryGetProperty("volumePercent", out _);
    }

    private static bool PreservesObservedClock(string source, string result)
    {
        if (!TryDerivedLocalClock(source, out string hhmm))
        {
            return true;
        }

        return ClockAppears(FoldForPolicy(result), hhmm);
    }

    private static readonly CultureInfo[] CalendarCultures =
        [CultureInfo.GetCultureInfo("es-ES"), CultureInfo.GetCultureInfo("en-US")];

    private static bool PreservesObservedDate(string source, string result)
    {
        if (!TryDerivedLocalMoment(source, out DateTimeOffset local))
        {
            return true;
        }

        const string month = "(?:enero|january|febrero|february|marzo|march|abril|april|"
            + "mayo|may|junio|june|julio|july|agosto|august|septiembre|setiembre|"
            + "september|octubre|october|noviembre|november|diciembre|december)";
        string pattern = @"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+(?:de\s+)?"
            + month + @"(?:\s+(?:de\s+)?\d{4})?|" + month
            + @"\s+\d{1,2}(?:,?\s+\d{4})?)\b";
        bool found = false;
        foreach (Match match in Regex.Matches(result, pattern,
                     RegexOptions.IgnoreCase | RegexOptions.CultureInvariant))
        {
            found = true;
            bool hasYear = Regex.IsMatch(match.Value, @"\b\d{4}\b");
            bool sameDate = CalendarCultures.Any(culture =>
                DateOnly.TryParse(match.Value, culture,
                    DateTimeStyles.AllowWhiteSpaces, out DateOnly date)
                && date.Month == local.Month && date.Day == local.Day
                && (!hasYear || date.Year == local.Year));
            if (!sameDate)
            {
                return false;
            }
        }

        return found;
    }

    private static bool InventedVolume(string source, string result)
    {
        string folded = FoldForPolicy(result);
        if (!ContainsAny(folded, ["volumen", "volume", " muted", "silenci"]))
        {
            return false;
        }

        if (!IsStructuredFacts(source))
        {
            return true;
        }

        return !source.Contains("\"level\"", StringComparison.Ordinal)
            && !source.Contains("\"muted\"", StringComparison.Ordinal)
            && !source.Contains("\"volumePercent\"", StringComparison.Ordinal);
    }

    private static bool InventedExtraClock(string source, string result)
    {
        if (!TryDerivedLocalClock(source, out string hhmm))
        {
            return false;
        }

        foreach (Match match in MatchClockTokens(result))
        {
            if (!ClockAppears(match.Value, hhmm))
            {
                return true;
            }
        }

        return false;
    }

    private static bool InventsOutOfWorldObject(string userText, string reply)
    {
        if (!LooksLikeOutOfWorldRequest(FoldForPolicy(userText)))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        return ContainsAny(
                said,
                ["libro", "book is reserved", "ya esta reservado", "ya está reservado",
                    "esta reservado", "está reservado", "is reserved", "reservado en",
                    "cuarto de noche", "booked"])
            || reply.Contains("teá", StringComparison.Ordinal)
            || ClaimsUnverifiedSuccess(reply)
            || IsGreetingOnly(reply);
    }

    private static bool ContainsInventedUtcOffset(string userText, string reply)
    {
        if (Regex.IsMatch(
                FoldForPolicy(reply),
                @"\butc\s*[+-]\s*\d+",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            && !FoldForPolicy(userText).Contains("utc", StringComparison.Ordinal))
        {
            return true;
        }

        return false;
    }

    private static bool InventsClockPlace(string result)
    {
        string folded = FoldForPolicy(result);
        return ContainsClockPattern(result)
            && ContainsAny(
                folded,
                ["de la sala", "of the room", "wall clock", "reloj de la",
                    "baxy is at", "seen you", "he visto", "living on the pc",
                    "vive en el pc", "i'm baxy", "im baxy"]);
    }

    private static bool DumpsUnsolicitedInterfaces(string userText, string reply)
    {
        string said = FoldForPolicy(reply);
        if (!ContainsAny(said, ["ethernet", "interfaces conectadas", "interfaces"]))
        {
            return false;
        }

        return string.IsNullOrWhiteSpace(userText)
            || !ContainsAny(FoldForPolicy(userText), ["ethernet", "interface"]);
    }

    private static bool MissesRequestedTranslation(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        if (!ContainsAny(user, ["traduce", "translate "]))
        {
            return false;
        }

        string folded = FoldForPolicy(reply).Trim().Trim('.', '!', '?', '¿', '¡', ' ');
        if (user.Contains("al espanol", StringComparison.Ordinal)
            || user.Contains("al español", StringComparison.Ordinal)
            || user.Contains("to spanish", StringComparison.Ordinal))
        {
            if (folded is "hi" or "hello" or "hey"
                || folded.StartsWith("hi,", StringComparison.Ordinal)
                || folded.StartsWith("hello,", StringComparison.Ordinal)
                || ContainsAny(folded, ["puedo ayudarte", "en que puedo", "i'm baxy", "im baxy"]))
            {
                return true;
            }

            if (ContainsAny(user, ["good morning"])
                && !ContainsAny(folded, ["buenos", "dias"]))
            {
                return true;
            }

            if (ContainsAny(user, ["good night", "good evening"])
                && !ContainsAny(folded, ["noches", "tardes"]))
            {
                return true;
            }

            if (ContainsAny(user, ["hello", "'hi'", "\"hi\""])
                && !ContainsAny(user, ["good morning", "good night", "good evening"])
                && !folded.Contains("hola", StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    private static bool LeaksPriorKnowledgeTopic(string userText, string reply)
    {
        if (!LooksLikeAmbiguousAction(FoldForPolicy(userText)))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        return ContainsAny(
            said,
            [" utc", "utc ", "huso", "time zone", "zona horaria", "una sola linea"]);
    }

    private static bool InventsUnsolicitedLegalFrame(string userText, string reply)
    {
        if (!LooksLikeKnowledgeQuestion(FoldForPolicy(userText)))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        return ContainsAny(
            said,
            ["illegal", "unethical", "ethical", "malicious", "principios", "ilegal",
                "safety polic", "promotes harm", "harmful", "legal requirement",
                "legal requirements", "guidelines"]);
    }

    private static bool InvertsRefuseQuestion(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        if (!ContainsAny(
                user,
                ["what will you", "what do you refuse", "que rechazas"]))
        {
            return false;
        }

        return ContainsAny(
            FoldForPolicy(reply),
            UserMessagePhrases.RefusalDenials);
    }

    private static bool MissesRefuseAnswer(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        if (!ContainsAny(
                user,
                ["what will you", "what do you refuse", "que rechazas"]))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        return !ContainsAny(said, UserMessagePhrases.LimitAnswers);
    }

    private static bool NamesNonPcRefuseAct(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        if (!ContainsAny(
                user,
                ["what will you", "what do you refuse", "que rechazas"]))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        if (ContainsAny(
                said,
                ["i don't do that", "i do not do that", "eso no lo hago"]))
        {
            return false;
        }

        if (!ContainsAny(said, UserMessagePhrases.LimitAnswers))
        {
            return false;
        }

        // Restringirse al trabajo de este PC ya nombra el ámbito: no hace falta
        // además un verbo de la lista para no ser una categoría moral.
        if (ContainsAny(
                said,
                ["only do", "only what", "only the work", "nothing beyond",
                    "nothing else", "nothing more", "not listed", "outside",
                    "solo hago", "sólo hago", "solo lo que", "sólo lo que",
                    "nada mas", "nada más", "unicamente", "únicamente",
                    "fuera de"]))
        {
            return false;
        }

        return !ContainsAny(
            said,
            ["open", "close", "launch", "book", "send", "install", "delete", "mute",
                "volume", "window", "app", "note", "file", "browser", "print",
                "abrir", "cerrar", "lanzar", "reservar", "enviar", "instalar", "room"]);
    }

    private static bool InventsUnsolicitedHardwareSpec(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        if (!ContainsAny(
                user,
                ["what will you", "what do you refuse", "que rechazas"]))
        {
            return false;
        }

        string said = FoldForPolicy(reply);
        return ContainsAny(said, [" ram", "ram ", " gb", "memory limit", "memory capacity"])
            || Regex.IsMatch(
                said,
                @"\b\d+\s*gb\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool InvertsNegativeConstraint(string userText, string reply)
    {
        string user = FoldForPolicy(userText);
        string said = FoldForPolicy(reply);
        if (LooksLikeContinueConstraint(user)
            && ContainsAny(said, UserMessagePhrases.ContinueConstraintRefusals))
        {
            return true;
        }

        if (!ContainsAny(
                user,
                ["no abras", "don't open", "dont open", "no lances",
                    "don't launch", "dont launch"]))
        {
            return false;
        }

        return ContainsAny(said, UserMessagePhrases.OpenRefusals);
    }

    private static bool ClaimsUnverifiedAmbiguousEffect(string userText, string reply)
    {
        if (!LooksLikeAmbiguousAction(FoldForPolicy(userText)))
        {
            return false;
        }

        return ContainsAny(
            FoldForPolicy(reply),
            ["he cerrado", "i closed", "i have closed", "i've closed",
                "cerre el", "proceso actual", "explorer", "esa carpeta"]);
    }

    private static bool InventedAppEffectOnClock(string source, string result)
    {
        // APPS1387 «abrí la calculadora y decime qué hora es»: the mission did
        // open the application before reading the clock, so «Abrí la calculadora
        // y son las 05:46» states a verified effect, not an invented one.
        if (!TryDerivedLocalClock(source, out _) || MissionOpenedAnApplication(source))
        {
            return false;
        }

        string folded = FoldForPolicy(result);
        return ContainsAny(
            folded,
            ["app is open", "the app is", "esta abierto", "esta abierta", "abri ",
                "is open", "mensaje fue enviado", "at level", "the app ",
                "pc is online", "the pc is online", "is online and",
                "hay red", "i am online", "i'm online", "estoy listo",
                "am online", "baxy esta en el pc", "titulo de nota",
                "el documento", "i am on the pc", "i'm at the pc",
                "im at the pc"]);
    }

    private static bool MissionOpenedAnApplication(string source)
    {
        if (!IsStructuredFacts(source)
            || !TryReadJson(source, out JsonElement root)
            || !root.TryGetProperty("steps", out JsonElement steps)
            || steps.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (JsonElement step in steps.EnumerateArray())
        {
            if (step.ValueKind == JsonValueKind.String
                && step.GetString() is { Length: > 0 } text
                && IsStructuredFacts(text)
                && TryReadJson(text, out JsonElement nested)
                && nested.TryGetProperty("operation", out JsonElement operation)
                && operation.ValueKind == JsonValueKind.String
                && operation.GetString() == "app.open"
                && ((nested.TryGetProperty("succeeded", out JsonElement succeeded)
                        && succeeded.ValueKind == JsonValueKind.True)
                    || (nested.TryGetProperty("verified", out JsonElement verified)
                        && verified.ValueKind == JsonValueKind.True)))
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsBareSuccessOpener(string modelText)
    {
        string folded = FoldForPolicy(modelText).Trim().Trim('.', '!', ' ');
        return folded is "listo" or "ready" or "done";
    }

    private static bool IsDanglingNamedSuccess(string source, string result)
    {
        string folded = FoldForPolicy(result).Trim().Trim('.', '!', ' ');
        if (!folded.StartsWith("listo, ", StringComparison.Ordinal))
        {
            return false;
        }

        string rest = folded["listo, ".Length..];
        if (rest.Contains(' ', StringComparison.Ordinal))
        {
            return false;
        }

        return rest.Length is >= 2 and <= 32
            && !FoldForPolicy(source).Contains(rest, StringComparison.Ordinal);
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
        if (!TryDerivedLocalMoment(source, out DateTimeOffset local))
        {
            return false;
        }

        hhmm = local.Hour.ToString(CultureInfo.InvariantCulture)
            + ":" + local.Minute.ToString("D2", CultureInfo.InvariantCulture);
        return true;
    }

    private static bool TryDerivedLocalMoment(string source, out DateTimeOffset local)
    {
        local = default;
        if (!IsStructuredFacts(source) || !TryReadJson(source, out JsonElement root))
        {
            return false;
        }

        if (!TryMomentFromObserved(root, out local)
            && root.TryGetProperty("steps", out JsonElement steps)
            && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.GetString() is { Length: > 0 } text
                    && IsStructuredFacts(text)
                    && TryReadJson(text, out JsonElement nested)
                    && TryMomentFromObserved(nested, out local))
                {
                    return true;
                }
            }

            return false;
        }

        return local != default;
    }

    private static bool TryMomentFromObserved(JsonElement root, out DateTimeOffset local)
    {
        local = default;
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

        local = utcTime.ToOffset(TimeSpan.FromMinutes(offsetMinutes));
        return true;
    }

    private static readonly Regex ClockTokens = new(
        @"\b(\d{1,2})(?::|\s+(?:horas?\s+y|hours?\s+and)\s+)"
            + @"(\d{1,2})(?:\s+(?:minutos?|minutes?))?(?:\s*([ap])\.?\s*m\.?)?\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static readonly Regex SpokenClockTokens = new(
        @"\b(?:son\s+las|es\s+la)\s+(\d{1,2})\s+y\s+(\d{1,2})"
            + @"(?:\s+minutos?)?(?:\s*([ap])\.?\s*m\.?)?\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static IEnumerable<Match> MatchClockTokens(string text) =>
        ClockTokens.Matches(text).Concat(SpokenClockTokens.Matches(text));

    private static bool ClockAppears(string foldedResult, string hhmm)
    {
        string[] parts = hhmm.Split(':');
        if (parts.Length != 2
            || !int.TryParse(parts[0], CultureInfo.InvariantCulture, out int hour)
            || !int.TryParse(parts[1], CultureInfo.InvariantCulture, out int minute))
        {
            return false;
        }

        foreach (Match match in MatchClockTokens(foldedResult))
        {
            int statedHour = int.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
            int statedMinute = int.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture);
            if (match.Groups[3].Success)
            {
                if (statedHour is < 1 or > 12)
                {
                    continue;
                }
                statedHour = statedHour % 12
                    + (match.Groups[3].Value.Equals("p", StringComparison.OrdinalIgnoreCase) ? 12 : 0);
            }
            if (statedHour == hour && statedMinute == minute)
            {
                return true;
            }
        }
        return false;
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

        result = WithoutVerifiedEmptyKnownFileFinding(source, result);
        result = WithoutScreenReadingImageScope(source, result);

        if (TryReadJson(source, out JsonElement root)
            && root.TryGetProperty("kind", out JsonElement kind) && kind.ValueKind == JsonValueKind.String && kind.GetString() == "operation"
            && root.TryGetProperty("operation", out JsonElement operation) && operation.ValueKind == JsonValueKind.String && operation.GetString() == "app.installed"
            && root.TryGetProperty("polarity", out JsonElement polarity) && polarity.ValueKind == JsonValueKind.String && polarity.GetString() == "success"
            && root.TryGetProperty("verified", out JsonElement verified) && verified.ValueKind == JsonValueKind.True
            && root.TryGetProperty("succeeded", out JsonElement succeeded) && succeeded.ValueKind == JsonValueKind.True
            && root.TryGetProperty("observed", out JsonElement observed) && observed.ValueKind == JsonValueKind.Object
            && observed.TryGetProperty("installed", out JsonElement installed) && installed.ValueKind == JsonValueKind.False
            && observed.TryGetProperty("authority", out JsonElement authority) && authority.ValueKind == JsonValueKind.String && authority.GetString() == "windows_start_catalog_snapshot"
            && observed.TryGetProperty("requestedName", out JsonElement requestedName) && requestedName.ValueKind == JsonValueKind.String
            && requestedName.GetString() is { Length: > 0 } name && !string.IsNullOrWhiteSpace(name))
        {
            // Reading absence is successful; a separate failure or invented opening is not.
            string assertions = FoldForPolicy(result);
            if (Regex.IsMatch(assertions,
                @"(?:^|[.;]|\b(?:pero|but|y|and)\b)\s*(?:(?:ya|yo|i|you|we|la|lo)\s+)*"
                + @"(?:abri|abriste|abrio|abrieron|opened|launched|intente|intentamos|tried|attempted)\b"
                + @"|\b(?:is|was|has\s+been)\s+(?:opened|launched)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
            {
                return true;
            }

            string target = @"(?:(?:la|the)\s+)?(?:(?:aplicacion|application|app)\s+)?"
                + Regex.Escape(FoldForPolicy(name));
            string scope = @"(?:en|in)\s+(?:el\s+catalogo(?:\s+de\s+(?:la\s+autoridad\s+observada|inicio\s+de\s+windows))?"
                + @"|the\s+(?:(?:observed|windows\s+start(?:\s+application)?)\s+)?catalog(?:ue)?"
                + @"(?:\s+of\s+the\s+observed\s+authority)?)";
            string absent = $@"(?:no\s+se\s+encontro\s+{target}|{target}\s+(?:was\s+)?not\s+found)\s+{scope}";
            string cannotOpen = @"(?:no\s+(?:se\s+)?(?:pude|pudo|puedo|puede)\s+abrir"
                + @"|(?:i\s+)?(?:couldn't|could\s+not|cannot|can't)\s+open)";
            string supported = $@"(?:{absent})(?:,\s*(?:por\s+lo\s+que|asi\s+que|so)\s+"
                + $@"(?:{cannotOpen}|it\s+(?:cannot|can't|could\s+not)\s+be\s+opened))?"
                + $@"|{cannotOpen}\s+{target}\s+(?:porque|because)\s+"
                + $@"(?:no\s+esta(?:\s+presente)?|(?:it\s+is|it's)\s+not\s+found)\s+{scope}";
            result = Regex.Replace(assertions, @"[^.;\n]+[.;]?", clause =>
                Regex.IsMatch(clause.Value.Trim().TrimEnd('.', ';'), $@"\A(?:{supported})\z",
                    RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
                    ? " " : clause.Value,
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
        }

        return LooksLikeFailure(result);
    }

    // SCREEN1417 «qué hay en la pantalla»: no vision provider exists, so a
    // verified screen reading says it cannot describe images and reads the
    // text. That clause states the reading's scope, not a failed mission.
    private static string WithoutScreenReadingImageScope(string source, string result)
    {
        if (!HasVerifiedScreenReading(source, 0))
        {
            return result;
        }

        return Regex.Replace(
            FoldForPolicy(result),
            @"\b(?:no\s+(?:puedo|podia|podria)|(?:i\s+)?(?:can't|cannot|can\s+not|couldn't|could\s+not|am\s+unable\s+to|am\s+not\s+able\s+to))"
            + @"\s+(?:describir|describirte|ver|describe|see)\s+(?:las\s+|the\s+)?(?:imagenes?|images?|pictures?|graficos?|graphics|visuales?|visuals)"
            + @"[^.;]{0,80}",
            " ",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool HasVerifiedScreenReading(string source, int depth)
    {
        if (depth > 8 || !TryReadJson(source, out JsonElement root) || root.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        if (root.TryGetProperty("operation", out JsonElement operation) && operation.ValueKind == JsonValueKind.String
            && operation.GetString() == "ocr.read"
            && root.TryGetProperty("verified", out JsonElement verified) && verified.ValueKind == JsonValueKind.True
            && root.TryGetProperty("succeeded", out JsonElement succeeded) && succeeded.ValueKind == JsonValueKind.True)
        {
            return true;
        }

        if (root.TryGetProperty("steps", out JsonElement steps) && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.ValueKind == JsonValueKind.String && HasVerifiedScreenReading(step.GetString()!, depth + 1))
                {
                    return true;
                }
            }
        }

        return false;
    }

    private static string WithoutVerifiedEmptyKnownFileFinding(string source, string result)
    {
        if (!TryReadJson(source, out JsonElement root)
            || !root.TryGetProperty("kind", out JsonElement kind) || kind.ValueKind != JsonValueKind.String || kind.GetString() != "operation"
            || !root.TryGetProperty("operation", out JsonElement operation) || operation.ValueKind != JsonValueKind.String || operation.GetString() != "filesystem.known.search"
            || !root.TryGetProperty("polarity", out JsonElement polarity) || polarity.ValueKind != JsonValueKind.String || polarity.GetString() != "success"
            || !root.TryGetProperty("verified", out JsonElement verified) || verified.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("succeeded", out JsonElement succeeded) || succeeded.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("observed", out JsonElement observed) || observed.ValueKind != JsonValueKind.Object
            || !observed.TryGetProperty("authority", out JsonElement authority) || authority.ValueKind != JsonValueKind.String || authority.GetString() != "windows_known_folders_bounded_postread"
            || !observed.TryGetProperty("count", out JsonElement count) || count.ValueKind != JsonValueKind.Number || !count.TryGetInt32(out int matches) || matches != 0
            || !observed.TryGetProperty("files", out JsonElement files) || files.ValueKind != JsonValueKind.Array || files.GetArrayLength() != 0
            || !observed.TryGetProperty("query", out JsonElement query) || query.ValueKind != JsonValueKind.String
            || query.GetString() is not { Length: > 0 } name || string.IsNullOrWhiteSpace(name))
        {
            return result;
        }

        // Only the query-bound negative finding is neutral in the failure lens.
        // Keep scope qualifiers and independent assertions; all other validators
        // still receive the original response and observed facts.
        string target = @"[""'«»“”‘’]?(?<!\w)" + Regex.Escape(FoldForPolicy(name.Trim()))
            + @"(?!\w)[""'«»“”‘’]?";
        string fileName = @"(?:(?:el|un|ningun|ninguno|the|a|any)\s+)?"
            + @"(?:(?:archivo|file)\s+)?(?:(?:llamado|named)\s+)?" + target;
        string finding = $@"\bno\s+(?:encontre|se\s+encontro)\s+{fileName}"
            + $@"|\b(?:i\s+)?(?:didn't|did\s+not)\s+find\s+{fileName}"
            + $@"|{fileName}\s+(?:no\s+se\s+encontro|was\s+not\s+found)\b";
        return Regex.Replace(FoldForPolicy(result), finding, string.Empty,
            RegexOptions.CultureInvariant);
    }

    private static bool ReversesFailedResult(string source, string result)
    {
        if (!LooksLikeFailure(source))
        {
            return false;
        }

        // out_of_catalog is a refuse, not a failed attempt. Honest "I don't
        // do that" / "eso no lo hago" must publish; only a claimed success
        // (Listo / ready / done) reverses the polarity.
        if (IsOutOfCatalogFailure(source))
        {
            return ClaimsUnverifiedSuccess(result);
        }

        return !LooksLikeFailure(result);
    }

    private static bool IsOutOfCatalogFailure(string source)
    {
        return IsStructuredFacts(source)
            && TryReadJson(source, out JsonElement root)
            && root.TryGetProperty("cause", out JsonElement cause)
            && cause.ValueKind == JsonValueKind.String
            && string.Equals(cause.GetString(), "out_of_catalog", StringComparison.Ordinal);
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
        // A single short recalled value is an observed literal, just like a
        // title. Preserve it through both composition and final acceptance.
        // Lists/long records still travel as observations; requiring every
        // value would turn a read into an unbounded literal-copy contract.
        if (root.TryGetProperty("operation", out JsonElement operation)
            && operation.ValueKind == JsonValueKind.String
            && operation.GetString() is "memory.recall" or "memory.list"
            && root.TryGetProperty("verified", out JsonElement verified)
            && verified.ValueKind == JsonValueKind.True
            && root.TryGetProperty("succeeded", out JsonElement succeeded)
            && succeeded.ValueKind == JsonValueKind.True
            && root.TryGetProperty("observed", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.Object
            && observed.TryGetProperty("records", out JsonElement records)
            && records.ValueKind == JsonValueKind.Array
            && records.GetArrayLength() == 1
            && records[0].ValueKind == JsonValueKind.Object
            && records[0].TryGetProperty("value", out JsonElement recalled)
            && recalled.ValueKind == JsonValueKind.String
            && recalled.GetString() is { Length: > 0 and <= 256 } literal
            && literal != "[REDACTED]")
        {
            facts.Add(literal);
        }

        foreach (string key in new[] { "reason", "title" })
        {
            if (root.TryGetProperty(key, out JsonElement value)
                && value.ValueKind == JsonValueKind.String
                && value.GetString() is { Length: > 0 } text)
            {
                facts.Add(text);
            }
        }
        if (root.TryGetProperty("reason", out JsonElement reason)
            && reason.ValueKind == JsonValueKind.Object)
        {
            CollectStructuredLiterals(reason, facts);
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
