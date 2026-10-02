using System.IO;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Redacta con el modelo local el texto visible de una respuesta ya verificada.
/// No conoce la conversación ni el estado de la ventana: recibe un borrador y
/// devuelve el texto aceptado por la política, o el motivo de su rechazo.
/// </summary>
internal static class ModelMessageComposer
{
    internal static JsonObject CreateFacts(
        UserMessageDraft draft,
        string? traceId = null,
        string? previousAnswer = null,
        IReadOnlyList<string>? priorRequests = null)
    {
        ArgumentNullException.ThrowIfNull(draft);
        var facts = new JsonObject { ["situation"] = draft.Source };
        if (!string.IsNullOrWhiteSpace(previousAnswer)
            && draft.Intent is "conversation" or "clarification")
        {
            facts["context"] = previousAnswer;
        }

        // Lo que la persona pidió antes viaja como dato para que la lectura
        // única del pedido resuelva el tema de un seguimiento elíptico. No es
        // un hecho publicable: el compositor lo excluye de los hechos y sólo
        // lo usa para saber de qué se está hablando. MUSIC1757: también decide
        // el idioma de un final de operación cuando la respuesta de la persona
        // no tiene idioma propio («Play a song on Spotify.» → «Queen»), así que
        // viaja con toda composición.
        if (priorRequests is { Count: > 0 })
        {
            var previousRequests = new JsonArray();
            foreach (string request in priorRequests)
            {
                if (!string.IsNullOrWhiteSpace(request))
                {
                    previousRequests.Add(request);
                }
            }

            if (previousRequests.Count > 0)
            {
                facts["priorRequests"] = previousRequests;
            }
        }

        // Correlación turno ↔ composición: sin ella una traza de rechazo no se
        // puede ligar al turno que la produjo.
        if (!string.IsNullOrWhiteSpace(traceId))
        {
            facts["traceId"] = traceId;
        }

        var forbiddenResponseTerms = new JsonArray();
        foreach (string term in UserMessagePolicy.ForbiddenResponseTerms)
        {
            forbiddenResponseTerms.Add(term);
        }
        facts["forbiddenResponseTerms"] = forbiddenResponseTerms;
        facts["route"] = PublicResponseRoute.FromDraft(draft);
        if (UserMessagePolicy.IsStructuredFacts(draft.Source)
            && draft.Intent == "confirmation")
        {
            var requiredWords = new JsonArray();
            foreach (string word in UserMessagePolicy.RequiredConfirmationWords(draft.Source))
            {
                requiredWords.Add(word);
            }

            facts["requiredResponseWords"] = requiredWords;
        }

        if (draft.Intent is "status" or "error")
        {
            facts["mustNotAskFollowUp"] = true;
            IReadOnlyList<string> requiredActions =
                UserMessagePolicy.RequiredBaxyActions(draft.Source);
            if (requiredActions.Count > 0)
            {
                facts["actor"] = "BAXY (yo, primera persona)";
                facts["mustPreserveFirstPerson"] = true;
                facts["requiredAction"] = requiredActions[0];
                var actions = new JsonArray();
                foreach (string action in requiredActions)
                {
                    actions.Add(action);
                }

                facts["requiredActions"] = actions;
            }
            IReadOnlyList<string> requiredFacts =
                UserMessagePolicy.RequiredFactualFragments(draft.Source);
            IReadOnlyList<string> requiredLiteralFacts =
                UserMessagePolicy.RequiredLiteralFacts(draft.Source);
            if (requiredFacts.Count > 0 || requiredLiteralFacts.Count > 0)
            {
                var factualFragments = new JsonArray();
                foreach (string fact in requiredFacts.Concat(requiredLiteralFacts))
                {
                    factualFragments.Add(fact);
                }

                facts["requiredFacts"] = factualFragments;
                if (draft.Intent == "error" && requiredFacts.Count > 0)
                {
                    facts["partialMission"] = true;
                }
            }
        }
        else if (draft.Intent == "confirmation")
        {
            var requiredWords = new JsonArray();
            foreach (string word in UserMessagePolicy.RequiredConfirmationWords(
                         draft.Source))
            {
                requiredWords.Add(word);
            }

            facts["requiredResponseWords"] = requiredWords;
        }

        return facts;
    }

