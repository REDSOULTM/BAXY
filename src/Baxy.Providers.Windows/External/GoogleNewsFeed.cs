using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The public Google News RSS search that web.search with source=news asks, in the edition of the language the model
/// chose (es or en). Auditoría final de BAXY Renew: web.news.headlines, which read the same feed, was retired as a
/// second door to it.
/// <para>
/// uso-82 (AMD e2e 2026-11-04, «¿Quién ganó la Copa América 2024?»; holdout v5 H5): each item's link is a Google News
/// link (news.google.com/rss/articles/…), not the outlet's page, and reading it gave Google's own page, with no article:
/// the model wrote an outlet address none of the results gave (held as host_not_from_session, or a 404). Google News is
/// now asked which article each link leads to (<see cref="ArticleAddressRequest"/>), as its own article page asks it, so
/// a result's address is its outlet's article. The outlet's site (the item's <c>&lt;source url&gt;</c>, RSS 2.0's
/// channel the item came from) is not given apart: given as a field, the model read that home page instead of the
/// article (2026-11-04, real model: 3 of 3 «Copa América» turns, and facebook.com, infobae.com and latimes.com in
/// another). The item's <c>&lt;description&gt;</c> is not kept either: in the search feed it repeats the title and the
/// outlet and nothing else (200 of 200 items, two searches read on 2026-11-04).
/// </para>
/// </summary>
internal static partial class GoogleNewsFeed
{
    private const string FeedAuthority = "https://news.google.com/rss";
    private const string Edition = "hl=es-419&gl=CL&ceid=CL:es-419";
    private const string EnglishEdition = "hl=en-US&gl=US&ceid=US:en";

    /// <summary>Where Google News answers the article a link leads to (its own pages ask it there).</summary>
    internal static readonly Uri ArticleAddressEndpoint = new("https://news.google.com/_/DotsSplashUi/data/batchexecute");

    // The request's inner JSON goes as a string inside the outer one, quotes escaped as «\"», as the page writes it.
    private static readonly JsonSerializerOptions AsWritten =
        new() { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

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

    /// <summary>The article id of a Google News link (news.google.com/rss/articles/{id} or /articles/{id}); null for
    /// any other address.</summary>
    internal static string? ArticleId(Uri address)
    {
        if (!string.Equals(address.Host, "news.google.com", StringComparison.OrdinalIgnoreCase))
            return null;
        string path = address.AbsolutePath;
        foreach (string prefix in (string[])["/rss/articles/", "/articles/"])
        {
            if (path.StartsWith(prefix, StringComparison.Ordinal)
                && path[prefix.Length..] is { Length: > 0 } id && !id.Contains('/', StringComparison.Ordinal))
                return id;
        }

        return null;
    }

    /// <summary>
    /// The one request that asks Google News which article each link leads to: each link's id with the signature and
    /// time its page carries (<c>data-n-a-sg</c>, <c>data-n-a-ts</c>), as that page's own script asks it (the
    /// «garturlreq» call of its batchexecute endpoint; the method the open-source google-news-url-decoder documents,
    /// 2024-2025), numbered by its place in <paramref name="articles"/> from 1. A page without a signature (not an
    /// article page, or Google changed it) is left out; null when none has one.
    /// </summary>
    internal static FormUrlEncodedContent? ArticleAddressRequest(IReadOnlyList<(string Id, string Page)> articles)
    {
        var calls = new JsonArray();
        for (int index = 0; index < articles.Count; index++)
        {
            (string id, string page) = articles[index];
            Match signature = SignaturePattern().Match(page);
            Match timestamp = TimestampPattern().Match(page);
            if (!signature.Success || !timestamp.Success
                || !long.TryParse(timestamp.Groups[1].Value, System.Globalization.NumberStyles.None,
                    System.Globalization.CultureInfo.InvariantCulture, out long time))
                continue;
            var client = new JsonArray(
                new JsonArray("X", "X", new JsonArray("X", "X"), null, null, 1, 1, "US:en", null, 1, null, null, null,
                    null, null, 0, 1),
                "X", "X", 1, new JsonArray(1, 1, 1), 1, 1, null, 0, 0, null, 0);
            string inner = new JsonArray("garturlreq", client, id, time, signature.Groups[1].Value).ToJsonString(AsWritten);
            calls.Add((JsonNode)new JsonArray("Fbv4je", inner, null,
                (index + 1).ToString(System.Globalization.CultureInfo.InvariantCulture)));
        }

        return calls.Count == 0
            ? null
            : new FormUrlEncodedContent(
                [new KeyValuePair<string, string>("f.req", new JsonArray(calls).ToJsonString(AsWritten))]);
    }

    /// <summary>The outlet's article address of each call Google News answered to <see cref="ArticleAddressRequest"/>,
    /// by the call's number; a call whose answer is not a web address off Google News is left out.</summary>
    internal static Dictionary<int, Uri> ArticleAddresses(string answer)
    {
        var addresses = new Dictionary<int, Uri>();
        // «)]}'», a blank line, then the calls' answers: ["wrb.fr","Fbv4je","[\"garturlres\",\"URL\",1]",…,"n"].
        int start = answer.IndexOf("\n\n", StringComparison.Ordinal);
        if (start < 0)
            return addresses;
        try
        {
            using JsonDocument calls = JsonDocument.Parse(answer[(start + 2)..]);
            if (calls.RootElement.ValueKind != JsonValueKind.Array)
                return addresses;
            foreach (JsonElement call in calls.RootElement.EnumerateArray())
            {
                if (call.ValueKind != JsonValueKind.Array || call.GetArrayLength() < 7
                    || call[1].ValueKind != JsonValueKind.String || call[1].GetString() != "Fbv4je"
                    || call[2].ValueKind != JsonValueKind.String || call[6].ValueKind != JsonValueKind.String
                    || !int.TryParse(call[6].GetString(), System.Globalization.NumberStyles.None,
                        System.Globalization.CultureInfo.InvariantCulture, out int number))
                    continue;
                using JsonDocument result = JsonDocument.Parse(call[2].GetString()!);
                if (result.RootElement.ValueKind == JsonValueKind.Array && result.RootElement.GetArrayLength() > 1
                    && result.RootElement[0].ValueKind == JsonValueKind.String
                    && result.RootElement[0].GetString() == "garturlres"
                    && result.RootElement[1].ValueKind == JsonValueKind.String
                    && Uri.TryCreate(result.RootElement[1].GetString(), UriKind.Absolute, out Uri? article)
                    && article.Scheme is "https" or "http"
                    && !string.Equals(article.Host, "news.google.com", StringComparison.OrdinalIgnoreCase))
                    addresses[number] = article;
            }
        }
        catch (JsonException)
        {
            return addresses;
        }

        return addresses;
    }

    [GeneratedRegex("data-n-a-sg=\"([^\"]+)\"", RegexOptions.CultureInvariant)]
    private static partial Regex SignaturePattern();

    [GeneratedRegex("data-n-a-ts=\"([0-9]+)\"", RegexOptions.CultureInvariant)]
    private static partial Regex TimestampPattern();

    internal readonly record struct Headline(string Title, string Source, string PublishedAt, string Url);
}
