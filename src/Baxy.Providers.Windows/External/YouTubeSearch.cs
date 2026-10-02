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
        return Parse(html);
    }

    internal static YouTubeSearchResult Parse(string html)
    {
        if (Encoding.UTF8.GetByteCount(html) > 4_000_000)
            return new(string.Empty, string.Empty, "youtube_search_response_too_large");
        Match video = VideoRenderer().Match(html);
        if (!video.Success)
            return new(string.Empty, string.Empty, "youtube_result_not_found");
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

    [GeneratedRegex("\\\"videoRenderer\\\":\\{\\\"videoId\\\":\\\"([A-Za-z0-9_-]{11})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex VideoRenderer();

    [GeneratedRegex("\\\"title\\\":\\{\\\"runs\\\":\\[\\{\\\"text\\\":\\\"((?:[^\\\"\\\\]|\\\\.){1,400})\\\"",
        RegexOptions.CultureInvariant)]
    private static partial Regex RendererTitle();
}
