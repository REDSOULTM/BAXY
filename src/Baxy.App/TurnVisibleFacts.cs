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

    internal static string Failure(string cause, JsonObject? extra = null) =>
        Event("failure", "failure", cause, extra);

    internal static string Status(string cause, JsonObject? extra = null) =>
        Event("status", "success", cause, extra);

    private static string Event(string kind, string polarity, string cause, JsonObject? extra)
    {
        var payload = new JsonObject
        {
            ["kind"] = kind,
            ["polarity"] = polarity,
            ["cause"] = cause,
        };
        Merge(payload, extra);
        return payload.ToJsonString(JsonOptions);
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
