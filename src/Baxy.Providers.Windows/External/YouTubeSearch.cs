using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>The video chosen from a YouTube results page: its id, its title when the page carries it, and whether that title
/// holds every word searched.</summary>
internal sealed record YouTubeSearchResult(string VideoId, string Title, string ErrorCode, bool TitleMatchesQuery = true)
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

    // Uso real 2026-10-21: «Red Ready» played «Rare Earth - Get Ready», YouTube's first result. Of the first videos, the
    // first whose title holds every word searched; with none, YouTube's first, told as not matching (the model then
    // does not tell it as what was asked for).
    private const int ResultsWeighed = 5;

    internal static YouTubeSearchResult Parse(string html, string? query = null)
    {
        if (Encoding.UTF8.GetByteCount(html) > 4_000_000)
            return new(string.Empty, string.Empty, "youtube_search_response_too_large");
        Match video = VideoRenderer().Match(html);
        if (video.Success)
        {
            string[] words = Words(query);
            if (words.Length == 0)
                return Result(html, video);
            YouTubeSearchResult first = Result(html, video);
            Match next = video;
            for (int weighed = 0; weighed < ResultsWeighed && next.Success; weighed++, next = next.NextMatch())
            {
                YouTubeSearchResult candidate = Result(html, next);
                if (Matches(candidate.Title, words))
                    return candidate;
            }

            return first with { TitleMatchesQuery = false };
        }
        // Ronda final 11 (regla 3): a consent page, a captcha or another markup has no results data: not read, never
        // «no video».
        return html.Contains("ytInitialData", StringComparison.Ordinal)
            ? new(string.Empty, string.Empty, "youtube_result_not_found")
            : new(string.Empty, string.Empty, "youtube_search_page_unreadable");
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

    // The words of a search, folded (lower case, no accents), each of two letters or more.
    private static string[] Words(string? text) =>
        Fold(text ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .Select(word => word.Trim('"', '\'', '«', '»', ',', '.', '-', ':', '¿', '?', '¡', '!'))
            .Where(word => word.Length >= 2)
            .ToArray();

    // Every word searched is a whole word of the title.
    private static bool Matches(string title, string[] words)
    {
        if (title.Length == 0)
            return false;
        var titleWords = new HashSet<string>(Words(title), StringComparer.Ordinal);
        return words.All(titleWords.Contains);
    }

    private static string Fold(string value)
    {
        string form = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var builder = new StringBuilder(form.Length);
        foreach (char character in form)
        {
            System.Globalization.UnicodeCategory category = System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character);
            if (category != System.Globalization.UnicodeCategory.NonSpacingMark)
                builder.Append(char.IsLetterOrDigit(character) ? character : ' ');
        }

        return builder.ToString();
    }

    [GeneratedRegex("\\\"videoRenderer\\\":\\{\\\"videoId\\\":\\\"([A-Za-z0-9_-]{11})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex VideoRenderer();

    [GeneratedRegex("\\\"title\\\":\\{\\\"runs\\\":\\[\\{\\\"text\\\":\\\"((?:[^\\\"\\\\]|\\\\.){1,400})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex RendererTitle();
}
