using System.Buffers;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// D32 (dueño, 2026-09-28): la búsqueda funciona sola, sin cuenta ni clave de nadie.
// Desde el 26-09 los buscadores tratan como robot a esta red (desafíos, resultados
// basura), y raspar su HTML no sirve para un producto que se distribuye. Lo que un
// saber enciclopédico contesta («quién escribió Drácula», «capital de Australia»)
// lo contesta la API abierta de Wikipedia: una petición por idioma, en serie, con el
// User-Agent que pide la política de Wikimedia (nombre/versión y la URL del proyecto;
// nunca nada de la persona). Sale sólo la consulta, reducida a sus palabras de
// contenido.
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

    // Una enciclopedia no sabe lo que cambia cada día ni lo que hay cerca de la
    // persona: una consulta que nombra el momento, un precio, un horario, una noticia
    // o un marcador va directa al buscador general. Palabras plegadas (sin tildes).
    // Quedan fuera las que también nombran saberes («partido político», «Semana
    // Santa», «quién ganó el Mundial de 2010», «código abierto»).
    internal static bool IsEncyclopedic(string query) =>
        !FoldedWords(query).Any(TimeBoundWords.Contains);

    private static readonly HashSet<string> TimeBoundWords = new(StringComparer.Ordinal)
    {
        "hoy", "ahora", "actual", "actualmente", "anoche", "ayer", "manana",
        "noticia", "noticias", "precio", "precios", "cuesta", "cuestan", "cotizacion",
        "horario", "horarios", "abre", "cierra", "marcador", "cerca", "comprar",
        "oferta", "ofertas", "clima", "pronostico", "cartelera", "estreno", "estrenos",
        "today", "now", "current", "currently", "tonight", "yesterday", "tomorrow",
        "latest", "news", "price", "prices", "cost", "costs", "schedule", "hours",
        "opens", "closes", "score", "scores", "near", "nearby", "buy", "deal", "deals",
        "weather", "forecast", "showtimes",
    };

    // El idioma de la consulta elige la Wikipedia que se pregunta primero; la otra
    // queda de respaldo. Empate: el idioma de la persona, y si no es ni español ni
    // inglés, español (el del producto).
    internal static string[] Languages(string query, CultureInfo culture)
    {
        string[] words = FoldedWords(query);
        int english = words.Count(EnglishMarkers.Contains);
        int spanish = words.Count(SpanishMarkers.Contains)
            + (query.AsSpan().IndexOfAny(SpanishLetters) >= 0 ? 1 : 0);
        bool englishFirst = english != spanish
            ? english > spanish
            : culture.TwoLetterISOLanguageName == "en";
        return englishFirst ? ["en", "es"] : ["es", "en"];
    }

    private static readonly SearchValues<char> SpanishLetters = SearchValues.Create("áéíóúñÁÉÍÓÚÑ¿¡");

    private static readonly HashSet<string> EnglishMarkers = new(StringComparer.Ordinal)
    {
        "the", "of", "who", "what", "which", "when", "where", "why", "how", "is", "are",
        "was", "were", "did", "does", "do", "and", "in", "on", "an", "by", "wrote",
        "with", "first", "invented",
    };

    private static readonly HashSet<string> SpanishMarkers = new(StringComparer.Ordinal)
    {
        "el", "la", "los", "las", "de", "del", "que", "quien", "cual", "cuando", "donde",
        "como", "por", "para", "es", "son", "fue", "un", "una", "y", "en", "al", "primer",
        "primera", "escribio", "invento",
    };

    // Lo que se le pide a Wikipedia son las palabras de contenido; «internet»,
    // «google» o «wikipedia» dicen dónde mirar, no qué.
    internal static string Terms(IEnumerable<string> contentTokens) =>
        string.Join(' ', contentTokens.Where(static token => !WhereToLookWords.Contains(token)));

    private static readonly HashSet<string> WhereToLookWords = new(StringComparer.Ordinal)
    {
        "internet", "web", "google", "bing", "duckduckgo", "wikipedia", "online", "net",
    };

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
    internal async Task<List<(string Title, string Url, string Snippet)>?> SearchAsync(
        string language,
        string terms,
        int limit,
        CancellationToken cancellationToken)
    {
        if (terms.Length == 0) return null;
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
    // del artículo en texto plano. Las desambiguaciones no contestan nada y se
    // descartan; una dirección que no es de esa Wikipedia, también.
    internal static List<(string Title, string Url, string Snippet)> ParseSearchResponse(
        string body,
        string language)
    {
        using JsonDocument document = JsonDocument.Parse(body);
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object) throw new JsonException("Not a MediaWiki answer.");
        if (root.TryGetProperty("error", out _)) throw new JsonException("MediaWiki answered an error.");
        var ranked = new List<(int Index, string Title, string Url, string Snippet)>();
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
            .Select(static item => (item.Title, item.Url, item.Snippet))
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

    // Minúsculas sin tildes, partidas en todo lo que no es letra ni dígito.
    internal static string[] FoldedWords(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var normalized = new StringBuilder(decomposed.Length);
        bool separatorPending = false;
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }
            if (char.IsLetterOrDigit(character))
            {
                if (separatorPending && normalized.Length > 0) normalized.Append(' ');
                normalized.Append(char.ToLowerInvariant(character));
                separatorPending = false;
            }
            else
            {
                separatorPending = true;
            }
        }
        return normalized.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries);
    }
}
