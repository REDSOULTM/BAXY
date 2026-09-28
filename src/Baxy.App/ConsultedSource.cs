using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

// M53 (paso 6 del goal v3, decisión D35 del dueño): lo que BAXY consultó en Wikipedia o
// Wikilibros se reproduce bajo CC BY-SA. La respuesta no nombra la fuente (la búsqueda
// es invisible); el mensaje publicado lleva la dirección de la página leída y la
// interfaz la muestra como un enlace discreto «fuente» debajo. Sólo cuando hubo una
// consulta real: un web.search verificado y con éxito cuya autoridad es de Wikimedia.
internal static class ConsultedSource
{
    private const int MaximumUrlCharacters = 2_048;

    internal static string? From(JsonObject facts)
    {
        ArgumentNullException.ThrowIfNull(facts);
        JsonObject? situation = facts["situation"] switch
        {
            JsonObject structured => structured,
            JsonValue value when value.TryGetValue(out string? text) => Parse(text),
            _ => null,
        };
        if (situation is null
            || (string?)situation["operation"] != "web.search"
            || situation["verified"]?.GetValueKind() != JsonValueKind.True
            || situation["succeeded"]?.GetValueKind() != JsonValueKind.True
            || situation["observed"] is not JsonObject observed
            || observed["authority"] is not JsonValue authorityValue
            || !authorityValue.TryGetValue(out string? authority)
            || !(authority.StartsWith("wikipedia_", StringComparison.Ordinal)
                || authority.StartsWith("wikibooks_", StringComparison.Ordinal))
            || observed["results"] is not JsonArray { Count: > 0 } results
            || results[0]?["url"] is not JsonValue urlValue
            || !urlValue.TryGetValue(out string? url))
        {
            return null;
        }

        return IsWikimediaPage(url) ? url : null;
    }

    // Una página https de Wikipedia o Wikilibros; nada que la interfaz pueda abrir fuera de ahí.
    internal static bool IsWikimediaPage(string? url) =>
        url is { Length: > 0 and <= MaximumUrlCharacters }
        && Uri.TryCreate(url, UriKind.Absolute, out Uri? uri)
        && uri.Scheme == Uri.UriSchemeHttps
        && uri.IsDefaultPort
        && string.IsNullOrEmpty(uri.UserInfo)
        && (uri.Host.EndsWith(".wikipedia.org", StringComparison.OrdinalIgnoreCase)
            || uri.Host.EndsWith(".wikibooks.org", StringComparison.OrdinalIgnoreCase));

    private static JsonObject? Parse(string? text)
    {
        if (string.IsNullOrWhiteSpace(text) || !text.TrimStart().StartsWith('{'))
        {
            return null;
        }

        try
        {
            return JsonNode.Parse(text) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
