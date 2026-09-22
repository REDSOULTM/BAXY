using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Hechos de una misión multipaso. El modelo formula la frase visible.
/// </summary>
internal static class MissionNarration
{
    internal static string CreateCompletionMessage(
        IReadOnlyList<string> completedMessages,
        string? completedRequest = null)
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
        if (!string.IsNullOrWhiteSpace(completedRequest))
        {
            extra["completedRequest"] = completedRequest;
        }
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
        JsonNode failureReason = JsonValue.Create(reason.Trim())!;
        try
        {
            if (JsonNode.Parse(reason) is JsonObject structuredReason)
            {
                failureReason = structuredReason;
            }
        }
        catch (JsonException)
        {
            // Legacy prose remains a value; structured facts retain their tree.
        }

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
                ["reason"] = failureReason,
            });
    }

    internal static string CreateRecoveryPrompt(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        if (MindPlanBoundary.CanRefreshConfirmationChallenge(execution))
        {
            return CreateConfirmationMessage(execution,
                "mission_recovery_uncertain_step",
                TurnVisibleFacts.ConfirmCancel);
        }

        if (execution.PendingEffectMayHaveOccurred)
        {
            return CreateUncertainEffectMessage(execution);
        }

        return CreateConfirmationMessage(execution,
            "mission_recovery_resume",
            TurnVisibleFacts.ContinueCancel);
    }

    internal static string CreateCancellationMessage(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        var steps = new JsonArray();
        foreach (string message in execution.CompletedMessages)
        {
            steps.Add(NormalizeOutcome(message));
        }

        return TurnVisibleFacts.Status("remaining_steps_cancelled", new JsonObject
        {
            ["steps"] = steps,
            ["cancelledRequest"] = execution.Objective,
            ["cancelledAction"] = DescribeCurrentAction(execution),
        });
    }

    internal static string CreateConfirmationMessage(
        PendingMindPlanExecution execution,
        string cause,
        IReadOnlyList<string> choices)
    {
        return TurnVisibleFacts.Confirmation(cause, choices, new JsonObject
        {
            ["step"] = execution.NextIndex + 1,
            ["pendingRequest"] = execution.Objective,
            ["pendingAction"] = DescribeCurrentAction(execution),
        });
    }

    private static JsonObject DescribeCurrentAction(PendingMindPlanExecution execution)
    {
        PreparedOperation? prepared = execution.Confirmation?.Prepared ?? execution.PendingOperation;
        return new JsonObject
        {
            ["operation"] = prepared?.OperationName ?? execution.CurrentStep.Operation,
            ["purpose"] = execution.CurrentStep.Purpose,
            ["arguments"] = prepared is null
                ? execution.CurrentStep.Arguments?.DeepClone()
                : JsonNode.Parse(prepared.Arguments.GetRawText()),
        };
    }

    /// <summary>
    /// The step's effect may have occurred and was not verified. Pending (the
    /// default) keeps the evidence for the recovery challenge of a confirmed step;
    /// terminal says it once and closes the mission (ctx-dueno-01, 2026-09-22).
    /// </summary>
    internal static string CreateUncertainEffectMessage(
        PendingMindPlanExecution execution,
        bool terminal = false) =>
        TurnVisibleFacts.Failure("result_unverified", new JsonObject
        {
            ["step"] = execution.NextIndex + 1,
            ["pendingRequest"] = execution.Objective,
            ["effectUncertain"] = true,
            ["verified"] = false,
            ["pending"] = !terminal,
            ["canRepeat"] = terminal,
            ["evidenceRetained"] = !terminal,
        });

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

        string normalized = string.Join(
            ' ',
            message.Split(
                ['\r', '\n'],
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
        try
        {
            if (JsonNode.Parse(normalized) is JsonObject result
                && result["operation"] is JsonValue operationValue
                && operationValue.TryGetValue(out string? operation)
                && ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor))
            {
                result["readOnly"] = descriptor.Risk == OperationRisks.ReadOnly;
                return result.ToJsonString();
            }
        }
        catch (JsonException)
        {
            // Legacy prose is not a typed operation result.
        }

        return normalized;
    }
}
