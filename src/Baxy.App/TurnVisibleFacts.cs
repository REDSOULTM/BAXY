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

    internal static string LastResortFailureProse(string? cause)
    {
        // Only when the composer produced no text after its bounded retries.
        // The live prompt already names these causes; silence is the worse lie.
        string key = (cause ?? "").Trim().ToLowerInvariant();
        return key switch
        {
            "no_response" or "provider_down" or "composer_request_failed"
                or "composer_unavailable" => "No pude: no responde.",
            "timeout" => "No pude: se agotó el tiempo.",
            "composition_lost_verified_facts" =>
                "No pude: no pude formular el resultado.",
            _ => "No pude: no pude formular el resultado.",
        };
    }

    internal static string LastResortProse(string? cause, string? source)
    {
        if (!string.IsNullOrWhiteSpace(source)
            && TryVerifiedOpenProse(source) is { Length: > 0 } prose)
        {
            return prose;
        }

        return LastResortFailureProse(cause);
    }

    private static string? TryVerifiedOpenProse(string source)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return null;
            }

            if (root.TryGetProperty("steps", out JsonElement steps)
                && steps.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement step in steps.EnumerateArray())
                {
                    if (step.ValueKind == JsonValueKind.String
                        && step.GetString() is { Length: > 0 } nested
                        && TryVerifiedOpenProse(nested) is { Length: > 0 } fromStep)
                    {
                        return fromStep;
                    }
                }
            }

            string? name = null;
            if (root.TryGetProperty("observed", out JsonElement observed)
                && observed.ValueKind == JsonValueKind.Object
                && observed.TryGetProperty("displayName", out JsonElement displayName)
                && displayName.ValueKind == JsonValueKind.String)
            {
                name = displayName.GetString();
            }

            string? polarity = root.TryGetProperty("polarity", out JsonElement polarityNode)
                && polarityNode.ValueKind == JsonValueKind.String
                    ? polarityNode.GetString()
                    : null;
            string? cause = root.TryGetProperty("cause", out JsonElement causeNode)
                && causeNode.ValueKind == JsonValueKind.String
                    ? causeNode.GetString()
                    : null;
            bool success = string.Equals(polarity, "success", StringComparison.Ordinal)
                || cause is "opened" or "focused" or "mission_completed";
            if (!success || string.IsNullOrWhiteSpace(name))
            {
                return null;
            }

            bool feminine = name.EndsWith('a')
                || name.Contains("calculadora", StringComparison.OrdinalIgnoreCase);
            return feminine
                ? "Listo, " + name + " está abierta."
                : "Listo, " + name + " está abierto.";
        }
        catch (JsonException)
        {
            return null;
        }
    }

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
