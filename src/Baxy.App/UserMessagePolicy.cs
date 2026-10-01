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
            if (!NamesTerm(text, term))
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

    /// <summary>
    /// A7 E2 (FINAL t241): a jargon term ends where its word ends. «operacion» inside «operaciones básicas»
    /// (arithmetic) or «tool» inside «toolkit» go on into another word; a name glued in front («XRouter notes»)
    /// still says «router». Twin of llm._names_forbidden_term.
    /// </summary>
    private static bool NamesTerm(string text, string term)
    {
        if (!text.Contains(term, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        string end = char.IsLetterOrDigit(term[^1]) ? @"(?![\w])" : string.Empty;
        return Regex.IsMatch(
            text,
            Regex.Escape(term) + end,
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
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
        // M50: in a conversation reply to a code request the code is the content asked for; only the prose around
        // it is judged for jargon and internal codes. A reply that is only code has no prose to judge.
        bool codeAsked = draft.Intent == "conversation" && AsksForCode(userText, priorUserText);
        if (codeAsked)
        {
            vocabularyText = RequestedCodeProse(vocabularyText);
        }
        if ((!codeAsked || vocabularyText.Length > 0)
            && LeakedInternalTerm(vocabularyText, userText, priorUserText) is not null)
        {
            return "unsafe_language";
        }

        if (BreaksFirstPerson(modelText))
        {
            return "broken_person_conjugation";
        }

        if (SpeaksOfThePerson(modelText, string.Concat(userText, " ", priorUserText)))
        {
            return "third_person_addressee";
        }

        if (IsPunctuationOnly(modelText) || IsTooThin(modelText))
        {
            return "no_response";
        }

        // WEB1481 «Investiga en internet que es el h2o»: a quoted result title
        // («¿Qué significa H2O?») is observed data, not the model restating the
        // definition ask; the lexical checks read the masked vocabulary.
        string judgedText = codeAsked ? vocabularyText : modelText;
        if (LooksLikeMachineSlotAsk(FoldForPolicy(vocabularyText))
            || LooksLikeRestatingDefinitionAsk(FoldForPolicy(vocabularyText))
            || HasRepeatedWord(FoldForPolicy(judgedText))
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
            // M108 twin of compose_visible_defect: the report of a result names no contract token, and what was
            // verified is never promised.
            if (!IsConversationSituation(draft.Source)
                && LeaksContractToken(modelText, draft.Source, string.Concat(userText, "\n", priorUserText)))
            {
                return "internal_code";
            }
            if (draft.Intent == "status" && !IsConversationSituation(draft.Source)
                && IsVerifiedEffect(draft.Source) && PromisesTheAct(modelText))
            {
                return "promised_effect";
            }
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
            // The mind projects only the date for it (semantic.network.asks_calendar_part);
            // reading it as a clock request here demanded the hour in the draft and
            // rejected six correct dates until the diagnostic code was published
            // (CLOCK1157/000..002).
            bool dateRequested = AsksCalendarPart(userText);
            bool clockRequested = !dateRequested || Regex.IsMatch(userText ?? string.Empty,
                @"\b(?:hora|time)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
            // CLOCK1333 «cuánto falta para las 3 de la tarde»: the answer is the
            // remaining time computed by the mind («Faltan 13 horas y 43 minutos
            // para las 3 de la tarde»); the observed clock is optional there and
            // the asked time is not an extra invented clock.
            bool countdownRequested = IsCountdownRequest(userText);
            // A7 C (DEV-A3 t217 «¿qué hora será de aquí a doce minutos?»): the mind adds the minutes to the
            // observed clock (M40) and its guard checks that later time; the current clock is not the answer.
            bool laterClockRequested = IsLaterClockRequest(userText);
            // M63 (v3f-final F-s019): a failure about the clock the person named («no hay alarma a las 8:00») owes
            // that clock, not this PC's current one.
            bool namedClockFailure = draft.Intent == "error" && PersonNamedClocks(userText).Count > 0;
            if (clockRequested && !countdownRequested && !laterClockRequested && !namedClockFailure
                && !PreservesObservedClock(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (dateRequested && !PreservesObservedDate(draft.Source, modelText, userText))
            {
                return "missing_literal_fact";
            }
            if (MissesObservedAudio(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (InventedClock(draft.Source, modelText, userText))
            {
                return "missing_literal_fact";
            }
            if (InventedVolume(draft.Source, modelText, userText))
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
            if (!countdownRequested && !laterClockRequested && InventedExtraClock(draft.Source, modelText, userText))
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
            // M69 (guion v3h t47): the asked state that already held is published as a result; its final still
            // tells the unchanged state and never an effect («Listo, activé el micrófono»).
            if ((draft.Intent == "error" || IsAskedStateAlreadyHeld(draft.Source))
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
        bool hasRequiredInput = false,
        IReadOnlyList<string>? missingFields = null) =>
        ConversationReplyRejectionReason(userText, reply, mindLanguage, priorUserText, clarification, hasRequiredInput, missingFields) is null;

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
        IReadOnlyList<string>? missingFields = null,
        bool unsupportedByMind = false)
    {
        // M50 (v3a-final F-w07-t1, F-w12-t1/t2: the mind's code was refused as internal_code): when the person asked
        // for code, the code of the reply is the content asked for and only the prose around it is judged. A reply
        // that is only code has nothing else to judge.
        if (!clarification && AsksForCode(userText, priorUserText) && !string.IsNullOrWhiteSpace(reply))
        {
            reply = RequestedCodeProse(reply);
            if (reply.Length == 0)
            {
                return null;
            }
        }

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
            // UI1647 «Type in the chat box.»: when the mind declares the text
            // as the missing field, the question names the place the person
            // named; repeating that place is the frame of the question, not a
            // request echoed back as a yes/no.
            ("echoes_request",
                !IsGreetingRequest(userText) && EchoesRequestAsQuestion(userText, reply)
                && !AsksForDeclaredText(said, missingFields)),
            ("greets_out_of_world", GreetsOutOfWorldTarget(said)),
            ("unverified_connectivity", ClaimsUnverifiedConnectivity(said)),
            // UI1659 «Go to the announcements channel in Discord.»: the mind
            // closed the turn as a known unsupported effect and its bounded
            // contract validated «I cannot go to …»; the request-text heuristic
            // does not see that limit, so the kind is passed explicitly. A limit
            // never attempted anything, so a reply that claims a failed attempt
            // («No pude abrir la aplicación») is still rejected and the turn
            // keeps its out_of_catalog boundary (plan post-goal 2026-09-20,
            // Fase 1 grupo F; mirrors the mind's own extra_claim veto).
            ("looks_like_failure",
                // M85 (DEV-D v3o D-p36-t2): what the characters of a written dialogue say inside quotes is theirs.
                LooksLikeFailure(WithoutQuotedSpeech(reply))
                && !(unsupportedByMind && !ClaimsFailedAttempt(reply))
                // M85 (DEV-D v3o D-p27-t1 «I don't know what you like, so I can't recommend anything specific. What
                // kind of movies do you usually enjoy?»): what BAXY cannot say yet (recommend, tell, choose), said to
                // ask the person for what is missing, is a question, not a failure told. «I can't browse the
                // internet… What do you like?» still is one. Twin of the mind's asserted_failure exemption.
                && !(EndsAskingThePerson(reply) && !ClaimsFailedAttempt(reply)
                    && !LooksLikeFailure(WithoutSayingInability(WithoutQuotedSpeech(reply))))
                // M75 (DEV-D v3l D-p02-t2): «No puedo hacer fotos» answers «¿Serías capaz de hacer foto ahora?».
                && !(AsksWhetherAble(user) && !ClaimsFailedAttempt(reply))
                && !OnlyEchoesThePersonsFailures(reply, userText)
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
            // MEME2053 «tienes alguna foto?»: an image with no subject is now
            // downloadable (web.download + file.open); the mind declares the
            // query as the missing field and asks what the picture should
            // show. That question names the picture; it is not a question
            // about something this world cannot do.
            ("out_of_world_question",
                LooksLikeOutOfWorldRequest(user)
                && AsksAboutTheOutOfWorldRequest(user, reply)
                && !AsksForDeclaredImageSubject(user, said, missingFields)),
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
                // KNOW1833: a long declarative statement («…, that is why pipes
                // burst in winter, at least that is what they told me.») carries
                // ask words that lead no clause; the mind's overheard-speech
                // clarification asks, and that question is not an unanswered ask.
                && !IsLongDeclarativeStatement(user)
                // M75 (DEV-D v3l D-w15-t3): with nothing to translate in the message, asking which is the answer.
                && !TranslationWithoutItsText(userText)
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
            ("broken_person_conjugation", BreaksFirstPerson(reply)),
            ("third_person_addressee", SpeaksOfThePerson(reply, string.Concat(userText, " ", priorUserText))),
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
            // Tanda 7 «¿cuánto rato queda para las seis?»: the mind's countdown reading (semantic/temporal.py
            // _COUNTDOWN_HEAD) takes any measure of time and any verb of remaining; the shell reads the same head.
            @"^\s*[¿¡]?\s*(?:(?:cu[aá]nt[oa]s?|qu[eé]\s+tanto)\s+(?:(?:tiempo|rato|horas?|minutos?)\s+)?"
            + @"(?:falta|faltan|queda|quedan|resta|restan)\s+(?:para|hasta|pa)\b|"
            + @"how\s+(?:long|much\s+time|many\s+(?:hours|minutes|mins))\s+(?:(?:is|are|do\s+(?:i|we)\s+have|"
            + @"have\s+(?:i|we)\s+got)\s+)?(?:(?:left|remaining|remain|to\s+go)\s+)?(?:until|till|til|before|to)\b)",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    /// <summary>
    /// The clock some minutes or hours from now («¿qué hora será de aquí a doce minutos?», «what time will it be
    /// in 2 hours»). Same heads as the mind's semantic.temporal clock_later_asked; the two must not diverge.
    /// M87 (DEV-D v3r D-s025 «si pasan cuarenta minutos, ¿qué hora será?»): M85 taught the mind the span said as time
    /// that passes («si pasan», «cuando pasen», «pasados», «after», «if … pass») and not this twin; the mind's correct
    /// «Serán las 17:54.» (the clock forty minutes on) was then judged here as a plain clock request and filtered as
    /// missing_literal_fact for not stating the current one.
    /// </summary>
    internal static bool IsLaterClockRequest(string? text)
    {
        string folded = FoldForPolicy(text ?? string.Empty);
        return Regex.IsMatch(
                folded,
                @"\b(?:que\s+hora\s+(?:sera|seran|va\s+a\s+ser)|what\s+time\s+(?:will\s+it\s+be|is\s+it\s+going\s+to\s+be))\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            && Regex.IsMatch(
                folded,
                @"\b(?:de\s+aqui\s+a|dentro\s+de|en|in|after|(?:si|cuando)\s+(?:pasan|pasen|transcurren|transcurran)"
                + @"|pasad[oa]s|(?:if|when)(?:\s+another)?)\s+(?:[a-z0-9]+\s+){0,3}(?:minutos?|horas?|minutes?|hours?)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

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

        // No family at all was named: the reply carries only the action the
        // person themself asked for, which is not a proposal of its own.
        return !coveredFamilyNamed && !SharesCatalogActionVerb(user, said);
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

        // Uso real 2026-09-23 «súbele un poco»: the bare clitic order is the
        // volume (the mind reads it so and asks the amount); naming the volume
        // in that question is the person's own request, not an offer.
        if (FamilyNamed(family, "volumen", "audio")
            && Regex.IsMatch(user, @"^[\s¿?¡!]*(?:sub[ei]le|bajale|aumentale)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            return true;
        }

        // tanda-02 (turn the music down a little, in spanglish): turning the music
        // or the sound up or down is its volume. The mind asked whether to lower
        // the music's volume, the family read as an offer of its own, and the
        // reworded question invented a second option nobody named.
        if (FamilyNamed(family, "volumen", "audio")
            && Regex.IsMatch(user, @"\b(?:musica|music|sonido|sound|cancion|song)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            && Regex.IsMatch(user,
                @"\b(?:turn|baja|bajale|bajala|bajar|bajame|sube|subele|subela|subir|subime|lower|raise|louder|quieter)\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
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
        // Uso real 2026-09-23 «Volume más alto please»: the person's English word
        // for the same family; without it the clarification about the volume
        // they asked for read as a proposal of their own.
        ["volumen", "volume", "audio", "silencio", "mute", "salida predeterminada"],
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
    private static bool AsksForDeclaredImageSubject(string user, string folded, IReadOnlyList<string>? missingFields) =>
        missingFields is not null
        && missingFields.Contains("query")
        && AsksForVisualContent(user)
        && (folded.Contains('?', StringComparison.Ordinal) || folded.Contains('¿', StringComparison.Ordinal));

    /// <summary>
    /// The field a clarification draft declares as missing, for the reply
    /// checks that read the declared field («folder», «text», «query»).
    /// </summary>
    internal static IReadOnlyList<string>? DeclaredMissingFields(UserMessageDraft draft) =>
        HasRequiredInput(draft)
        && TryReadJson(draft.Source, out JsonElement root)
        && root.TryGetProperty("missingValue", out JsonElement missing)
        && missing.GetString() is { Length: > 0 } value
            ? [value]
            : null;

    private static bool AsksForDeclaredFolder(string folded, IReadOnlyList<string>? missingFields) =>
        missingFields is not null
        && missingFields.Contains("folder")
        && Regex.IsMatch(folded, @"\b(?:carpeta|directorio|folder|directory)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static bool AsksForDeclaredText(string folded, IReadOnlyList<string>? missingFields) =>
        missingFields is not null
        && missingFields.Contains("text")
        && (folded.Contains('?', StringComparison.Ordinal) || folded.Contains('¿', StringComparison.Ordinal))
        && Regex.IsMatch(folded, @"\b(?:texto|text|mensaje|message|palabras|words)\b",
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

    // M85 (DEV-D v3o D-p35-t1 «Has un análisis de FODA sobre la empresa Adidas… A la vez hazlo con la experiencia que
    // tendría un experto en marketing.»: the FODA the mind wrote was refused as ambiguous_without_question and the turn
    // asked back): a pointer with no object is the request only when it is (nearly) all the message, as the mind's
    // INTENT_AMBIGUOUS_ACTION reads it; «hazlo con la experiencia de…» inside a request that names the work is not.
    private static readonly string[] AmbiguousActionTokens =
        ["abreme eso", "abre eso", "cierra aquello", "open that", "close that",
            "hazlo", "do it", "do that", "haz eso", "open it", "close it"];

    private static bool LooksLikeAmbiguousAction(string user)
    {
        int words = user.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).Length;
        return AmbiguousActionTokens.Any(token =>
            words <= token.Split(' ').Length + 3
            && Regex.IsMatch(
                user,
                @"(?<![\p{L}\p{N}])" + Regex.Escape(token) + @"(?![\p{L}\p{N}])",
                RegexOptions.CultureInvariant));
    }

    private static bool LooksLikeKnowledgeQuestion(string user) =>
        ContainsAny(user, UserMessagePhrases.KnowledgeAsks);

    /// <summary>
    /// A long statement with no question mark whose knowledge-ask words never
    /// lead a clause («that is why…», «what they told me»): overheard or thought
    /// aloud, not a question to answer.
    /// </summary>
    private static bool IsLongDeclarativeStatement(string user)
    {
        if (user.Contains('?', StringComparison.Ordinal) || user.Contains('¿', StringComparison.Ordinal))
        {
            return false;
        }
        int words = user.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length;
        if (words < 15)
        {
            return false;
        }
        foreach (string ask in UserMessagePhrases.KnowledgeAsks)
        {
            int index = user.IndexOf(ask, StringComparison.Ordinal);
            while (index >= 0)
            {
                string before = user[..index].TrimEnd();
                if (before.Length == 0 || ".,;:!(".Contains(before[^1]))
                {
                    return false;
                }
                int space = before.LastIndexOf(' ');
                string lead = space >= 0 ? before[(space + 1)..] : before;
                if (lead is "y" or "e" or "o" or "pero" or "and" or "or" or "but" or "decime" or "dime" or "contame"
                    or "cuentame" or "explicame" or "explica" or "sabes" or "sabe" or "explain" or "know" or "baxy" or "me")
                {
                    return false;
                }
                index = user.IndexOf(ask, index + 1, StringComparison.Ordinal);
            }
        }
        return true;
    }

    /// <summary>
    /// Greeting heads recognized on both sides of the boundary. The Python
    /// owner (`baxy_mind.semantic.request`) keeps the same list, and
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
                && !IsLaughter(word.Value)
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

    // Tanda 5 «¿estamos a mitad de semana?»: a quoted snippet «…lo que significa que estamos a un paso del fin de
    // semana» died as internal_code. «lo que significa que» is a connective, not the definition ask restated.
    private static bool LooksLikeRestatingDefinitionAsk(string folded) =>
        folded.Contains("significa exactamente", StringComparison.Ordinal)
        || folded.Replace("lo que significa", string.Empty, StringComparison.Ordinal)
            .Contains("que significa", StringComparison.Ordinal)
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

    // cien-37 030/040 «send flowers to Deimos»: any question at all used to
    // veto the reply, so a final that stated the limit and then offered help
    // in general died and the person was left with nothing. What must not
    // happen is asking ABOUT the thing that cannot be done (cien-36 060 «What
    // specific details do you need about shipping a piano to Charon?»), so the
    // interrogative sentence is what gets read. A reply that asks nothing about
    // the request must still say it cannot do it.
    private static bool AsksAboutTheOutOfWorldRequest(string user, string reply)
    {
        bool asks = false;
        foreach (string sentence in Regex.Split(reply, @"(?<=[.!?\u00bf])\s+"))
        {
            if (!sentence.Contains('?', StringComparison.Ordinal)
                && !sentence.Contains('\u00bf', StringComparison.Ordinal))
            {
                continue;
            }

            asks = true;
            string said = FoldForPolicy(sentence);
            foreach (Match word in Regex.Matches(FoldForPolicy(user), @"[a-z]{4,}"))
            {
                if (OutOfWorldQuestionStopWords.Contains(word.Value))
                {
                    continue;
                }

                if (said.Contains(word.Value, StringComparison.Ordinal))
                {
                    return true;
                }
            }
        }

        return asks && !StatesAnInability(FoldForPolicy(reply));
    }

    private static readonly HashSet<string> OutOfWorldQuestionStopWords =
        new(StringComparer.Ordinal)
        {
            "please", "could", "would", "there", "that", "this", "with", "para",
            "porfa", "favor", "quiero", "puedes", "podrias", "quieres",
        };

    private static bool StatesAnInability(string said) =>
        said.Contains("cannot", StringComparison.Ordinal)
        || said.Contains("can t", StringComparison.Ordinal)
        || said.Contains("can't", StringComparison.Ordinal)
        || said.Contains("no puedo", StringComparison.Ordinal)
        || said.Contains("outside what i do", StringComparison.Ordinal)
        || said.Contains("fuera de lo que", StringComparison.Ordinal)
        || said.Contains("no hago", StringComparison.Ordinal)
        || said.Contains("i do not do", StringComparison.Ordinal)
        || said.Contains("i don t do", StringComparison.Ordinal);

    private static bool LooksLikeOutOfWorldRequest(string user) =>
        AsksForAWorldAction(user)
        || AsksForVisualContent(user)
        || ContainsAnyWholeWord(
            user,
            ["marte", "mars", "jupiter", "saturn", "neptun", "pluton",
                "europa", "ganymede", "ganimedes", "calisto", "callisto",
                "triton", "ceres", "phobos", "deimos", "oberon", "rocket",
                // BUILD1143 made these whole words («martes» is not «marte»);
                // the plural stays out of this world (Fase 1 grupo F).
                "bitcoin", "bitcoins", "titan",
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

        // tanda-02b t28 «¡ave, cesar!» → «¡Ave, César! ¿Cómo estás?»: returning a
        // salutation in its own exclamation and then asking something else is
        // an answer; only a question that carries the request echoes it.
        // A7 E7 (DEV-A3 t201 «new address» → «What is the new address?»): a request that is only a short noun
        // phrase is answered by asking its value; a question that opens with an interrogative word asks for new
        // data and does not hand the request back.
        bool nounPhraseRequest = asked.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= 3;
        foreach (string sentence in Regex.Split(reply, @"(?<=[.!?…])\s+"))
        {
            string folded = FoldForPolicy(sentence);
            if (sentence.Contains('?', StringComparison.Ordinal)
                && folded.Contains(asked, StringComparison.Ordinal)
                && !(nounPhraseRequest && AsksForAValue(folded)))
            {
                return true;
            }
        }

        return false;
    }

    private static bool AsksForAValue(string foldedSentence) =>
        Regex.IsMatch(
            foldedSentence,
            @"^\s*[¿¡]?\s*(?:que|cual|cuales|cuando|donde|quien|what|which|when|where|who)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private static bool GreetsOutOfWorldTarget(string folded) =>
        Regex.IsMatch(
            folded,
            @"\b(?:hi|hey|hello|hola)[, ]+(?:saturno?|marte|mars|jupiter|neptuno?)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    // Past-tense own failure: «no pude», «no logré», «I couldn't», «failed to».
    // A present limit («no puedo», «I cannot») is not an attempt.
    // M85: twins of semantic.conversation.without_quoted_speech and ends_asking_the_person.
    private static readonly Regex QuotedSpeech = new(
        "\"[^\"\\n]*\"|«[^»\\n]*»|“[^”\\n]*”", RegexOptions.CultureInvariant);

    internal static string WithoutQuotedSpeech(string reply) => QuotedSpeech.Replace(reply ?? string.Empty, " ");

    private static readonly Regex SayingInability = new(
        @"\b(?:can\s*not|can['’]t|cannot|no\s+(?:te\s+|le\s+|les\s+)?puedo)\s+(?:\w+\s+)?"
        + @"(?:recommend|suggest|say|tell|know|choose|pick|guess|decide|recomendar\w*|sugerir\w*|decir\w*|saber|"
        + @"elegir\w*|adivinar\w*|decidir\w*)\b",
        RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);

    internal static string WithoutSayingInability(string reply) =>
        SayingInability.Replace(FoldForPolicy(reply ?? string.Empty), " ");

    internal static bool EndsAskingThePerson(string reply) =>
        Regex.IsMatch((reply ?? string.Empty).Trim(), "\\?[\\s\"»”')]*$", RegexOptions.CultureInvariant);

    private static bool ClaimsFailedAttempt(string reply) =>
        Regex.IsMatch(
            FoldForPolicy(reply),
            @"\b(?:no\s+(?:pude|logr[eé]|consegu[ií]|complet[eé]|realic[eé])|(?:i\s+)?(?:couldn['’]t|could\s+not)|failed\s+to)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    // M75 (DEV-D v3l D-p02-t2 «¿Serías capaz de hacer foto ahora?»): whether BAXY is able to do something is answered
    // yes or no, and «No puedo hacer fotos» is that answer. Twin of semantic.conversation.asks_whether_able.
    private static bool AsksWhetherAble(string user) =>
        Regex.IsMatch(
            user,
            @"\b(?:eres|seras|serias|sos|serian|son)\s+(?:\w+\s+)?capa(?:z|ces)\s+de\b"
            + @"|\btienes\s+(?:la\s+)?(?:capacidad|posibilidad)\s+de\b"
            + @"|\b(?:are|were)\s+you\s+(?:\w+\s+)?(?:able|capable)\s+(?:to|of)\b"
            + @"|\bwould\s+you\s+be\s+(?:able|capable)\s+(?:to|of)\b"
            + @"|\bdo\s+you\s+have\s+the\s+(?:ability|capacity)\s+to\b",
            RegexOptions.CultureInvariant);

    // M75 (DEV-D v3l D-w15-t3 «traducelo al ingles que es para mi jefa»): a translation of something only pointed at
    // has no text to translate, so asking which is the reply. Twin of semantic.conversation.translation_without_its_text.
    private static bool TranslationWithoutItsText(string userText)
    {
        string text = userText ?? string.Empty;
        return Regex.IsMatch(
                FoldForPolicy(text),
                @"\btraduc(?:e|i|ir)(?:me|nos|se)?(?:lo|la|los|las)\b"
                + @"|\btraduc(?:e|i|ir)(?:me|nos)?\s+(?:eso|esto|esa|ese|este|esta|aquello|lo\s+anterior)\b"
                + @"|\btranslate\s+(?:it|them|that|this|these|those)\b(?!\s+(?!(?:to|into|in|for|please)\b)[a-z])",
                RegexOptions.CultureInvariant)
            && !Regex.IsMatch(text, @"['‘“""«][^'’”""»]{2,40}['’”""»]", RegexOptions.CultureInvariant)
            && !text.Contains(':', StringComparison.Ordinal);
    }

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

    private static readonly string[] CatalogActionVerbs =
    [
        "cierra", "close", "abre", "open", "lanza", "launch", "borra",
        "delete", "silencia", "mute", "revisa", "muestra", "chequea",
        "check", "envia", "send", "traduce", "translate", "haz ",
        "hazlo", "do that", "do it",
    ];

    private static bool ContainsCatalogActionVerb(string user) =>
        ContainsAny(user, CatalogActionVerbs);

    // cien-36 027 «open that» → «What do you want me to open?»: the question
    // repeats the very verb the person used and names nothing else, so it
    // proposes no action of its own.
    private static bool SharesCatalogActionVerb(string user, string said)
    {
        foreach (string verb in CatalogActionVerbs)
        {
            if (said.Contains(verb, StringComparison.Ordinal)
                && user.Contains(verb, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

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

    // M108 (M107's report) twin of llm._CONTRACT_TOKENS: the report of a verified effect leaked the contract in shapes
    // the snake and dotted checks do not see («verified=true succeeded=true», «succeeded: true», «{"state": "off"}»,
    // «TARGET_NOT_FOUND», «0x80070005», «windowId»). Judged on the report of a result (status, error) only, once links
    // and mail addresses are out; a token the person wrote or the result observed is theirs.
    // Product names keep their spelling («Baxy.App», «iPhone», «macOS», «RTX 4060 Ti»).
    private static readonly Regex[] ContractTokens =
    [
        new(@"\b[A-Za-z_][A-Za-z0-9_]{2,}=\S", RegexOptions.CultureInvariant),
        new(@"\b[A-Za-z_][A-Za-z0-9_]{2,}\s*[:=]\s*(?:true|false|null)\b",
            RegexOptions.CultureInvariant | RegexOptions.IgnoreCase),
        new(@"\{\s*""[^""{}\n]{1,64}""\s*:|""[A-Za-z_][\w.-]{0,63}""\s*:\s*(?:true|false|null|-?\d|""|\{|\[)",
            RegexOptions.CultureInvariant),
        new(@"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", RegexOptions.CultureInvariant),
        new(@"\b0x[0-9A-Fa-f]{4,}\b", RegexOptions.CultureInvariant),
        new(@"\b[a-z]{2,}(?:[A-Z][a-z0-9]+)+\b", RegexOptions.CultureInvariant),
    ];

    private static readonly Regex LinkOrAddress = new(
        @"(?:\bhttps?://|\bwww\.)\S+|\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)+\b",
        RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);

    // What a result says about itself, never what it observed.
    private static readonly HashSet<string> ContractFieldsNotObserved = new(StringComparer.Ordinal)
    {
        "operation", "operations", "authority", "error", "errorCode", "code", "cause", "kind", "polarity",
        "diagnosticCode",
    };

    /// <summary>The report of a result names a contract token nobody said or observed (twin of
    /// llm.visible_reply_leaks_a_contract_token). A field named in prose before a colon («your open windows: …») is
    /// English, not the contract; only a field written with its value as the contract writes it is.</summary>
    internal static bool LeaksContractToken(string reply, string source, string? ownWords)
    {
        var observed = new StringBuilder();
        if (TryReadJson(source, out JsonElement root))
        {
            CollectObserved(root, string.Empty, 0, observed);
        }

        string own = string.Concat(observed.ToString(), "\n", ownWords).ToLowerInvariant();
        string judged = LinkOrAddress.Replace(reply ?? string.Empty, " ");
        return ContractTokens.Any(pattern => pattern.Matches(judged)
            .Any(found => !own.Contains(found.Value.ToLowerInvariant(), StringComparison.Ordinal)));
    }

    private static void CollectObserved(JsonElement value, string key, int depth, StringBuilder texts)
    {
        if (depth > 8 || ContractFieldsNotObserved.Contains(key))
        {
            return;
        }

        switch (value.ValueKind)
        {
            case JsonValueKind.String:
                string text = value.GetString() ?? string.Empty;
                if (text.TrimStart().StartsWith('{') && TryReadJson(text, out JsonElement decoded))
                {
                    CollectObserved(decoded, key, depth + 1, texts);
                    return;
                }

                texts.Append(text).Append('\n');
                break;
            case JsonValueKind.Object:
                foreach (JsonProperty property in value.EnumerateObject())
                {
                    CollectObserved(property.Value, property.Name, depth + 1, texts);
                }

                break;
            case JsonValueKind.Array:
                foreach (JsonElement child in value.EnumerateArray())
                {
                    CollectObserved(child, key, depth + 1, texts);
                }

                break;
        }
    }

    // M108 twin of llm.visible_reply_promises_the_act: a verified effect reported as a promise («Voy a hacerlo
    // enseguida.», «I'll do it right away», «Procederé a apagar el bluetooth.»). A sentence that opens (after a «sí»,
    // «claro», «ok»…) with a first-person act still to come is the promise; what a verified notice will do («te avisaré
    // a las 9», «I'll remind you») and a state left as it is («lo dejo así», «I'll keep it muted») are no promise.
    private const string PromiseLead =
        @"^[\s""'«“]*(?:(?:si|claro(?:\s+que\s+si)?|ok(?:ay|ey)?|vale|dale|listo|perfecto|bueno|bien|entendido|"
        + @"de\s+acuerdo|por\s+supuesto|sure|of\s+course|alright|all\s+right|got\s+it|no\s+problem|yes|yeah|okay)"
        + @"\s*[,.!:;—–-]*\s*)*";

    private const string PromiseClitic = @"(?:me|te|se|lo|la|le|los|las|les|nos)\s+";

    private const string PromiseSoon =
        @"(?:ahora\s+mismo|ya\s+mismo|enseguida|en\s+seguida|de\s+inmediato|inmediatamente|en\s+un\s+(?:momento|segundo|"
        + @"instante)|en\s+breve|right\s+away|right\s+now|in\s+a\s+(?:moment|second|sec))";

    private static readonly Regex SpanishPromise = new(
        PromiseLead + @"(?:(?:" + PromiseSoon + @"|ahora|ya)\s*,?\s*)?"
        + @"(?:me\s+(?:pongo\s+a|encargo|ocupo)\b|(?:" + PromiseClitic + @"){0,2}"
        + @"(?:(?:voy|vamos)\s+a\s+(?:" + PromiseClitic + @")?(?<act>\w+)|procedo\s+a\b|llevo\s+a\b|(?<word>\w+)))",
        RegexOptions.CultureInvariant);

    private static readonly Regex SpanishPromisePresent = new(
        PromiseLead + @"(?:" + PromiseSoon + @"\s*,?\s*(?:" + PromiseClitic + @"){1,2}\w+o\b|"
        + @"(?:" + PromiseClitic + @"){1,2}\w+o\s+" + PromiseSoon + @")",
        RegexOptions.CultureInvariant);

    private static readonly Regex EnglishPromise = new(
        PromiseLead + @"(?:" + PromiseSoon + @"\s*,?\s*)?"
        + @"(?:i'll|i\s+will|i\s+shall|i'm\s+going\s+to|i\s+am\s+going\s+to|i'm\s+about\s+to|i\s+am\s+about\s+to|"
        + @"let\s+me|we'll|we\s+will|let's\s+go|going\s+to|i'm\s+on\s+it|on\s+it)\b(?:\s+(?<act>\w+))?",
        RegexOptions.CultureInvariant);

    private static readonly Regex NotAPromisedAct = new(
        @"^(?:avis|record|notific|despert|alert|estar\b|seguir|qued|dej|manten|"
        + @"(?:remind|notify|let|alert|wake|ping|ring|be|keep|leave|stay|know|tell)\b)",
        RegexOptions.CultureInvariant);

    // Doing in general, besides each catalog act (OperationFloor.SpanishInfinitives): «lo haré», «procederé».
    private static readonly string[] SpanishPromiseVerbs =
    [
        "hacer", "proceder", "intentar", "encargar", "ocupar", "ir", "llevar", "mostrar", "ver", "terminar",
        "conseguir", "lograr", "arreglar", "resolver", "realizar", "completar",
    ];

    private static readonly Dictionary<string, string> SpanishFutureStems = new(StringComparer.Ordinal)
    {
        ["hacer"] = "har", ["poner"] = "pondr", ["decir"] = "dir", ["salir"] = "saldr", ["tener"] = "tendr",
        ["venir"] = "vendr", ["querer"] = "querr", ["saber"] = "sabr", ["deshacer"] = "deshar", ["rehacer"] = "rehar",
        ["reponer"] = "repondr",
    };

    private static readonly Lazy<HashSet<string>> SpanishPromisedFutures = new(() =>
    {
        var futures = new HashSet<string>(StringComparer.Ordinal);
        foreach (string verb in OperationFloor.SpanishInfinitives.Concat(SpanishPromiseVerbs))
        {
            if (verb == "dejar")
            {
                continue;
            }

            string stem = SpanishFutureStems.GetValueOrDefault(verb, verb);
            futures.Add(FoldForPolicy(stem + "é"));
            futures.Add(FoldForPolicy(stem + "emos"));
        }

        return futures;
    });

    /// <summary>A sentence of the reply promises an act instead of telling it done.</summary>
    internal static bool PromisesTheAct(string reply)
    {
        foreach (string part in Regex.Split((reply ?? string.Empty).Replace('’', '\''), @"[.!?;:\n¡¿]+"))
        {
            string sentence = Regex.Replace(FoldForPolicy(part), @"\s+", " ").Trim();
            if (sentence.Length == 0)
            {
                continue;
            }

            if (SpanishPromisePresent.IsMatch(sentence))
            {
                return true;
            }

            Match found = SpanishPromise.Match(sentence);
            if (found.Success)
            {
                if (found.Groups["act"].Success)
                {
                    if (!NotAPromisedAct.IsMatch(found.Groups["act"].Value))
                    {
                        return true;
                    }
                }
                else if (!found.Groups["word"].Success || SpanishPromisedFutures.Value.Contains(found.Groups["word"].Value))
                {
                    return true;
                }
            }

            found = EnglishPromise.Match(sentence);
            if (found.Success && (!found.Groups["act"].Success || !NotAPromisedAct.IsMatch(found.Groups["act"].Value)))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>A result the PC verified done: one operation verified and succeeded, or a completed mission.</summary>
    private static bool IsVerifiedEffect(string source)
    {
        if (!TryReadJson(source, out JsonElement root))
        {
            return false;
        }

        if (root.TryGetProperty("cause", out JsonElement cause) && cause.ValueKind == JsonValueKind.String
            && string.Equals(cause.GetString()?.Trim(), "mission_completed", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return root.TryGetProperty("operation", out JsonElement operation) && operation.ValueKind == JsonValueKind.String
            && !string.IsNullOrEmpty(operation.GetString())
            && root.TryGetProperty("verified", out JsonElement verified) && verified.ValueKind == JsonValueKind.True
            && root.TryGetProperty("succeeded", out JsonElement succeeded) && succeeded.ValueKind == JsonValueKind.True;
    }

    private static bool IsConversationSituation(string source) =>
        TryReadJson(source, out JsonElement root)
        && root.TryGetProperty("kind", out JsonElement kind) && kind.ValueKind == JsonValueKind.String
        && kind.GetString() == "conversation";

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
        // MAIL1861: an e-mail address is what a mail reply has to name («Se envió
        // … a autor@example.com»); its domain is not a dotted
        // operation name. Only the address span is excluded, so codes elsewhere
        // still cross the checks below.
        withoutWebHosts = Regex.Replace(withoutWebHosts,
            @"\b[a-z0-9._%+-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}\b",
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
            // Tanda 6c «haz una carcajada cuando quieras» → «¡Jajajaja!» died here and the shell composed «Claro,
            // te doy una carcajada cuando quieras.»: a laugh written out repeats its syllable by nature.
            if (IsLaughter(word))
            {
                continue;
            }

            // WEB1449: a doubled two-letter tail is ordinary morphology
            // («contienen», «intereses», «preparar», «succeeded»), not a
            // stutter; the measured stutters («llamarar») are listed by
            // token above. Only a doubled tail of three or more letters counts.
            for (int size = 3; size <= 4 && size * 2 <= word.Length; size++)
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

    // «jajajaja», «hahaha», «jejeje», «muajajaja»: one laughing syllable repeated.
    private static bool IsLaughter(string word) =>
        Regex.IsMatch(word, @"^(?:mu|bu)?a?(?:[jh][aeiou]){2,}[jh]?$", RegexOptions.CultureInvariant);

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

    // M50 (v3a-final F-w07, F-w12, F-w14, F-p10): code asked for in the conversation is content, not an internal
    // code of the product. Twin of semantic.conversation.asks_for_code: a verb of writing or giving and a piece of
    // code, making something in a named programming language, or carrying code to another language; asked now or in
    // one of the earlier requests the shell keeps.
    private const string CodeLanguageName =
        @"(?:python|javascript|js|typescript|java|c\+\+|c#|csharp|rust|kotlin|swift|php|ruby|sql|bash|powershell|html|"
        + @"css|matlab|scala|lua|dart|haskell|golang|perl|vba)(?![\w+#])";
    private const string CodeWritingVerb =
        @"(?:escrib\w*|haz|hazme|haceme|hacer|hacerme|haces|crea|crear|creame|creas|genera\w*|dame|damelo|damela|"
        + @"pasa\w*|pasas|mostra\w*|muestra\w*|ensena\w*|arma\w*|programa\w*|codea\w*|codifica\w*|conviert\w*|"
        + @"traduc\w*|reescrib\w*|write|make|create|generate|give|show|build|code|convert|translate|rewrite|port)";
    private const string CodePieceNoun =
        @"(?:scripts?|scriptcitos?|funcion(?:es|cita)?|functions?|algoritmos?|algorithms?|snippets?|quer(?:y|ies)|"
        + @"consultas?\s+(?:de\s+)?sql|codigos?|code|regex|one-?liners?|metodos?|methods?|"
        + @"programas?\s+(?:en|in|para|que)|programs?\s+(?:in|that)|clases?\s+(?:en|in))(?![\w])";
    private static readonly Regex CodeAsked = new(
        @"\b" + CodeWritingVerb + @"\b.{0,60}\b" + CodePieceNoun + "|"
        + @"\b" + CodeWritingVerb + @"\b.{0,160}\b(?:en|in|a|to|into|para|for|con|with|using|usando)\s+(?:el\s+|the\s+)?"
        + @"(?:lenguaje\s+(?:de\s+programacion\s+)?)?" + CodeLanguageName + "|"
        + @"^[\s¿¡]*(?:y\s+|and\s+)?(?:ahora\s+|now\s+)?(?:en|in)\s+" + CodeLanguageName + @"[\s?!.]*$|"
        // M85 (DEV-D v3o D-w20-t1 «estoy haciendo un script en Python y necesito leer un CSV y sacar el promedio de la
        // columna price, can you write it?»: the mind wrote the script and this twin refused it as internal_code, ⚠):
        // the piece of code described first and asked for after with a pronoun, as M81 already reads it in the mind.
        + @"\b" + CodePieceNoun + @".{0,240}\b(?:(?:write|code|make)\s+(?:it|this|that|one)|"
        + @"(?:escrib[ei]|haz|hace|codea)(?:lo|la|melo|mela)|"
        + @"(?:lo|la|me\s+lo|me\s+la)\s+(?:puedes|podes|podrias|podras)\s+(?:escribir|hacer|codear))\b",
        RegexOptions.CultureInvariant);

    internal static bool AsksForCode(string? userText, string? priorUserText) =>
        new[] { userText, priorUserText }.Any(static said =>
            !string.IsNullOrWhiteSpace(said)
            && CodeAsked.IsMatch(string.Join(" ", FoldForPolicy(said).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries))));

    // Twin of llm.requested_code_prose: the reply without its fenced or inline code and without its lines of code.
    private static readonly Regex CodeFence = new(@"```[\s\S]*?(?:```|\z)|`[^`\n]+`", RegexOptions.CultureInvariant);
    private static readonly Regex CodeLine = new(
        @"^(?:[ \t]{2,}\S.*"
        + @"|\s*(?:def|class|function|const|let|var|return|import|elif|except|catch|public|private|static|async|await|"
        + @"fn|func|package|using|#include)\b.*"
        + @"|\s*from\s+[\w.]+\s+import\b.*"
        + @"|\s*(?:for|while|if|switch)\s*\(.*"
        + @"|\s*(?:print|console\.\w+|document\.\w+|System\.out\.\w+)\s*\(.*"
        + @"|\s*(?:SELECT|FROM|WHERE|ORDER BY|GROUP BY|HAVING|LIMIT|INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE|"
        + @"(?:LEFT |RIGHT |INNER |OUTER )?JOIN|VALUES|UNION)\b.*"
        + @"|\s*[\w.\[\]]+\s*(?:[-+*/%]|\?\?)?=\s*[^=\s].*"
        + @"|.*[{};]\s*|\s*[}\])].*)$",
        RegexOptions.CultureInvariant);

    internal static string RequestedCodeProse(string reply)
    {
        string unfenced = CodeFence.Replace(reply ?? string.Empty, " ");
        return string.Join(
            "\n",
            unfenced.Replace("\r\n", "\n", StringComparison.Ordinal).Split('\n')
                .Where(static line => !CodeLine.IsMatch(line))).Trim();
    }

    // v3a-final F-s007 «…no la activan yo», F-s077 «No leeo SMS»: BAXY's «yo» with a plural verb, or a first person
    // made from an «-eer» stem plus «-o». Twin of llm.visible_reply_breaks_first_person.
    private static bool BreaksFirstPerson(string reply)
    {
        string folded = FoldForPolicy(reply);
        return Regex.IsMatch(folded, @"\b(?:lo|la|los|las|le|les)\s+[a-z]{2,}(?:an|en)\s+yo\b", RegexOptions.CultureInvariant)
            || Regex.IsMatch(folded, @"\b[a-z]+eeo\b", RegexOptions.CultureInvariant);
    }

    // v3a-final F-s074/F-s091 «…access to the person's Outlook calendar or mail»: the reply speaks to the person,
    // never about them. Twin of llm.visible_reply_speaks_of_the_person.
    private static bool SpeaksOfThePerson(string reply, string? userText)
    {
        Match found = Regex.Match(
            FoldForPolicy(reply),
            @"\b(?:the|this)\s+(?:person|user)(?:'s|’s|s')(?!\w)|"
            + @"\b(?:calendario|agenda|correos?|mails?|cuentas?|archivos?|carpetas?|tareas?|notas?|recordatorios?|listas?|"
            + @"mensajes?|datos|musica|biblioteca|outlook|pc|equipo|computadora)\s+(?:\w+\s+)?de\s+la\s+persona\b",
            RegexOptions.CultureInvariant);
        return found.Success
            && !FoldForPolicy(userText ?? string.Empty).Contains(found.Value, StringComparison.Ordinal);
    }

    public static string WithDiagnosticCode(string text, UserMessageDraft draft)
    {
        _ = draft;
        // El código estable queda disponible para diagnóstico interno; nunca
        // forma parte del mensaje que recibe una persona.
        return text.Trim();
    }

    // Owner script «Por dios, odio estos fallos» → «Entiendo que la frustración por
    // los fallos es inmensa»: the person's «fallos», answered back, claims no
    // failure of BAXY's. What is left once they are removed is judged as always.
    // Twin of llm._failure_word_is_the_persons.
    private const string EchoedFailures = @"\b(?:los|estos|esos|tantos|tus|sus)\s+fallos\b";

    private static bool OnlyEchoesThePersonsFailures(string reply, string userText)
    {
        if (!Regex.IsMatch(FoldForPolicy(userText ?? string.Empty), @"\bfallos\b", RegexOptions.CultureInvariant))
        {
            return false;
        }
        string rest = Regex.Replace(reply, EchoedFailures, string.Empty,
            RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
        // Independent review B3: a cause after the person's «fallos» is a claim of BAXY's.
        if (Regex.IsMatch(FoldForPolicy(rest), @"\b(?:se\s+deben?|debid[oa]s?|porque|ya\s+que|because|due\s+to|caused)\b",
                RegexOptions.CultureInvariant))
        {
            return false;
        }
        return !string.Equals(rest, reply, StringComparison.Ordinal) && !LooksLikeFailure(rest);
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
        // M93 (held-out v3v t10): «El Bloc de notas no pudo abrirse» is «no se pudo abrir»; twin of llm._asserts_failure.
        || Regex.IsMatch(assertedFailures,
            @"\b(?:fallos?|failed)\b|\bno\s+(?:encontre|se\s+(?:pudo|pudieron|encontro|encontraron))\b"
            + @"|\bno\s+pud(?:o|ieron)\s+[a-z]+(?:arse|erse|irse)\b",
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
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
        // H0714 «apagá la computadora», H0401 «reiniciá la PC»: «Windows no
        // aceptó la solicitud de apagado, por lo que el PC sigue encendido» es
        // un fallo dicho entero y bien. Como ningún marcador lo reconocía, la
        // respuesta fiel se leía como si invirtiera el resultado y el turno
        // moría sin publicar nada. Que algo no se acepte o se rechace es
        // afirmar que no ocurrió. El gemelo de esta lista vive en
        // _FAILURE_MARKERS de la mente y cambia con ella.
        || Regex.IsMatch(
            normalized,
            @"\b(?:no\s+(?:la\s+|lo\s+)?acepto|no\s+fue\s+aceptad[ao]|rechazo|rechazad[ao]|refused|rejected)\b"
            + @"|\b(?:did\s*not|didn[’']?t|does\s*not|doesn[’']?t|was\s+not|wasn[’']?t)\s+accept(?:ed)?\b",
            RegexOptions.CultureInvariant)
        // Owner's test 2026-09-21 (turn 205): «ya estaba silenciado, así que no
        // cambié nada» states the failure entire — nothing changed. Twin of the
        // same marker in the mind's _FAILURE_MARKERS.
        || Regex.IsMatch(
            normalized,
            @"\b(?:no\s+cambi[oe]\s+nada|no\s+se\s+cambio\s+nada|no\s+hubo\s+cambios?|no\s+hubo\s+ningun\s+cambio|nothing\s+(?:was\s+)?changed|no\s+change\s+was\s+made)\b"
            + @"|\b(?:no\s+se\s+realizo|no\s+se\s+hizo|no\s+fue\s+posible|no\s+realice|was\s+not\s+(?:done|performed|carried\s+out)|could\s+not\s+be\s+(?:done|performed))\b"
            + @"|\b(?:no\s+se\s+(?:guardo|bajo|descargo)\s|nada\s+se\s+guardo|nada\s+fue\s+guardad[oa]|no\s+guarde\s+nada|nothing\s+was\s+saved|was\s+not\s+saved)\b"
            // PPTX2051: «the opening is not confirmed» / «cannot be verified» say the failure entire.
            + @"|\b(?:(?:is|was|were|could)\s+not\s+(?:be\s+)?(?:confirmed|verified)|cannot\s+be\s+(?:confirmed|verified)|not\s+confirmed|unconfirmed|unverified|no\s+(?:esta|quedo|queda)\s+confirmad[oa]|sin\s+confirmar)\b"
            // WINGET2083: «no se puede confirmar», «no se confirma la instalación».
            // Tanda 9: «no se puede verificar si hay correos nuevos» (twin of the mind's _FAILURE_MARKERS).
            + @"|\b(?:no\s+(?:se\s+)?(?:puede|pude|puedo|podemos|logro)\s+(?:confirmar|verificar|comprobar)|no\s+se\s+(?:confirma|verifica|comprueba))\b"
            // A7 E6 (FINAL t305 «No he podido subir el volumen… el cambio no se confirmó»): the mind accepted it and
            // this twin read it as a reversed result. Same markers as the mind's _FAILURE_MARKERS.
            + @"|\bno\s+se\s+(?:ha\s+|han\s+)?(?:confirm|verific|comprob)(?:o|ado|ada|aron)\b"
            + @"|\bno\s+(?:esta|quedo)\s+(?:verificad|comprobad)[oa]\b|\bno\s+estoy\s+segur[oa]\s+de\s+que\b"
            + @"|\bno\s+(?:he|hemos)\s+podido\b|\b(?:haven[’']?t|have\s+not)\s+been\s+able\b"
            // M60 (DEV-D p25-t1 v3c «I checked the weather service for Martinez, but it did not respond, so no
            // forecast was available»): the mind's _FAILURE_MARKERS read a source that did not respond, or a thing
            // not found, as the failure told; this twin read it as a reversed result.
            + @"|\b(?:did\s+not|didn[’']?t)\s+(?:respond|find)\b|\bno\s+responde\b",
            RegexOptions.CultureInvariant);
    }

    private static bool AttributesBaxyActionToUser(string source, string result)
    {
        // M60 (DEV-D s024 q4 «Añade un iPhone a mi lista de deseos que hice la semana pasada»): structured facts
        // carry BAXY's act as the operation, not as a first-person verb, so the verb found there was the person's own
        // («details»: «…que hice la semana pasada») and «la lista que creaste la semana pasada» died as wrong_actor.
        // RequiredBaxyActions reads no verb from structured facts either; the mind's twin (action_attributed_to_user)
        // judges the verified effect told as the person's.
        if (IsStructuredFacts(source))
        {
            return false;
        }

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
        // Owner's test 2026-09-21 (turn 205): «Tu micrófono está activo de nuevo»
        // reports the observed unmute by naming the microphone, not a mute word.
        return !ContainsAny(
            folded,
            ["volumen", "volume", "silenci", "muted", "unmuted", "mute",
                "audio", "altavoc", "microfono", "microphone", " mic "]);
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

    // Tanda 5 «¿estamos a mitad de semana?»: which part of the week today is asks for the weekday and the date.
    // The same words as the mind's semantic.network.WEEK_PERIOD; the two must not diverge.
    private const string CalendarWeekPeriod =
        @"(?:(?:el|la|the)\s+)?(?:(?:mitad|medio|mediados|principio|inicio|comienzo|final|fin)\s+de\s+(?:la\s+)?semana|"
        + @"finde|(?:middle|start|beginning|end)\s+of\s+the\s+week|mid-?\s?week|weekend)";

    // Tanda 3 «¿estamos a enero o febrero?» was answered «Son 02:54.»: a calendar unit, a month or weekday
    // name (not the English «may») or «a cuántos estamos» asks for the date. The same words as the mind's
    // semantic.network.asks_calendar_part; the two must not diverge.
    private static readonly Regex CalendarPartAsked = new(
        @"\b(?:d[ií]a(?:\s+de\s+la\s+semana)?|fecha|mes|a[ñn]o|day(?:\s+of\s+the\s+week)?|date|month|year|weekday|"
        + "enero|january|febrero|february|marzo|march|abril|april|mayo|junio|june|julio|july|agosto|august|"
        + "septiembre|setiembre|september|octubre|october|noviembre|november|diciembre|december|"
        + @"lunes|monday|martes|tuesday|mi[ée]rcoles|wednesday|jueves|thursday|viernes|friday|s[áa]bado|saturday|"
        + @"domingo|sunday|a\s+cu[áa]ntos\s+estamos|" + CalendarWeekPeriod
        // Tanda 6: a year («¿estamos en 2025?») and a day of the month («¿hoy es 24?») asked.
        + @"|(?:19|20)\d\d|hoy\s+es\s+(?:el\s+)?\d{1,2}|estamos\s+a\s+\d{1,2}|is\s+(?:it|today)\s+the\s+\d{1,2})\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    // Tanda 6 «¿sabes qué días fueron el último fin de semana?»: a day counted from today (mañana, ayer, el lunes
    // pasado, el próximo fin de semana, dentro de diez días, two days ago) is the calendar too. The mind computes
    // those days from the observed date and checks every one (semantic.network.relative_calendar_days,
    // llm._misses_calendar_facts); here they only mean that today's date is not the answer.
    private const string CalendarNamedDay =
        @"(?:fin\s+de\s+semana|finde|weekend|lunes|monday|martes|tuesday|mi[ée]rcoles|wednesday|jueves|thursday|"
        + @"viernes|friday|s[áa]bado|saturday|domingo|sunday)";

    private static readonly Regex RelativeCalendarDay = new(
        @"\b(?:(?<!\b(?:la|esta)\s)ma[ñn]ana|tomorrow|ayer|yesterday|anteayer|antier|"
        + @"day\s+(?:after\s+tomorrow|before\s+yesterday)|"
        + @"(?:[úu]ltimo|pasado|anterior|pr[óo]ximo|siguiente)\s+" + CalendarNamedDay + "|"
        + CalendarNamedDay + @"\s+(?:pasado|anterior|que\s+viene|pr[óo]ximo)|"
        + @"(?:last|next|previous|past|coming)\s+" + CalendarNamedDay + "|"
        + @"(?:hace|dentro\s+de|en)\s+\S+\s+d[íi]as|in\s+\S+\s+days|\S+\s+days\s+ago)\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    internal static bool AsksCalendarDate(string? userText) => AsksCalendarPart(userText);

    private static bool AsksCalendarPart(string? userText) =>
        CalendarPartAsked.IsMatch(userText ?? string.Empty) || RelativeCalendarDay.IsMatch(userText ?? string.Empty);

    // Tanda 4c «¿qué mes sale ahora mismo en el calendario de mi casa?» → «Este mes es septiembre.» was rejected
    // for lacking the day: a day, date, weekday, number or «a cuántos estamos» asks for the whole date; otherwise
    // the month and/or the year asked is the answer, and any day stated is a guess. The same reading as the mind's
    // semantic.network.calendar_parts_asked; the two must not diverge. Tanda 6: a year in digits asks the year.
    private static readonly Regex CalendarDayAsked = new(
        @"\b(?:d[ií]a|fecha|day|date|weekday|lunes|monday|martes|tuesday|mi[ée]rcoles|wednesday|jueves|thursday|"
        + @"viernes|friday|s[áa]bado|saturday|domingo|sunday|a\s+cu[áa]ntos\s+estamos|" + CalendarWeekPeriod
        + @")\b|(?<!\d)\d{1,2}(?!\d)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static readonly Regex CalendarYearAsked = new(
        @"\b(?:a[ñn]o|year|(?:19|20)\d\d)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    // Tanda 6b «¿hoy es lunes?» → «No, hoy es jueves.» died three times for lacking the day of the month: a weekday,
    // the weekday unit or a part of the week asked, with no day, date, number, month or year, is answered by the
    // observed weekday; a date said with it must still be the observed one. The same reading as the mind's
    // semantic.network.calendar_parts_asked («weekday»); the two must not diverge.
    private const string CalendarWeekdayUnit = @"(?:d[ií]a\s+de\s+la\s+semana|day\s+of\s+the\s+week)";

    private static readonly Regex CalendarWeekdayAsked = new(
        @"\b(?:" + CalendarWeekdayUnit + "|weekday|lunes|monday|martes|tuesday|mi[ée]rcoles|wednesday|jueves|"
        + @"thursday|viernes|friday|s[áa]bado|saturday|domingo|sunday|" + CalendarWeekPeriod + @")\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static readonly Regex CalendarBeyondWeekday = new(
        @"\b(?:d[ií]a|fecha|day|date|a\s+cu[áa]ntos\s+estamos)\b|(?<!\d)\d{1,4}(?!\d)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    // Indexed by DayOfWeek.
    private static readonly string[][] CalendarWeekdayNames =
    [
        ["domingo", "sunday"], ["lunes", "monday"], ["martes", "tuesday"], ["mi[ée]rcoles", "wednesday"],
        ["jueves", "thursday"], ["viernes", "friday"], ["s[áa]bado", "saturday"],
    ];

    private static bool CalendarWeekdayOnlyAsked(string user) =>
        CalendarWeekdayAsked.IsMatch(user)
        && !CalendarBeyondWeekday.IsMatch(Regex.Replace(user, @"\b" + CalendarWeekdayUnit + @"\b", " ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant));

    private static readonly string[][] CalendarMonthNames =
    [
        ["enero", "january"], ["febrero", "february"], ["marzo", "march"], ["abril", "april"],
        ["mayo", "may"], ["junio", "june"], ["julio", "july"], ["agosto", "august"],
        ["septiembre", "setiembre", "september"], ["octubre", "october"], ["noviembre", "november"],
        ["diciembre", "december"],
    ];

    // The months named in a text; the English «may» counts only as the capitalised month, never the modal.
    private static HashSet<int> CalendarMonthsNamed(string text, bool asked)
    {
        HashSet<int> named = [];
        for (int index = 0; index < CalendarMonthNames.Length; index++)
        {
            foreach (string name in CalendarMonthNames[index])
            {
                bool matched = name == "may"
                    ? !asked && Regex.IsMatch(text, @"\bMay\b", RegexOptions.CultureInvariant)
                    : Regex.IsMatch(text, @"\b" + name + @"\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (matched)
                {
                    named.Add(index + 1);
                }
            }
        }

        return named;
    }

    private static bool PreservesObservedDate(string source, string result, string? userText)
    {
        string user = userText ?? string.Empty;
        if (!TryDerivedLocalMoment(source, out DateTimeOffset local) || RelativeCalendarDay.IsMatch(user))
        {
            return true;
        }

        bool monthAsked = CalendarMonthsNamed(user, asked: true).Count > 0
            || Regex.IsMatch(user, @"\b(?:mes|month)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        bool yearAsked = CalendarYearAsked.IsMatch(user);
        bool weekdayOnly = !(monthAsked || yearAsked) && CalendarWeekdayOnlyAsked(user);
        bool dateAsked = !weekdayOnly && (CalendarDayAsked.IsMatch(user) || !(monthAsked || yearAsked));

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
            if (!sameDate || !(dateAsked || weekdayOnly))
            {
                return false;
            }
        }

        if (dateAsked)
        {
            return found;
        }

        if (weekdayOnly)
        {
            return CalendarWeekdayNames[(int)local.DayOfWeek].Any(name => Regex.IsMatch(result, @"\b" + name + @"\b",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant));
        }

        HashSet<int> months = CalendarMonthsNamed(result, asked: false);
        HashSet<string> years = Regex.Matches(result, @"(?<!\d)\d{4}(?!\d)", RegexOptions.CultureInvariant)
            .Select(static match => match.Value).ToHashSet(StringComparer.Ordinal);
        return (!monthAsked || months.SetEquals([local.Month]))
            && (!yearAsked || years.SetEquals([local.Year.ToString(CultureInfo.InvariantCulture)]));
    }

    private static bool InventedVolume(string source, string result, string? userText = null)
    {
        string folded = FoldForPolicy(result);
        if (userText is not null
            && ContainsAny(FoldForPolicy(userText), ["volumen", "volume"]))
        {
            // AUDIO1577 «subí el volumen y decime qué fecha es»: the final reports
            // the date and ends by asking how much to change the volume. The
            // question names the volume the person asked about; it states no
            // level. Only the sentences before that question can invent one.
            folded = FoldForPolicy(WithoutTrailingQuestion(result));
        }
        if (!ContainsAny(folded, ["volumen", "volume", " muted", "silenci"]))
        {
            return false;
        }

        if (!IsStructuredFacts(source))
        {
            return true;
        }

        // ctx-dueno-04 (2026-09-22, «Dime algo» → a Wikipedia snippet about a
        // tsunami's «volumen de agua»): a volume word the observed data carries
        // is reported, not invented.
        string foldedSource = FoldForPolicy(source);
        if (ContainsAny(foldedSource, ["volumen", "volume"]))
        {
            return false;
        }

        return !source.Contains("\"level\"", StringComparison.Ordinal)
            && !source.Contains("\"muted\"", StringComparison.Ordinal)
            && !source.Contains("\"volumePercent\"", StringComparison.Ordinal)
            // Owner's test 2026-09-21 (turn 205): the typed cause of the failure
            // («microphone_already_muted») is the mute state the final names.
            && !source.Contains("\"microphone_already_", StringComparison.Ordinal);
    }

    private static string WithoutTrailingQuestion(string result)
    {
        string trimmed = result.TrimEnd();
        if (!trimmed.EndsWith('?'))
        {
            return result;
        }

        int cut = trimmed.LastIndexOfAny(['.', '!', '?'], Math.Max(0, trimmed.Length - 2));
        return cut < 0 ? string.Empty : trimmed[..(cut + 1)];
    }

    private static bool InventedExtraClock(string source, string result, string? userText)
    {
        if (!TryDerivedLocalClock(source, out string hhmm))
        {
            return false;
        }

        // M63: a clock the person named (the alarm to move) is not another reading of this PC's clock.
        HashSet<(int Hour, int Minute)> named = PersonNamedClocks(userText);
        foreach (Match match in MatchClockTokens(result))
        {
            if (!ClockAppears(match.Value, hhmm)
                && !named.Contains((
                    int.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture) % 12,
                    int.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture))))
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
        // The dump is this machine's interface list («24 interfaces conectadas, 14 de ellas son ethernet»), the
        // same two marks the mind's composer rejects. «interfaces» alone is ordinary vocabulary: tanda 6 «¿Es
        // posible la herencia múltiple en Java?» lost «…mediante la herencia de interfaces» to it twice.
        string said = FoldForPolicy(reply);
        if (!ContainsAny(said, ["ethernet", "interfaces conectadas"]))
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

    private static bool InventedClock(string source, string result, string? userText)
    {
        if (TryDerivedLocalClock(source, out _) || ContainsClockPattern(source))
        {
            return false;
        }

        // M63 (v3f-final F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»): the failure carried no
        // clock and «no estaba configurada para las 8:00 … ¿la establezco para las 9:00?» died as invented. A clock
        // the person named is theirs to hear back, in any equivalent form; the mind judges the same
        // (llm._failure_invents_a_clock).
        HashSet<(int Hour, int Minute)> named = PersonNamedClocks(userText);
        foreach (Match match in ReplyClockTokens.Matches(result))
        {
            int hour = int.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
            int minute = int.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture);
            if (!named.Contains((hour % 12, minute)))
            {
                return true;
            }
        }

        return false;
    }

    // «8:00», «08:00», «8:00 a. m.», «20:00» in the reply; the hour is compared on the twelve-hour dial, since the
    // part of the day may be said on either side and a person's «las 8» is the reply's «20:00» as well.
    private static readonly Regex ReplyClockTokens = new(
        @"(?<!\d)(\d{1,2}):(\d{2})(?!\d)",
        RegexOptions.CultureInvariant);

    // The clocks the person named: «8:00», «08:00», «8:00 a. m.», «8 am», «las 8 (de la mañana)», «at 8». The twin
    // of the mind's semantic.temporal.spoken_clocks, read on the twelve-hour dial.
    private static readonly Regex PersonClockTokens = new(
        @"(?<!\d)(\d{1,2}):(\d{2})(?!\d)"
            + @"|(?<![\d:])(\d{1,2})(?![\d:])(?=\s*(?:[ap]\.?\s*m\b|(?:de|en|por)\s+la\s+(?:manana|madrugada|tarde|noche)"
            + @"|en\s+punto|o'?\s*clock))"
            + @"|\b(?:las?|at)\s+(\d{1,2})(?![\d:])",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static HashSet<(int Hour, int Minute)> PersonNamedClocks(string? userText)
    {
        var named = new HashSet<(int Hour, int Minute)>();
        foreach (Match match in PersonClockTokens.Matches(FoldForPolicy(userText ?? string.Empty)))
        {
            (string hour, string minute) = match.Groups[1].Success
                ? (match.Groups[1].Value, match.Groups[2].Value)
                : (match.Groups[3].Success ? match.Groups[3].Value : match.Groups[4].Value, "0");
            int statedHour = int.Parse(hour, CultureInfo.InvariantCulture);
            int statedMinute = int.Parse(minute, CultureInfo.InvariantCulture);
            if (statedHour <= 24 && statedMinute <= 59)
            {
                named.Add((statedHour % 12, statedMinute));
            }
        }

        return named;
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
            // Uso real tanda 4: a reading of another place's time answers with that
            // place's clock (or a converted one) computed by the mind; this PC's
            // clock is not the fact owed there, so it is not demanded here either.
            || observed.TryGetProperty("place", out _)
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
        result = WithoutLibraryEntitlementConsequence(source, result);
        result = WithoutWebSearchObservedVocabulary(source, result);
        result = WithoutUnlistedNoteFinding(source, result);

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

    // INSTALL1621 «Install Stardew Valley on Steam»: a verified library read
    // found the game is not the person's; «it cannot be downloaded or
    // installed» states that consequence, not a failed read. Only that
    // predicate is masked; any other failure assertion still counts.
    private static string WithoutLibraryEntitlementConsequence(string source, string result)
    {
        if (!TryReadJson(source, out JsonElement root)
            || !root.TryGetProperty("operation", out JsonElement operation) || operation.ValueKind != JsonValueKind.String
            || operation.GetString() != "game.entitlement.named"
            || !root.TryGetProperty("verified", out JsonElement verified) || verified.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("succeeded", out JsonElement succeeded) || succeeded.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("observed", out JsonElement observed) || observed.ValueKind != JsonValueKind.Object
            || !observed.TryGetProperty("owned", out JsonElement owned) || owned.ValueKind != JsonValueKind.False)
        {
            return result;
        }

        return Regex.Replace(
            FoldForPolicy(result),
            @"\b(?:no\s+(?:puedo|puedes|podes|podras|podre|podria|podrias|se\s+puede|es\s+posible|vas\s+a\s+poder|voy\s+a\s+poder)"
            + @"|(?:it\s+|you\s+|i\s+)?(?:can't|cannot|can\s+not|couldn't|could\s+not|won't\s+be\s+able\s+to|am\s+unable\s+to|is\s+not\s+possible\s+to))"
            + @"\s+(?:be\s+)?(?:descargar|descargarlo|descargarla|descargarse|bajar|bajarlo|bajarla|instalar|instalarlo|instalarla|instalarse"
            + @"|desinstalar|desinstalarlo|desinstalarla|desinstalarse|download|downloaded|install|installed|uninstall|uninstalled|remove|removed)"
            + @"[^.;]{0,80}",
            " ",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    // SCREEN1417 «qué hay en la pantalla»: no vision provider exists, so a
    // verified screen reading says it cannot describe images and reads the
    // text. That clause states the reading's scope, not a failed mission.
    // H0060 «me falla mucho whatsapp … porqué suele fallar»: a verified web
    // search about failures returns titles and snippets that say «fallos»,
    // «no funciona», «cortes»; a reply that repeats them reports what was
    // found, not a failed search. Only words the results carry are masked,
    // word by word, so «no pude» and the other markers of an own failure
    // still count. Same lens as the mind's _without_observed_search_vocabulary.
    private static string WithoutWebSearchObservedVocabulary(string source, string result)
    {
        var vocabulary = new HashSet<string>(StringComparer.Ordinal);
        CollectWebSearchVocabulary(source, vocabulary, 0);
        if (vocabulary.Count == 0)
        {
            return result;
        }

        // Owner rule 2026-09-24: when no page answers, the lookup stays invisible
        // and the answer says only that it was not found («No lo encontré», «I
        // couldn't find it»); that is the scope of the read, not a failed search.
        // Twin of the mind's mask in compose_visible_defect.
        // M83 (D35, owner: «sin fuente, BAXY responde de memoria y lo avisa en corto»): when the pages did not state
        // what was asked, the answer from memory opens with that notice («No pude comprobarlo; de memoria…», «I
        // couldn't check this; from memory…»); it is the scope of the read too, not a failed search. Twin of the
        // mind's _says_it_is_from_memory.
        string withoutNotFound = Regex.Replace(
            FoldForPolicy(result),
            @"\b(?:no\s+(?:(?:lo|la|los|las)\s+)?(?:encontre|halle|pude\s+encontrar(?:lo|la|los|las)?)"
            + @"|(?:i\s+)?(?:couldn[’']?t|could\s+not|didn[’']?t|did\s+not|wasn[’']?t\s+able\s+to|was\s+not\s+able\s+to)\s+find)"
            + @"[^.;]{0,120}"
            // M101b (DEV-D v4a D-p16-t1 «No results mention valet parking for the Kenzi Rose Garden.»): the mind's
            // _SEARCH_NOT_FOUND_CLAUSE reads «no results», «not found» and «sin resultados» as the not-found of the
            // search too; this twin read the report as a reversed result and the turn ended with no final.
            + @"|\b(?:not\s+found|no\s+results|sin\s+resultados)\b[^.;]{0,120}"
            + @"|\bno\s+(?:lo\s+|la\s+)?pude\s+comprobar(?:lo|la)?\b(?=[^.]{0,80}\bde\s+memoria\b)[^.:\n]{0,80}"
            + @"|\b(?:i\s+)?(?:couldn[’']?t|could\s+not|wasn[’']?t\s+able\s+to)\s+(?:check|verify)\b"
            + @"(?=[^.]{0,80}\bfrom\s+memory\b)[^.:\n]{0,80}",
            " ",
            RegexOptions.CultureInvariant);
        return Regex.Replace(
            withoutNotFound,
            @"(?<![a-z0-9])[a-z0-9]{3,}(?![a-z0-9])",
            match => vocabulary.Contains(match.Value) ? " " : match.Value,
            RegexOptions.CultureInvariant);
    }

    private static void CollectWebSearchVocabulary(string source, HashSet<string> vocabulary, int depth)
    {
        if (depth > 8 || !TryReadJson(source, out JsonElement root) || root.ValueKind != JsonValueKind.Object)
        {
            return;
        }

        if (root.TryGetProperty("operation", out JsonElement operation) && operation.ValueKind == JsonValueKind.String
            && operation.GetString() == "web.search"
            && root.TryGetProperty("verified", out JsonElement verified) && verified.ValueKind == JsonValueKind.True
            && root.TryGetProperty("succeeded", out JsonElement succeeded) && succeeded.ValueKind == JsonValueKind.True
            && root.TryGetProperty("observed", out JsonElement observed) && observed.ValueKind == JsonValueKind.Object
            && observed.TryGetProperty("results", out JsonElement results) && results.ValueKind == JsonValueKind.Array)
        {
            if (observed.TryGetProperty("query", out JsonElement query))
            {
                CollectPolicyWords(query, vocabulary);
            }
            foreach (JsonElement entry in results.EnumerateArray())
            {
                if (entry.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }
                if (entry.TryGetProperty("title", out JsonElement title))
                {
                    CollectPolicyWords(title, vocabulary);
                }
                if (entry.TryGetProperty("snippet", out JsonElement snippet))
                {
                    CollectPolicyWords(snippet, vocabulary);
                }
            }
        }

        if (root.TryGetProperty("steps", out JsonElement steps) && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.ValueKind == JsonValueKind.String)
                {
                    CollectWebSearchVocabulary(step.GetString()!, vocabulary, depth + 1);
                }
            }
        }
    }

    private static void CollectPolicyWords(JsonElement value, HashSet<string> vocabulary)
    {
        if (value.ValueKind != JsonValueKind.String)
        {
            return;
        }
        foreach (Match word in Regex.Matches(
            FoldForPolicy(value.GetString()!), @"[a-z0-9]{3,}", RegexOptions.CultureInvariant))
        {
            vocabulary.Add(word.Value);
        }
    }

    private static string WithoutScreenReadingImageScope(string source, string result)
    {
        if (!HasVerifiedScreenReading(source, 0))
        {
            return result;
        }

        return Regex.Replace(
            FoldForPolicy(result),
            @"\b(?:no\s+(?:puedo|podia|podria)|(?:i\s+)?(?:can't|cannot|can\s+not|couldn't|could\s+not|am\s+unable\s+to|am\s+not\s+able\s+to))"
            // SCREEN1809 «identificá el botón»: the scope said about buttons too.
            + @"\s+(?:describir|describirte|ver|identificar|reconocer|describe|see|identify|recognize|recognise)"
            + @"\s+(?:las\s+|los\s+|the\s+)?(?:imagenes?|images?|pictures?|graficos?|graphics|visuales?|visuals|botones?|buttons?)"
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

    // M58 (v3d-final F-p03-t1 «Actually, can you find the note called grocery?» read the notes and
    // «I cannot find a note called "grocery" in your active notes; the only note visible is titled
    // "Llego tarde hoy".» died as reversed_result: the turn ended with no answer). A verified read of
    // the notes that has no note by the asked name is answered by saying so; that finding is the read,
    // not a failure. Only a name the read does not list is masked.
    private static string WithoutUnlistedNoteFinding(string source, string result)
    {
        if (!TryReadJson(source, out JsonElement root)
            || !root.TryGetProperty("kind", out JsonElement kind) || kind.ValueKind != JsonValueKind.String || kind.GetString() != "operation"
            || !root.TryGetProperty("operation", out JsonElement operation) || operation.ValueKind != JsonValueKind.String
            || operation.GetString() is not ("note.list" or "note.search")
            || !root.TryGetProperty("polarity", out JsonElement polarity) || polarity.ValueKind != JsonValueKind.String || polarity.GetString() != "success"
            || !root.TryGetProperty("verified", out JsonElement verified) || verified.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("succeeded", out JsonElement succeeded) || succeeded.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("observed", out JsonElement observed) || observed.ValueKind != JsonValueKind.Object
            || !observed.TryGetProperty("notes", out JsonElement notes) || notes.ValueKind != JsonValueKind.Array)
        {
            return result;
        }

        static string Bare(string text) => Regex.Replace(FoldForPolicy(text), @"[""'«»“”‘’]", string.Empty).Trim();
        var listed = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement note in notes.EnumerateArray())
        {
            if (note.ValueKind == JsonValueKind.Object && note.TryGetProperty("title", out JsonElement title)
                && title.ValueKind == JsonValueKind.String && title.GetString() is { Length: > 0 } name)
            {
                listed.Add(Bare(name));
            }
        }

        const string quoted = @"[""'«“‘]?(?<name>[^""'«»“”‘’.;,]{1,120}?)[""'»”’]?";
        string finding =
            @"\b(?:i\s+)?(?:cannot|can't|could\s+not|couldn't|did\s+not|didn't)\s+find\s+(?:a|any|the)\s+note\s+"
            + @"(?:called|named|titled)\s+" + quoted + @"(?=\s+in\b|\s*[.;,]|$)"
            + @"|\bno\s+(?:encontre|encuentro|pude\s+encontrar|puedo\s+encontrar|se\s+encontro|hay)\s+(?:una|ninguna|la)\s+"
            + @"nota\s+(?:llamada|titulada|con\s+el\s+titulo)\s+" + quoted + @"(?=\s+en\b|\s*[.;,]|$)";
        return Regex.Replace(FoldForPolicy(result), finding, found =>
            listed.Contains(Bare(found.Groups["name"].Value)) ? found.Value : " ",
            RegexOptions.CultureInvariant);
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

        // Uso real 2026-09-23 «qué música se está reproduciendo» with no player
        // found: «No hay un video de YouTube en ejecución» IS the failure told
        // when the failure is that absence. Twin of the mind's _ABSENCE_STATEMENT.
        if (IsNotFoundFailure(source)
            && Regex.IsMatch(FoldForPolicy(result), AbsenceStatement,
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            return false;
        }

        // Fase 3.5b «activa mi microfono» already on: «ya estaba activo» IS the failure told when the
        // failure is that the target already had the asked state. Twin of the mind's _ALREADY_STATEMENT.
        if (IsAlreadyStateFailure(source)
            && Regex.IsMatch(FoldForPolicy(result), AlreadyStatement,
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            && !Regex.IsMatch(FoldForPolicy(result), FirstPersonAlready,
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            return false;
        }

        return !LooksLikeFailure(result);
    }

    // Independent review A2: «Ya está, activé tu micrófono» is «done», not «it already was»; twin of
    // llm._ALREADY_STATEMENT.
    // NonBacktracking takes no lookaround: «ya está» before a state word is «ya está» and a letter, and BAXY's own
    // «I already…» is excluded by FirstPersonAlready. M101 (owner script v3z2 t45): «estaba ya silenciado» too.
    private const string AlreadyStatement =
        @"\bya\s+(?:estaba|estaban|era|eran)\b|\b(?:estaba|estaban|era|eran)\s+ya\b|\bya\s+estan?\s+[a-z]|\balready\b";
    private const string FirstPersonAlready = @"\bi(?:'ve|\s+have)?\s+already\b";

    /// <summary>
    /// The typed failure is that the target already had the asked state («microphone_already_unmuted»).
    /// Twin of the mind's _failure_is_an_unchanged_state.
    /// </summary>
    private static bool IsAlreadyStateFailure(string source) =>
        TryReadJson(source, out JsonElement root)
        && HasErrorCode(root, 0, static code => code.Contains("_already_", StringComparison.Ordinal));

    // M69 (guion v3h t46/t47): «activa mi microfono» with the microphone already active. The typed codes whose asked
    // state already holds: the adapter read the state and crossed no boundary, so the person is told that state as a
    // result, not an error. «volume_already_at_*» stays a failure (the asked change, louder or quieter, cannot
    // happen), and «zip_already_exists» is a conflict. Twin of the mind's _ASKED_STATE_ALREADY_HELD.
    private static readonly HashSet<string> AskedStateAlreadyHeldCodes = new(StringComparer.Ordinal)
    {
        "microphone_already_muted",
        "microphone_already_unmuted",
        "airplane_mode_already_on",
        "airplane_mode_already_off",
    };

    internal static bool IsAskedStateAlreadyHeldCode(string? code) =>
        code is not null && AskedStateAlreadyHeldCodes.Contains(code);

    /// <summary>
    /// M69: the failure told is that the asked state already held («microphone_already_unmuted»), in the failure or
    /// in the step failure it wraps. Twin of the mind's _failure_is_an_asked_state_held.
    /// </summary>
    internal static bool IsAskedStateAlreadyHeld(string source) =>
        TryReadJson(source, out JsonElement root)
        && HasErrorCode(root, 0, static code => AskedStateAlreadyHeldCodes.Contains(code));

    private static bool HasErrorCode(JsonElement node, int depth, Func<string, bool> matches)
    {
        if (depth > 4 || node.ValueKind != JsonValueKind.Object)
        {
            return false;
        }
        foreach (JsonProperty property in node.EnumerateObject())
        {
            if (property.Value.ValueKind == JsonValueKind.Object && HasErrorCode(property.Value, depth + 1, matches))
            {
                return true;
            }
            if (property.Value.ValueKind != JsonValueKind.String)
            {
                continue;
            }
            string text = property.Value.GetString() ?? string.Empty;
            if (property.NameEquals("error") && matches(text))
            {
                return true;
            }
            if (property.NameEquals("reason") && TryReadJson(text, out JsonElement wrapped)
                && HasErrorCode(wrapped, depth + 1, matches))
            {
                return true;
            }
        }
        return false;
    }

    private const string AbsenceStatement =
        @"\bno\s+hay\b|\bningun[oa]?\b|\bno\s+(?:se\s+)?(?:esta|estan|estaba)\s+"
        + @"(?:sonando|reproduciendo|reproduciendose|abiert[oa]s?|en\s+(?:ejecucion|reproduccion))\b|"
        + @"\bno\s+suena\b|\bnothing\s+(?:is|was)\b|\bthere\s+(?:is|are|was|were)\s+no\b|"
        + @"\b(?:isn't|is\s+not|aren't|are\s+not|wasn't|was\s+not)\s+(?:playing|open|running)\b|"
        + @"\bno\s+\w+(?:\s+\w+)?\s+(?:is|was)\s+(?:playing|open|running)\b|"
        // Uso real tanda 5 (weather_place_not_found): «el servicio no reconoce ese lugar» tells that absence.
        + @"\bno\s+(?:se\s+)?(?:reconoce|reconocio|conoce|conocio|encuentra|encontro)\b|"
        + @"\b(?:doesn't|does\s+not|didn't|did\s+not)\s+(?:recognize|recognise|know|find)\b";

    /// <summary>
    /// The typed failure is that something was not found («youtube_tab_not_found»,
    /// «media_session_not_found»), in the failure or in the step failure it wraps.
    /// Twin of the mind's _failure_is_an_absence.
    /// </summary>
    private static bool IsNotFoundFailure(string source)
    {
        return TryReadJson(source, out JsonElement root) && HasNotFoundError(root, 0);

        static bool HasNotFoundError(JsonElement node, int depth)
        {
            if (depth > 4 || node.ValueKind != JsonValueKind.Object)
            {
                return false;
            }
            foreach (JsonProperty property in node.EnumerateObject())
            {
                if (property.Value.ValueKind == JsonValueKind.Object
                    && HasNotFoundError(property.Value, depth + 1))
                {
                    return true;
                }
                if (property.Value.ValueKind != JsonValueKind.String)
                {
                    continue;
                }
                string text = property.Value.GetString() ?? string.Empty;
                if (property.NameEquals("error") && text.Contains("not_found", StringComparison.Ordinal))
                {
                    return true;
                }
                if (property.NameEquals("reason") && TryReadJson(text, out JsonElement wrapped)
                    && HasNotFoundError(wrapped, depth + 1))
                {
                    return true;
                }
            }
            return false;
        }
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
