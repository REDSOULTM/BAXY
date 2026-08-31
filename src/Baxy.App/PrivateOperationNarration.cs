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
        return TurnVisibleFacts.Clarification(cause);
    }

    internal static string CreateMemoryConfirmationPrompt(
        PreparedOperation prepared,
        bool reconciliationRequired = false)
    {
        if (reconciliationRequired)
        {
            return TurnVisibleFacts.Confirmation(
                "memory_reconcile_same_attempt",
                ["confirmar", "confirm"]);
        }

        string cause = prepared.OperationName switch
        {
            "memory.sensitive.save" => "memory_sensitive_save",
            "memory.forget" => "memory_forget_irreversible",
            "memory.enable" => "memory_enable",
            "memory.export" => "memory_export_privacy",
            _ => "memory_needs_confirmation",
        };
        JsonObject? extra = string.Equals(cause, "memory_export_privacy", StringComparison.Ordinal)
            ? new JsonObject
            {
                ["destination"] = "Documents/BAXY",
                ["mayRedirectOrSync"] = true,
            }
            : null;
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
        string category = prepared.OperationName switch
        {
            "memory.enable" or "memory.disable" => "memory_config",
            "memory.save" or "memory.sensitive.save" or "memory.correct" =>
                "memory_update",
            "memory.forget" or "memory.session.clear" => "memory_erase",
            "memory.recall" or "memory.list" or "memory.status" => "memory_query",
            "memory.export" => "memory_export",
            _ => "memory_request",
        };
        return TurnVisibleFacts.Confirmation(
            "memory_recovery_pending",
            TurnVisibleFacts.ContinueCancel,
            new JsonObject { ["category"] = category });
    }

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
