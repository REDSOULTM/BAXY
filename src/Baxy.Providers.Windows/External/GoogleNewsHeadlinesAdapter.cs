using System.Net.Http;
using System.Text.Json;
using System.Xml.Linq;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo N): la encuesta pide las
/// noticias, no nombres de portales. Esta lectura trae los titulares del día
/// (o los de un tema nombrado) de un canal RSS público, cada uno con su medio
/// y su hora; el final los cita tal cual y no resume nada en voz propia.
/// </summary>
internal sealed class GoogleNewsHeadlinesAdapter : IExternalOperationAdapter, IDisposable
{
    private const string FeedAuthority = "https://news.google.com/rss";
    private const string Edition = "hl=es-419&gl=CL&ceid=CL:es-419";

    private readonly HttpClient _http;
    private readonly Func<string, CancellationToken, Task<string>>? _fetch;

    internal GoogleNewsHeadlinesAdapter()
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(12) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 news-read");
    }

    // Las pruebas entregan el canal sin red.
    internal GoogleNewsHeadlinesAdapter(Func<string, CancellationToken, Task<string>> fetch)
    {
        _http = new HttpClient();
        _fetch = fetch;
    }

    public bool CanHandle(string operation) => operation is "web.news.headlines";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string? topic = null;
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("topic", out JsonElement named)
            && named.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(named.GetString()))
        {
            topic = named.GetString()!.Trim();
        }

        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 5), 1, 10);
        string url = topic is null
            ? FeedAuthority + "?" + Edition
            : FeedAuthority + "/search?q=" + Uri.EscapeDataString(topic) + "&" + Edition;
        string xml;
        try
        {
            xml = _fetch is not null
                ? await _fetch(url, cancellationToken).ConfigureAwait(false)
                : await _http.GetStringAsync(url, cancellationToken).ConfigureAwait(false);
        }
        catch (HttpRequestException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "news_feed_unavailable");
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.FailureBeforeEffect(operation, "news_feed_unavailable");
        }

        List<Headline> headlines;
        try
        {
            headlines = Parse(xml, limit);
        }
        catch (System.Xml.XmlException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "news_feed_unreadable");
        }

        if (headlines.Count == 0)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, topic is null ? "news_feed_empty" : "news_topic_without_headlines");
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            if (topic is not null)
                writer.WriteString("topic", topic);
            writer.WriteString("edition", "es-419/CL");
            writer.WriteNumber("count", headlines.Count);
            writer.WriteStartArray("headlines");
            foreach (Headline headline in headlines)
            {
                writer.WriteStartObject();
                writer.WriteString("title", headline.Title);
                writer.WriteString("source", headline.Source);
                writer.WriteString("publishedAt", headline.PublishedAt);
                writer.WriteString("url", headline.Url);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteString("authority", "google_news_rss_es419_cl");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    internal static List<Headline> Parse(string xml, int limit)
    {
        XDocument document = XDocument.Parse(xml);
        var headlines = new List<Headline>();
        foreach (XElement item in document.Descendants("item"))
        {
            string rawTitle = (item.Element("title")?.Value ?? string.Empty).Trim();
            if (rawTitle.Length == 0)
                continue;
            string source = (item.Element("source")?.Value ?? string.Empty).Trim();
            string title = rawTitle;
            // El canal escribe «Titular - Medio»; el medio también viene en su
            // propio elemento, así que el titular se queda sin la cola.
            int separator = rawTitle.LastIndexOf(" - ", StringComparison.Ordinal);
            if (separator > 0)
            {
                string tail = rawTitle[(separator + 3)..].Trim();
                if (source.Length == 0 || string.Equals(tail, source, StringComparison.OrdinalIgnoreCase))
                {
                    title = rawTitle[..separator].Trim();
                    if (source.Length == 0)
                        source = tail;
                }
            }

            headlines.Add(new Headline(
                title,
                source,
                (item.Element("pubDate")?.Value ?? string.Empty).Trim(),
                (item.Element("link")?.Value ?? string.Empty).Trim()));
            if (headlines.Count >= limit)
                break;
        }

        return headlines;
    }

    public void Dispose() => _http.Dispose();

    internal readonly record struct Headline(string Title, string Source, string PublishedAt, string Url);
}
