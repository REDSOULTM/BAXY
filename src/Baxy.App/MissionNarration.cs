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

        var facts = new JsonObject
        {
            ["steps"] = steps,
            ["cancelledRequest"] = execution.Objective,
            ["cancelledAction"] = DescribeCurrentAction(execution),
        };
        // C7Y5 (banco fp c7): the cancelled act of a computer-use mission ends the whole mission; the sub-goals after the
        // one it belonged to are left undone, and the floor says them (operation_floor._goals_left).
        int current = (int?)execution.ComputerUse?["subgoal"] ?? 0;
        if (execution.ComputerUse?["subgoals"] is JsonArray subgoals && current + 1 < subgoals.Count)
        {
            facts["cancelledGoals"] = new JsonArray([.. subgoals.Skip(current + 1).OfType<JsonObject>()
                .Select(subgoal => (JsonNode)new JsonObject
                {
                    ["goal"] = (string?)subgoal["goal"],
                    ["application"] = (string?)subgoal["application"],
                })]);
        }

        return TurnVisibleFacts.Status("remaining_steps_cancelled", facts);
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
        var described = new JsonObject
        {
            ["operation"] = prepared?.OperationName ?? execution.CurrentStep.Operation,
            ["purpose"] = execution.CurrentStep.Purpose,
            ["arguments"] = prepared is null
                ? execution.CurrentStep.Arguments?.DeepClone()
                : JsonNode.Parse(prepared.Arguments.GetRawText()),
        };

        // Encargo VZ: an act that goes out to the world is asked from its family and its name (operation_floor
        // «worldActAsked»), in BAXY's first person, never in the person's words («que entres»).
        if (prepared is not null && Kernel.Policy.RiskPolicy.WorldActOf(prepared.OperationName, prepared.Arguments) is { } act)
        {
            described["worldAct"] = act.Family;
            described["actName"] = act.Name;
        }

        return described;
    }

    /// <summary>
    /// The step's effect may have occurred and was not verified. Pending (the
    /// default) keeps the evidence for the recovery challenge of a confirmed step;
    /// terminal says it once and closes the mission (ctx-dueno-01, 2026-09-22).
    /// </summary>
    internal static string CreateUncertainEffectMessage(
        PendingMindPlanExecution execution,
        bool terminal = false)
    {
        var facts = new JsonObject
        {
            ["step"] = execution.NextIndex + 1,
            ["pendingRequest"] = execution.Objective,
            ["effectUncertain"] = true,
            ["verified"] = false,
            ["pending"] = !terminal,
            ["canRepeat"] = terminal,
            ["evidenceRetained"] = !terminal,
        };

        // Estabilización F (tandas estab t4-c03 t2, t3-c07 t1, t2-c07 t1): the step left unconfirmed was named only by
        // the plan's objective, and the writer filled it with an act («Se le envió…», «No he enviado…»). It goes with
        // its own facts and the steps made before it, so the floor says it as tried and not confirmed.
        if (MindPlanBoundary.UncertainStep(execution) is { } reason)
        {
            var steps = new JsonArray();
            foreach (string message in execution.CompletedMessages)
            {
                steps.Add(NormalizeOutcome(message));
            }

            facts["steps"] = steps;
            facts["reason"] = reason;
        }

        return TurnVisibleFacts.Failure("result_unverified", facts);
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
            "utc", "localUtcOffsetMinutes", "place", "muted", "level", "online",
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
