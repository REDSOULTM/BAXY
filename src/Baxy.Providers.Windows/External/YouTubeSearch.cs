using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>The first video of a YouTube results page: its id and, when the page carries it, its title.</summary>
internal sealed record YouTubeSearchResult(string VideoId, string Title, string ErrorCode)
{
    internal bool Found => ErrorCode.Length == 0;

    internal Uri WatchUri => new("https://www.youtube.com/watch?v=" + VideoId);
}

internal static partial class YouTubeSearch
{
    internal static async ValueTask<YouTubeSearchResult> FirstVideoAsync(
        HttpClient http,
        string query,
        CancellationToken cancellationToken)
    {
        Uri search = new("https://www.youtube.com/results?search_query="
            + Uri.EscapeDataString(query));
        using var request = new HttpRequestMessage(HttpMethod.Get, search);
        request.Headers.UserAgent.ParseAdd("Mozilla/5.0 BAXY/1.0");
        using HttpResponseMessage response = await http.SendAsync(
            request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        string html = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        return Parse(html, query);
    }

    // Ronda 19 (r17 t1-c03 #4 «ponme el trailer en youtube» → «tráiler de Avatar» played «Tráiler Oficial Avatar: Los
    // Siete Refugios | Nueva Serie Original | Paramount+», the first result, another work): among the first results,
    // the one whose title carries every content word of the query and adds no subtitle of another work after a «:»
    // is played; when none does, the first, as before. A query that names the subtitle («Avatar La Leyenda de Aang»)
    // keeps it, and a first result that already fits is never passed over.
    private const int ResultsConsidered = 8;

    // Words that say what kind of video a subtitle segment is, not which work («Avatar: Tráiler oficial»).
    private static readonly HashSet<string> VideoFrameWords = new(StringComparer.Ordinal)
    {
        "trailer", "teaser", "oficial", "official", "final", "nuevo", "nueva", "new", "hd", "4k", "completo",
        "completa", "full", "espanol", "spanish", "latino", "subtitulado", "subtitulos", "sub", "subs", "version",
        "clip", "video", "avance", "promo", "doblado", "castellano", "english",
    };

    internal static YouTubeSearchResult Parse(string html, string query = "")
    {
        if (Encoding.UTF8.GetByteCount(html) > 4_000_000)
            return new(string.Empty, string.Empty, "youtube_search_response_too_large");
        List<YouTubeSearchResult> results = [];
        foreach (Match video in VideoRenderer().Matches(html))
        {
            results.Add(Result(html, video));
            if (results.Count == ResultsConsidered) break;
        }
        if (results.Count == 0)
            return new(string.Empty, string.Empty, "youtube_result_not_found");
        string[] terms = SearchPertinence.ContentTerms(query);
        if (terms.Length == 0) return results[0];
        return results.FirstOrDefault(result => Fits(result.Title, terms)) ?? results[0];
    }

    private static bool Fits(string title, string[] terms)
    {
        if (title.Length == 0) return false;
        var observed = new HashSet<string>(WikipediaSearchSource.FoldedWords(title), StringComparer.Ordinal);
        if (!terms.All(term => WebBrowserAdapter.MatchesSearchTerm(term, observed))) return false;
        var asked = new HashSet<string>(terms, StringComparer.Ordinal);
        foreach (Match subtitle in Subtitle().Matches(title))
        {
            // Revisión r19 («tyler the creator tiny desk» → «Tyler, The Creator: NPR Music Tiny Desk Concert»): a
            // subtitle that carries a word the query says is part of what was asked, however it describes it; only a
            // subtitle the query never touches names another work («Avatar: Los Siete Refugios» for «tráiler de
            // Avatar»).
            string[] words = SearchPertinence.ContentTerms(subtitle.Groups[1].Value)
                .Where(word => !word.All(char.IsAsciiDigit) && !VideoFrameWords.Contains(word))
                .ToArray();
            bool foreign = words.Length > 0 && !words.Any(word => WebBrowserAdapter.MatchesSearchTerm(word, asked));
            if (foreign) return false;
        }
        return true;
    }

    private static YouTubeSearchResult Result(string html, Match video)
    {
        // The renderer's own title follows its id within the same object; a
        // bounded window keeps a later result's title from being borrowed.
        int start = video.Index + video.Length;
        string window = html.Substring(start, Math.Min(6_000, html.Length - start));
        Match title = RendererTitle().Match(window);
        string text = string.Empty;
        if (title.Success)
        {
            try
            {
                using JsonDocument literal = JsonDocument.Parse("\"" + title.Groups[1].Value + "\"");
                text = literal.RootElement.GetString() ?? string.Empty;
            }
            catch (JsonException)
            {
                text = string.Empty;
            }
        }
        return new(video.Groups[1].Value, text.Trim(), string.Empty);
    }

    // What follows a «:» up to the next separator («|», « - », «(», «[», a dash) is a subtitle.
    [GeneratedRegex(@":\s*([^|:(\[–—]+?)(?=\s*(?:\||\s-\s|\(|\[|–|—|$))", RegexOptions.CultureInvariant)]
    private static partial Regex Subtitle();

    [GeneratedRegex("\\\"videoRenderer\\\":\\{\\\"videoId\\\":\\\"([A-Za-z0-9_-]{11})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex VideoRenderer();

    [GeneratedRegex("\\\"title\\\":\\{\\\"runs\\\":\\[\\{\\\"text\\\":\\\"((?:[^\\\"\\\\]|\\\\.){1,400})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex RendererTitle();
}
