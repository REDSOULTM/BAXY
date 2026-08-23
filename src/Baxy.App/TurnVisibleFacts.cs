using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Hechos de un turno de shell. El modelo formula la frase; esto no se publica.
/// </summary>
internal static class TurnVisibleFacts
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    internal static readonly string[] ConfirmCancel =
        ["confirmar", "confirm", "cancelar", "cancel"];

    internal static readonly string[] ContinueCancel =
        ["continuar", "continue", "cancelar", "cancel"];

    internal static readonly string[] ContinueRetry =
        ["continuar", "continue", "retry"];

    internal static string Welcome() => Event("welcome");

    internal static string Failure(string cause, JsonObject? extra = null) =>
        Event("failure", cause, extra);

    internal static string Status(string cause, JsonObject? extra = null) =>
        Event("status", cause, extra);

    internal static string Clarification(string cause, JsonObject? extra = null) =>
        Event("clarification", cause, extra);

    internal static string Confirmation(string cause, IReadOnlyList<string> choices, JsonObject? extra = null)
    {
        JsonObject payload = Base("confirmation", cause);
        var array = new JsonArray();
        foreach (string choice in choices)
        {
            array.Add(choice);
        }

        payload["choices"] = array;
        Merge(payload, extra);
        return payload.ToJsonString(JsonOptions);
    }

    internal static string Event(string kind, string? cause = null, JsonObject? extra = null)
    {
        JsonObject payload = Base(kind, cause);
        Merge(payload, extra);
        return payload.ToJsonString(JsonOptions);
    }

    private static JsonObject Base(string kind, string? cause)
    {
        string polarity = kind switch
        {
            "failure" or "error" => "failure",
            "confirmation" or "clarification" => "pending",
            _ => "success",
        };
        var payload = new JsonObject
        {
            ["kind"] = kind,
            ["polarity"] = polarity,
        };
        if (!string.IsNullOrWhiteSpace(cause))
        {
            payload["cause"] = cause;
        }

        return payload;
    }

    private static void Merge(JsonObject payload, JsonObject? extra)
    {
        if (extra is null)
        {
            return;
        }

        foreach ((string key, JsonNode? value) in extra)
        {
            payload[key] = value?.DeepClone();
        }
    }
}