    internal static async Task<ModelMessageCompositionOutcome> ComposeAsync(
        UserMessageDraft draft,
        string userText,
        JsonObject facts,
        Func<string, string, JsonObject, TimeSpan, CancellationToken,
            Task<MindComposedMessage?>> compose,
        bool cpuFallback,
        bool allowRecovery,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(draft);
        ArgumentNullException.ThrowIfNull(facts);
        ArgumentNullException.ThrowIfNull(compose);

        // These words came from the person, not from the product internals.
        // Use them only for vocabulary; the current request still owns intent.
        string? priorUserText = facts["priorRequests"] is JsonArray prior
            ? string.Join(" ", prior.Select(static item => (string?)item))
            : null;

        MindComposedMessage? composed = await compose(
            userText,
            draft.Intent,
            facts,
            SelectTimeout(draft, facts, cpuFallback),
            cancellationToken).ConfigureAwait(false);
        string? accepted = AcceptPublishedConversation(
            composed?.Text,
            draft,
            userText,
            priorUserText);
        if (accepted is not null)
        {
            return new ModelMessageCompositionOutcome(
                accepted,
                Failure: null,
                UsedRecovery: false);
        }

        string originalFailure = RejectionReason(
            composed?.Text,
            draft,
            userText,
            priorUserText);
        // Latency 2026-09-23 (tanda-01, uso-real-03): with the served greedy
        // writer no recovery call ever published; it repeated the refused
        // composition and doubled a 0.4–9 s wait. A reproducible writer's answer
        // is final; only a writer that samples, or a mind that did not answer,
        // gets the second call.
        if (!allowRecovery || composed is { Reproducible: true })
        {
            return new ModelMessageCompositionOutcome(
                null,
                originalFailure,
                UsedRecovery: false,
                Unanswered: composed is null,
                RejectedText: composed?.Text);
        }

        // Retry the same verified facts. A lost-facts failure draft used to
        // turn a Core-verified clock into «No pude: no pude encontrarlo.»
        MindComposedMessage? recovered = await compose(
            userText,
            draft.Intent,
            facts,
            SelectTimeout(draft, facts, cpuFallback),
            cancellationToken).ConfigureAwait(false);
        string? acceptedRecovery = AcceptPublishedConversation(
            recovered?.Text,
            draft,
            userText,
            priorUserText);
        if (acceptedRecovery is not null)
        {
            return new ModelMessageCompositionOutcome(
                acceptedRecovery,
                originalFailure,
                UsedRecovery: true);
        }

        string recoveryFailure = RejectionReason(
            recovered?.Text,
            draft,
            userText,
            priorUserText);
        return new ModelMessageCompositionOutcome(
            null,
            $"{originalFailure};recovery:{recoveryFailure}",
            UsedRecovery: true,
            Unanswered: recovered is null,
            RejectedText: recovered?.Text ?? composed?.Text);
    }

    // cien-36 027 «open that»: the clarification was refused by
    // IsSafeConversationReply, whose reason the composer never asked, so the
    // turn recorded the bare «model_response_rejected» and no check could be
    // told from another. Both reason functions are consulted, in the order
    // they run.
    private static string RejectionReason(
        string? modelText,
        UserMessageDraft draft,
        string userText,
        string? priorUserText) =>
        UserMessagePolicy.ModelResponseRejectionReason(
            modelText, draft, userText, priorUserText)
        ?? (modelText is null
            ? null
            : UserMessagePolicy.ConversationReplyRejectionReason(
                userText,
                modelText,
                priorUserText: priorUserText,
                hasRequiredInput: UserMessagePolicy.HasRequiredInput(draft),
                missingFields: UserMessagePolicy.DeclaredMissingFields(draft)))
        ?? "model_response_rejected";

