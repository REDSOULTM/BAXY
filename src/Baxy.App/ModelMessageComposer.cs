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

    internal static UserMessageDraft CreateRecoveryDraft() =>
        UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("composition_lost_verified_facts"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService));

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
        // A generic apology is terminal. It may replace a status or error that
        // could not be rendered, but never a welcome, clarification or
        // confirmation whose exact wording is required for the next turn.
        bool canUseTerminalRecovery = allowRecovery
            && draft.Intent is "status" or "error";
        if (!canUseTerminalRecovery)
        {
            return new ModelMessageCompositionOutcome(
                null,
                originalFailure,
                UsedRecovery: false);
        }

        if (UserMessagePolicy.IsStructuredFacts(draft.Source))
        {
            // A second model call on the recovery draft would throw away the
            // verified facts and publish a generic apology.
            return new ModelMessageCompositionOutcome(
                null,
                "composition_lost_verified_facts",
                UsedRecovery: false);
        }

        // The deterministic sentence below is evidence for a second model call;
        // it is never shown. This is the model-authored apology required when a
        // factual result cannot be rendered without losing its contract.
        UserMessageDraft recoveryDraft = CreateRecoveryDraft();
        JsonObject recoveryFacts = CreateFacts(recoveryDraft);
        MindComposedMessage? recovered = await compose(
            userText,
            recoveryDraft.Intent,
            recoveryFacts,
            SelectTimeout(recoveryDraft, recoveryFacts, cpuFallback),
            cancellationToken).ConfigureAwait(false);
        string? acceptedRecovery = UserMessagePolicy.AcceptModelAuthoredResponse(
            recovered?.Text,
            recoveryDraft);
        if (acceptedRecovery is not null)
        {
            return new ModelMessageCompositionOutcome(
                acceptedRecovery,
                originalFailure,
                UsedRecovery: true);
        }

        string recoveryFailure = UserMessagePolicy.ModelResponseRejectionReason(
            recovered?.Text,
            recoveryDraft) ?? "model_response_rejected";
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
