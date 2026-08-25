using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Hechos de una misión multipaso. El modelo formula la frase visible.
/// </summary>
internal static class MissionNarration
{
    internal static string CreateCompletionMessage(
        IReadOnlyList<string> completedMessages)
    {
        ArgumentNullException.ThrowIfNull(completedMessages);
        if (completedMessages.Count == 0)
        {
            throw new ArgumentException(
                "A completed mission must contain at least one result.",
                nameof(completedMessages));
        }

        if (completedMessages.Count == 1
            && UserMessagePolicy.IsStructuredFacts(completedMessages[0]))
        {
            return completedMessages[0];
        }

        var steps = new JsonArray();
        foreach (string message in completedMessages)
        {
            steps.Add(NormalizeOutcome(message));
        }

        return TurnVisibleFacts.Status(
            "mission_completed",
            new JsonObject
            {
                ["stepCount"] = completedMessages.Count,
                ["steps"] = steps,
            });
    }

    internal static string CreateFailureMessage(
        IReadOnlyList<string> completedMessages,
        string reason)
    {
        ArgumentNullException.ThrowIfNull(completedMessages);
        ArgumentException.ThrowIfNullOrWhiteSpace(reason);
        var steps = new JsonArray();
        foreach (string message in completedMessages)
        {
            steps.Add(NormalizeOutcome(message));
        }

        return TurnVisibleFacts.Failure(
            "mission_failed",
            new JsonObject
            {
                ["stepCount"] = completedMessages.Count,
                ["steps"] = steps,
                ["reason"] = NormalizeFailureReason(reason),
            });
    }

    internal static string CreateRecoveryPrompt(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        if (MindPlanBoundary.CanRefreshConfirmationChallenge(execution))
        {
            return TurnVisibleFacts.Confirmation(
                "mission_recovery_uncertain_step",
                TurnVisibleFacts.ConfirmCancel);
        }

        if (execution.PendingEffectMayHaveOccurred)
        {
            return TurnVisibleFacts.Failure("mission_recovery_uncertain_effect");
        }

        return TurnVisibleFacts.Confirmation(
            "mission_recovery_resume",
            TurnVisibleFacts.ContinueCancel);
    }

    internal static UserMessageEvent CreateRecoveryEvent(
        PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        return MindPlanBoundary.IsTerminalUnrefreshableEffect(execution)
            ? UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted)
            : UserMessageEvent.Confirmation;
    }

    private static string NormalizeOutcome(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return TurnVisibleFacts.Status("step_verified");
        }

        return string.Join(
            ' ',
            message.Split(
                ['\r', '\n'],
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
    }

    private static string NormalizeFailureReason(string reason)
    {
        string trimmed = reason.Trim();
        try
        {
            if (JsonNode.Parse(trimmed) is JsonObject facts)
            {
                foreach (string key in new[] { "error", "cause" })
                {
                    if (facts[key] is JsonValue value
                        && value.TryGetValue(out string? code)
                        && !string.IsNullOrWhiteSpace(code))
                    {
                        return code.Trim();
                    }
                }
            }
        }
        catch (JsonException)
        {
            // A plain person-facing reason remains valid input.
        }

        return trimmed;
    }
}
