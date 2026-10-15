using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// D32 (dueño, 2026-09-28): la búsqueda funciona sola, sin cuenta ni clave de nadie. web.search con
// source=encyclopedia pregunta a la API abierta de Wikipedia, en el idioma que eligió el modelo (language), con el
// User-Agent que pide la política de Wikimedia (nombre/versión y la URL del proyecto; nunca nada de la persona). Sale
// sólo la consulta tal como la escribió el modelo; vuelve cada artículo con el inicio que la API devuelve.
internal sealed class WikipediaSearchSource(HttpClient http)
{
    private const string ProjectUrl = "https://github.com/REDSOULTM/baxy-assistant";

    // Formato recomendado por Wikimedia: «<cliente>/<versión> (<contacto>)».
    internal static string UserAgent { get; } = "BAXY/"
        + (typeof(WikipediaSearchSource).Assembly.GetName().Version is { } version
            ? version.ToString(2) : "1.0")
        + " (" + ProjectUrl + ")";

    private readonly HttpClient _http = http ?? throw new ArgumentNullException(nameof(http));

    internal static string Authority(string language) => "wikipedia_" + language + "_api";

    internal static Uri SearchUri(string language, string terms, int limit)
    {
        int count = Math.Clamp(limit, 1, 10);
        return new Uri("https://" + language + ".wikipedia.org/w/api.php"
            + "?action=query&format=json&formatversion=2"
            + "&generator=search&gsrnamespace=0&gsrlimit=" + count
            + "&gsrsearch=" + Uri.EscapeDataString(terms)
            + "&prop=extracts%7Cinfo%7Cpageprops&exintro=1&explaintext=1&exsentences=3"
            + "&exlimit=" + count + "&inprop=url&ppprop=disambiguation");
    }

    // Null cuando Wikipedia no contestó (red, estado HTTP, cuerpo que no es su JSON):
    // no se buscó, que no es lo mismo que no encontrar.
    internal async Task<List<(string Title, string Url, string Extract)>?> SearchAsync(
        string language,
        string terms,
        int limit,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, SearchUri(language, terms, limit));
        request.Headers.TryAddWithoutValidation("User-Agent", UserAgent);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            string body = await WebBrowserAdapter.ReadBoundedTextAsync(response, 1_000_000, cancellationToken)
                .ConfigureAwait(false);
            return ParseSearchResponse(body, language);
        }
        catch (HttpRequestException)
        {
            return null;
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // Cada página trae su puesto en la búsqueda («index»), su dirección y el inicio
    // del artículo en texto plano. Una página que la propia API marca como
    // desambiguación no es un artículo y se descarta; una dirección que no es de esa
    // Wikipedia, también.
    internal static List<(string Title, string Url, string Extract)> ParseSearchResponse(
        string body,
        string language)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object) throw new JsonException("Not a MediaWiki answer.");
        if (root.TryGetProperty("error", out _)) throw new JsonException("MediaWiki answered an error.");
        var ranked = new List<(int Index, string Title, string Url, string Extract)>();
        if (!root.TryGetProperty("query", out JsonElement query)
            || !query.TryGetProperty("pages", out JsonElement pages)
            || pages.ValueKind != JsonValueKind.Array)
        {
            return [];
        }
        string host = language + ".wikipedia.org";
        foreach (JsonElement page in pages.EnumerateArray())
        {
            if (page.ValueKind != JsonValueKind.Object
                || (page.TryGetProperty("pageprops", out JsonElement props)
                    && props.ValueKind == JsonValueKind.Object
                    && props.TryGetProperty("disambiguation", out _)))
            {
                continue;
            }
            string title = StringOf(page, "title");
            string url = StringOf(page, "fullurl");
            if (title.Length is 0 or > 4_096
                || !Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                || parsed.Scheme != Uri.UriSchemeHttps
                || !string.Equals(parsed.Host, host, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            int index = page.TryGetProperty("index", out JsonElement position)
                && position.TryGetInt32(out int value) ? value : int.MaxValue;
            ranked.Add((index, title, parsed.AbsoluteUri, PlainText(StringOf(page, "extract"))));
        }
        return ranked
            .OrderBy(static item => item.Index)
            .Select(static item => (item.Title, item.Url, item.Extract))
            .ToList();
    }

    private static string StringOf(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    // El extracto trae espacios de ancho cero y saltos de párrafo; queda una línea.
    private static string PlainText(string extract)
    {
        string text = extract.Replace("​", string.Empty, StringComparison.Ordinal);
        string joined = string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return joined.Length <= 1_000 ? joined : joined[..1_000];
    }
}
