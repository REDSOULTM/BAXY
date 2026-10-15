using System.Xml.Linq;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The public Google News RSS search that web.search with source=news asks, in the edition of the language the model
/// chose (es or en). Auditoría final de BAXY Renew: web.news.headlines, which read the same feed, was retired as a
/// second door to it.
/// </summary>
internal static class GoogleNewsFeed
{
    private const string FeedAuthority = "https://news.google.com/rss";
    private const string Edition = "hl=es-419&gl=CL&ceid=CL:es-419";
    private const string EnglishEdition = "hl=en-US&gl=US&ceid=US:en";

    internal static Uri SearchUri(string topic, string language) =>
        new(FeedAuthority + "/search?q=" + Uri.EscapeDataString(topic) + "&"
            + (language == "en" ? EnglishEdition : Edition));

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

    internal readonly record struct Headline(string Title, string Source, string PublishedAt, string Url);
}
