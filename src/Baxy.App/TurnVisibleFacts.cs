using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Hechos de un resultado que la App proyecta (memoria), con la misma cabecera que el núcleo: «status» y, si falló,
/// «error». El modelo formula la frase; esto no se publica.
/// </summary>
internal static class TurnVisibleFacts
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    internal static string Failure(string cause, JsonObject? extra = null) =>
        Event(new JsonObject { ["status"] = "failed", ["error"] = cause }, extra);

    internal static string Status(string cause, JsonObject? extra = null) =>
        Event(new JsonObject { ["status"] = "completed", ["cause"] = cause }, extra);

    private static string Event(JsonObject payload, JsonObject? extra)
    {
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
