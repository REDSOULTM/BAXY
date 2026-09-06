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

        var steps = new JsonArray();
        foreach (string message in completedMessages)
        {
            steps.Add(NormalizeOutcome(message));
        }

        var extra = new JsonObject
        {
            ["stepCount"] = completedMessages.Count,
            ["steps"] = steps,
        };
        JsonObject? observed = MergeObserved(completedMessages);
        if (observed is not null)
        {
            extra["observed"] = observed;
        }

        return TurnVisibleFacts.Status("mission_completed", extra);
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
                ["reason"] = reason.Trim(),
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
            return TurnVisibleFacts.Status("mission_recovery_uncertain_effect");
        }

        return TurnVisibleFacts.Confirmation(
            "mission_recovery_resume",
            TurnVisibleFacts.ContinueCancel);
    }

    private static JsonObject? MergeObserved(IReadOnlyList<string> messages)
    {
        var merged = new JsonObject();
        foreach (string message in messages)
        {
            string trimmed = message.Trim();
            if (trimmed.Length == 0 || trimmed[0] != '{')
            {
                continue;
            }

            try
            {
                using JsonDocument document = JsonDocument.Parse(trimmed);
                JsonElement root = document.RootElement;
                JsonElement observed = root;
                if (root.TryGetProperty("observed", out JsonElement nested)
                    && nested.ValueKind == JsonValueKind.Object)
                {
                    observed = nested;
                }

                CopyObservedFacts(observed, merged);
                if (observed.TryGetProperty("state", out JsonElement state)
                    && state.ValueKind == JsonValueKind.Object)
                {
                    CopyObservedFacts(state, merged);
                    if (state.TryGetProperty("volumePercent", out JsonElement volume))
                    {
                        merged["level"] = JsonNode.Parse(volume.GetRawText());
                    }
                }
            }
            catch (JsonException)
            {
                // Prose step outcomes are not observed facts.
            }
        }

        return merged.Count == 0 ? null : merged;
    }

    private static void CopyObservedFacts(JsonElement observed, JsonObject merged)
    {
        foreach (string key in new[]
        {
            "utc", "localUtcOffsetMinutes", "muted", "level", "online",
        })
        {
            if (observed.TryGetProperty(key, out JsonElement value))
            {
                merged[key] = JsonNode.Parse(value.GetRawText());
            }
        }
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
}
