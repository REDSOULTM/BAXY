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
        if (!allowRecovery)
        {
            return new ModelMessageCompositionOutcome(
                null,
                originalFailure,
                UsedRecovery: false);
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
            UsedRecovery: true);
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
                hasRequiredInput: UserMessagePolicy.HasRequiredInput(draft)))
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
            && !UserMessagePolicy.IsSafeConversationReply(
                userText, accepted, priorUserText: priorUserText,
                clarification: draft.Intent == "clarification",
                hasRequiredInput: UserMessagePolicy.HasRequiredInput(draft)))
        {
            return null;
        }

        return accepted;
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

internal sealed record ModelMessageCompositionOutcome(
    string? Text,
    string? Failure,
    bool UsedRecovery);