    private static string? AcceptPublishedConversation(
        string? modelText,
        UserMessageDraft draft,
        string userText,
        string? priorUserText)
    {
        string? accepted = UserMessagePolicy.AcceptModelAuthoredResponse(
            modelText,
            draft,
            userText,
            priorUserText);
        if (accepted is null)
        {
            return null;
        }

        if ((draft.Intent is "welcome" or "clarification" or "conversation"
                || UserMessagePolicy.ConversationFallbackIntent(userText) == "out_of_catalog")
            // cien-36 027 «open that» → «What do you want me to open?»: the
            // person did ask for an opening, and the question asks which one;
            // without this flag the check read it as a catalog action nobody
            // asked for and the turn exhausted, while the Spanish «¿Qué querés
            // que abra?» passed.
            // MEME2057 «Tienes algun meme?»: the fallback still reads an image
            // ask as out of catalog, so a verified mission's status reply crossed
            // these conversation checks with its raw words and «meme.jpg» — the
            // observed file the viewer shows — died in internal_code. A status or
            // error draft is checked on its masked vocabulary, as the response
            // checks already do; the published text keeps every word.
            && !UserMessagePolicy.IsSafeConversationReply(
                userText,
                draft.Intent is "status" or "error"
                    ? ObservedResponseLiterals.WithoutObservedIdentifiers(
                        ObservedResponseLiterals.WithoutObservedNames(accepted, draft.Source), draft.Source)
                    : accepted,
                priorUserText: priorUserText,
                clarification: draft.Intent == "clarification",
                hasRequiredInput: UserMessagePolicy.HasRequiredInput(draft),
                missingFields: UserMessagePolicy.DeclaredMissingFields(draft)))
        {
            return null;
        }

        return accepted;
    }

    /// <summary>
    /// A7 twin of the mind's llm._deterministic_final: when every composition of a result was refused (or the mind
    /// returned none), the result is told in one short sentence of the person's language. A verified result with an
    /// own sentence here (the clock, the volume, a YouTube title) says its observed values; a typed failure whose
    /// cause is known says it whole; any other action — done, failed, left uncertain, or a mission step by step — is
    /// said by <see cref="OperationFloor"/> (M107), from the same data the mind reads. The sentence passes the same
    /// acceptance as a composed one. <paramref name="clock"/> (M108) is the PC's clock the day words are told against
    /// (the system clock when null).
    /// </summary>
    internal static string? DeterministicFinal(
        UserMessageDraft draft,
        string userText,
        JsonObject facts,
        string? rejectedText,
        TimeProvider? clock = null)
    {
        ArgumentNullException.ThrowIfNull(draft);
        ArgumentNullException.ThrowIfNull(facts);
        if (draft.Intent is not ("status" or "error") || !UserMessagePolicy.IsStructuredFacts(draft.Source))
        {
            return null;
        }

        JsonObject? source;
        try
        {
            source = JsonNode.Parse(draft.Source) as JsonObject;
        }
        catch (System.Text.Json.JsonException)
        {
            return null;
        }

        if (source is null)
        {
            return null;
        }

        // A mind that answered nothing («no_response») left an empty text: the request then says the language.
        bool english = LooksEnglish(string.IsNullOrWhiteSpace(rejectedText) ? userText : rejectedText);
        bool done = ReadBool(source, "verified") == true && ReadBool(source, "succeeded") == true;
        string? text = done
            ? VerifiedResultFinal(source, userText, draft.Source, english)
            : OperationFloor.FailureSentence(source, english);
        text ??= OperationFloor.Final(source, english, clock);
        if (text is null)
        {
            return null;
        }

        string? priorUserText = facts["priorRequests"] is JsonArray prior
            ? string.Join(" ", prior.Select(static item => (string?)item))
            : null;
        return AcceptPublishedConversation(text, draft, userText, priorUserText);
    }

    // The verified results the App tells with their own observed values; null for any other.
    private static string? VerifiedResultFinal(JsonObject source, string userText, string draftSource, bool english)
    {
        if (ReadString(source, "operation") is not { } operation)
        {
            return null;
        }

        JsonObject? seen = source["observed"] as JsonObject;
        string? text = null;
        if (operation == "system.time")
        {
            if (!UserMessagePolicy.IsCountdownRequest(userText)
                && !UserMessagePolicy.IsLaterClockRequest(userText)
                && !UserMessagePolicy.AsksCalendarDate(userText)
                && UserMessagePolicy.TryDerivedLocalClock(draftSource, out string hhmm))
            {
                text = english ? $"It's {hhmm}." : $"Son las {hhmm}.";
            }
        }
        else if (operation is "audio.volume" or "audio.volume.adjust"
            && seen?["level"] is JsonValue levelValue
            && levelValue.TryGetValue(out int level))
        {
            text = VolumeFinal(level, ReadString(seen, "direction"), ReadBool(seen, "muted") == true, english);
        }
        else if (operation == "media.play.youtube"
            && ReadString(seen, "playbackStatus") == "playing"
            && ReadString(seen, "title") is { Length: > 0 } title
            && ReadBool(seen, "titleObserved") != false)
        {
            string where = title.EndsWith("youtube", StringComparison.OrdinalIgnoreCase)
                ? string.Empty
                : english ? " on YouTube" : " en YouTube";
            text = english ? $"Now playing «{title}»{where}." : $"Está sonando «{title}»{where}.";
        }
        // A search the App could not phrase has no fixed sentence here: the owner's zero-fixed-visible-prose census
        // (A7 had put «No lo encontré.» in this place) keeps that wording in the mind, whose not-found fallback is
        // written from the turn; the App's own last resort only states values it observed (the operation floor
        // tells no verified search either: by the owner's rule the search is not shown).
        return text;
    }

