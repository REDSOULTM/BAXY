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
    internal static JsonObject CreateFacts(UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        var facts = new JsonObject { ["situation"] = draft.Source };
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

        MindComposedMessage? composed = await compose(
            userText,
            draft.Intent,
            facts,
            SelectTimeout(draft, facts, cpuFallback),
            cancellationToken).ConfigureAwait(false);
        string? accepted = UserMessagePolicy.AcceptModelAuthoredResponse(
            composed?.Text,
            draft);
        if (accepted is not null)
        {
            return new ModelMessageCompositionOutcome(
                accepted,
                Failure: null,
                UsedRecovery: false);
        }

        string originalFailure = UserMessagePolicy.ModelResponseRejectionReason(
            composed?.Text,
            draft) ?? "model_response_rejected";
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
        string? acceptedRecovery = UserMessagePolicy.AcceptModelAuthoredResponse(
            recovered?.Text,
            draft);
        if (acceptedRecovery is not null)
        {
            return new ModelMessageCompositionOutcome(
                acceptedRecovery,
                originalFailure,
                UsedRecovery: true);
        }

        string recoveryFailure = UserMessagePolicy.ModelResponseRejectionReason(
            recovered?.Text,
            draft) ?? "model_response_rejected";
        return new ModelMessageCompositionOutcome(
            null,
            $"{originalFailure};recovery:{recoveryFailure}",
            UsedRecovery: true);
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
