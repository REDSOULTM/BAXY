using System.Text.Json;

namespace Baxy.App;

/// <summary>
/// Identifies which public-response route produced a visible text. The same
/// compose path authors the words; this only names the route for evidence.
/// </summary>
internal static class PublicResponseRoute
{
    internal const string Welcome = "welcome";
    internal const string Conversation = "conversation";
    internal const string Clarification = "clarification";
    internal const string Confirmation = "confirmation";
    internal const string Progress = "progress";
    internal const string Result = "result";
    internal const string Error = "error";
    internal const string MissionSummary = "mission-summary";

    internal static string FromDraft(UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        if (draft.Intent == "welcome")
        {
            return Welcome;
        }

        if (draft.Intent == "confirmation")
        {
            return Confirmation;
        }

        if (draft.Intent == "clarification")
        {
            return Clarification;
        }

        if (draft.Intent == "error")
        {
            return Error;
        }

        if (UserMessagePolicy.IsStructuredFacts(draft.Source)
            && TryReadKindCause(draft.Source, out string kind, out string cause))
        {
            if (string.Equals(cause, "acting", StringComparison.Ordinal))
            {
                return Progress;
            }

            if (string.Equals(cause, "mission_completed", StringComparison.Ordinal))
            {
                return MissionSummary;
            }

            if (string.Equals(kind, "failure", StringComparison.Ordinal)
                || string.Equals(kind, "error", StringComparison.Ordinal))
            {
                return Error;
            }

            if (string.Equals(kind, "operation", StringComparison.Ordinal)
                || string.Equals(kind, "status", StringComparison.Ordinal))
            {
                return Result;
            }
        }

        return draft.Intent == "status" ? Result : Conversation;
    }

    private static bool TryReadKindCause(string source, out string kind, out string cause)
    {
        kind = string.Empty;
        cause = string.Empty;
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            if (root.TryGetProperty("kind", out JsonElement kindElement)
                && kindElement.GetString() is { Length: > 0 } kindValue)
            {
                kind = kindValue;
            }

            if (root.TryGetProperty("cause", out JsonElement causeElement)
                && causeElement.GetString() is { Length: > 0 } causeValue)
            {
                cause = causeValue;
            }

            return kind.Length > 0 || cause.Length > 0;
        }
        catch (JsonException)
        {
            return false;
        }
    }
}
