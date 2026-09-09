using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>
/// Hechos de operaciones privadas. El modelo formula la frase visible.
/// </summary>
internal static class PrivateOperationNarration
{
    internal static string CreateMemoryClarification(MemoryParseResult result)
    {
        string cause = result.MustNotDelete
            ? "memory_delete_needs_target"
            : result.MustNotPersist
                ? "memory_save_needs_content"
                : result.MustNotInvent
                    ? "memory_recall_needs_query"
                    : "memory_request_underspecified";
        JsonObject? extra = result.MissingSaveSubject == MemorySaveSubject.Name
            ? new JsonObject { ["missingValue"] = "the person's name", ["saved"] = false }
            : null;
        return TurnVisibleFacts.Clarification(cause, extra);
    }

    internal static string CreateMemoryConfirmationPrompt(
        PreparedOperation prepared,
        bool reconciliationRequired = false)
    {
        if (reconciliationRequired)
        {
            return TurnVisibleFacts.Confirmation(
                "memory_reconcile_same_attempt",
                ["confirmar", "confirm"],
                PendingMemoryAction(prepared));
        }

        string cause = prepared.OperationName switch
        {
            "memory.sensitive.save" => "memory_sensitive_save",
            "memory.forget" => "memory_forget_irreversible",
            "memory.enable" => "memory_enable",
            "memory.export" => "memory_export_privacy",
            _ => "memory_needs_confirmation",
        };
        JsonObject extra = PendingMemoryAction(prepared);
        if (string.Equals(cause, "memory_export_privacy", StringComparison.Ordinal))
        {
            extra["destination"] = "Documents/BAXY";
            extra["mayRedirectOrSync"] = true;
        }
        return TurnVisibleFacts.Confirmation(cause, TurnVisibleFacts.ConfirmCancel, extra);
    }

    internal static string CreateMemoryFailureMessage(
        string operationName,
        OperationResponse response)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentNullException.ThrowIfNull(response);
        if (string.Equals(operationName, "memory.export", StringComparison.Ordinal)
            && response.Replayed)
        {
            return TurnVisibleFacts.Failure("memory_export_unverified_replay");
        }

        string cause = response.Status switch
        {
            OperationStatuses.Pending => "memory_pending_safe_check",
            OperationStatuses.Rejected => "memory_rejected_safety",
            OperationStatuses.Failed when string.Equals(
                response.ErrorCode,
                "memory_disabled",
                StringComparison.Ordinal) => "memory_disabled",
            OperationStatuses.Failed => "memory_failed_safe",
            _ => "memory_no_safe_response",
        };
        return TurnVisibleFacts.Failure(
            cause,
            new JsonObject { ["operation"] = operationName });
    }

    internal static string CreateMemoryRecoveryPrompt(PreparedOperation prepared)
    {
        return TurnVisibleFacts.Confirmation(
            "memory_recovery_pending",
            TurnVisibleFacts.ContinueCancel,
            PendingMemoryAction(prepared));
    }

    internal static JsonObject PendingMemoryAction(PreparedOperation prepared) => new()
    {
        ["pendingAction"] = MemoryAction(prepared),
    };

    internal static string CreateMemoryCancellationMessage(PreparedOperation prepared) =>
        TurnVisibleFacts.Status(
            "memory_cancelled",
            new JsonObject { ["cancelledAction"] = MemoryAction(prepared) });

    private static JsonObject MemoryAction(PreparedOperation prepared) => new()
    {
        ["operation"] = prepared.OperationName,
        ["target"] = "private local memory",
    };

    internal static string CreateAudioRecoveryPrompt(PreparedOperation operation)
    {
        JsonElement arguments = operation.Arguments;
        if (string.Equals(operation.OperationName, "audio.volume", StringComparison.Ordinal)
            && arguments.TryGetProperty("level", out JsonElement level)
            && level.ValueKind == JsonValueKind.Number
            && level.TryGetInt32(out int requestedLevel))
        {
            return TurnVisibleFacts.Confirmation(
                "audio_volume_pending",
                TurnVisibleFacts.ContinueRetry,
                new JsonObject { ["level"] = requestedLevel });
        }

        if (string.Equals(operation.OperationName, "audio.mute", StringComparison.Ordinal)
            && arguments.TryGetProperty("state", out JsonElement state)
            && state.ValueKind is JsonValueKind.True or JsonValueKind.False)
        {
            return TurnVisibleFacts.Confirmation(
                "audio_mute_pending",
                TurnVisibleFacts.ContinueRetry,
                new JsonObject { ["mute"] = state.GetBoolean() });
        }

        return TurnVisibleFacts.Confirmation(
            "audio_adjust_pending",
            TurnVisibleFacts.ContinueRetry);
    }
}