    private static string? ReadString(JsonObject? node, string key) =>
        node?[key] is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private static bool? ReadBool(JsonObject? node, string key) =>
        node?[key] is JsonValue value && value.TryGetValue(out bool flag) ? flag : null;

    private static string VolumeFinal(int level, string? direction, bool muted, bool english)
    {
        if (english)
        {
            string head = direction is "down" or "up"
                ? $"I turned the volume {direction} to {level}%"
                : $"The volume is at {level}%";
            return head + (muted ? "; it is muted." : ".");
        }

        string spanish = direction is "down" or "up"
            ? $"{(direction == "down" ? "Bajé" : "Subí")} el volumen a {level} %"
            : $"El volumen está en {level} %";
        return spanish + (muted ? "; está silenciado." : ".");
    }

    // BAXY's own refused sentence (or else the request) decides the language of the fallback: Spanish unless
    // English function words outnumber Spanish ones; accents and inverted marks are Spanish. M107: the floor of an
    // action the mind answered nothing for reads the request alone («open google keep for me» was told in Spanish),
    // so the common request words of each language count too; a word both languages write («me», «a», «no») never.
    private static bool LooksEnglish(string? text)
    {
        if (string.IsNullOrWhiteSpace(text) || text.IndexOfAny(['á', 'é', 'í', 'ó', 'ú', 'ñ', '¿', '¡']) >= 0)
        {
            return false;
        }

        string[] words = text.ToLowerInvariant().Split(
            [' ', ',', '.', '?', '!', ';', ':'], StringSplitOptions.RemoveEmptyEntries);
        int english = words.Count(static word => word is "the" or "is" or "it" or "i" or "what" or "you" or "to"
            or "my" or "of" or "and" or "in" or "on" or "time" or "play" or "show" or "like"
            or "for" or "please" or "can" or "could" or "this" or "that" or "open" or "close" or "turn" or "off"
            or "with" or "from" or "at" or "are" or "do" or "how" or "where" or "which" or "your" or "set" or "an");
        int spanish = words.Count(static word => word is "el" or "la" or "es" or "que" or "de" or "los" or "las"
            or "en" or "y" or "mi" or "mis" or "por" or "un" or "una" or "hora" or "pon" or "ponme"
            or "para" or "con" or "del" or "al" or "abre" or "cierra" or "favor" or "lo" or "se" or "quiero"
            or "puedes" or "esta" or "este" or "como" or "pero" or "hay");
        return english > spanish;
    }

    internal static bool IsTransientFailure(Exception exception) =>
        exception is IOException
            or InvalidDataException
            or InvalidOperationException
            or TimeoutException
            or System.Text.Json.JsonException;

    private static TimeSpan SelectTimeout(
        UserMessageDraft draft,
        JsonObject facts,
        bool cpuFallback) =>
        draft.Intent == "welcome"
            ? MindSidecarClient.SelectWelcomeCompositionTimeout(cpuFallback)
            : MindSidecarClient.SelectMessageCompositionTimeout(facts, cpuFallback);
}

/// <summary>
/// <see cref="Unanswered"/>: the last request got no answer from the mind
/// (not ready, transport or runtime failure). Only such a failure can go
/// differently later; a draft the writer answered or that the policy refused
/// is the composition's outcome. <see cref="RejectedText"/> is the mind's text
/// the policy refused, kept for the private audit only (A7).
/// </summary>
internal sealed record ModelMessageCompositionOutcome(
    string? Text,
    string? Failure,
    bool UsedRecovery,
    bool Unanswered = false,
    string? RejectedText = null);
