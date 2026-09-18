using System.Buffers;
using System.Diagnostics;
using System.Globalization;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;
using Baxy.Security.Windows;

namespace Baxy.Providers.Windows.External;

internal sealed class WebBrowserAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly CdpBrowserSession _browser;
    private readonly CdpBrowserSessionContext? _sessionContext;
    private readonly HttpClient _http;
    private readonly string? _searchDiagnosticPath;

    internal WebBrowserAdapter(string dataRoot)
        : this(dataRoot, sessionContext: null)
    {
    }

    internal WebBrowserAdapter(string dataRoot, CdpBrowserSessionContext? sessionContext)
    {
        _browser = new CdpBrowserSession(Path.Combine(dataRoot, "browser-profile"));
        _sessionContext = sessionContext;
        _searchDiagnosticPath = Path.Combine(dataRoot, "captures", "web-search-rejections.jsonl");
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 structured-search");
    }

    internal WebBrowserAdapter(
        CdpBrowserSession browser,
        HttpClient http,
        CdpBrowserSessionContext? sessionContext = null)
    {
        _browser = browser ?? throw new ArgumentNullException(nameof(browser));
        _http = http ?? throw new ArgumentNullException(nameof(http));
        _sessionContext = sessionContext;
    }

    public bool CanHandle(string operation) => operation is
        "browser.control" or "browser.navigate" or "browser.page.read" or "browser.tabs.list"
        or "media.play.youtube"
        or "streaming.navigate" or "streaming.play.named" or "web.search";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return operation switch
            {
                "browser.control" => await ControlAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "browser.navigate" => await NavigateAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "browser.page.read" => await ReadPageAsync(operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                "browser.tabs.list" => await ListTabsAsync(operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                "media.play.youtube" => await PlayYouTubeAsync(
                    operation, arguments, effectBoundary, cancellationToken).ConfigureAwait(false),
                "streaming.navigate" => await StreamingAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "streaming.play.named" => await PlayStreamingNamedAsync(
                    operation, arguments, effectBoundary, cancellationToken).ConfigureAwait(false),
                "web.search" => await SearchAsync(
                    operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "web_adapter_unavailable");
        }
        catch (InvalidDataException)
        {
            return effectBoundary.Failure(operation, "web_argument_invalid");
        }
        catch (Exception exception) when (exception is IOException
            or HttpRequestException or WebSocketException or JsonException
            or TimeoutException or XmlException)
        {
            return effectBoundary.Failure(operation, "web_adapter_unavailable");
        }
    }

    public void Dispose()
    {
        _browser.Dispose();
        _http.Dispose();
    }

    private async ValueTask<ExternalCapabilityReceipt> ControlAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string action = ExternalJson.RequiredString(arguments, "action");
        CdpBrowserSession browser = _sessionContext?.Active ?? _browser;
        effectBoundary.Cross(cancellationToken);
        CdpBrowserControlResult control = await browser.ControlAsync(action, cancellationToken)
            .ConfigureAwait(false);
        if (!control.Verified)
            return effectBoundary.Failure(operation, control.ErrorCode, control.EffectObserved);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("action", control.Action);
            writer.WriteString("targetId", control.TargetId);
            writer.WriteString("observedState", control.ObservedState);
            writer.WriteString("authority", "cdp_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, control.EffectObserved);
    }

    private async ValueTask<ExternalCapabilityReceipt> NavigateAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        Uri target = RequireWebUri(ExternalJson.RequiredString(arguments, "url"));
        _sessionContext?.Activate(_browser);
        effectBoundary.Cross(cancellationToken);
        CdpNavigationResult navigation = await _browser.NavigateAsync(target, cancellationToken)
            .ConfigureAwait(false);
        if (!navigation.Verified)
        {
            return effectBoundary.Failure(
                operation, navigation.ErrorCode, navigation.EffectObserved);
        }
        return ExternalJson.Success(operation, NavigationResult(navigation, "cdp"));
    }

    private async ValueTask<ExternalCapabilityReceipt> ReadPageAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int maximumCharacters = Math.Clamp(
            ExternalJson.OptionalInt(arguments, "maximumCharacters", 12_000), 256, 32_768);
        CdpBrowserSession browser = _sessionContext?.Active ?? _browser;
        CdpPageReadResult page = await browser.ReadPageAsync(maximumCharacters, cancellationToken)
            .ConfigureAwait(false);
        if (!page.Verified)
            return ExternalJson.Failure(operation, page.ErrorCode);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("targetId", page.TargetId);
            writer.WriteString("url", page.Url);
            writer.WriteString("title", page.Title);
            writer.WriteString("text", page.Text);
            writer.WriteBoolean("truncated", page.Truncated);
            writer.WriteString("authority", "cdp_dom_visible_text_snapshot");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> ListTabsAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 50);
        CdpBrowserSession browser = _sessionContext?.Active ?? _browser;
        CdpBrowserTabsResult tabs = await browser.ListTabsAsync(limit, cancellationToken)
            .ConfigureAwait(false);
        if (!tabs.Verified)
            return ExternalJson.Failure(operation, tabs.ErrorCode);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("count", tabs.TotalCount);
            writer.WriteBoolean("truncated", tabs.Truncated);
            writer.WriteStartArray("tabs");
            foreach (CdpBrowserTab tab in tabs.Tabs)
            {
                writer.WriteStartObject();
                writer.WriteString("targetId", tab.TargetId);
                writer.WriteString("title", tab.Title);
                writer.WriteString("url", tab.Url);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "cdp_page_targets_snapshot");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> StreamingAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string service = ExternalJson.RequiredString(arguments, "service");
        Uri target = RequireWebUri(ExternalJson.RequiredString(arguments, "resourceUri"));
        if (!HostMatchesService(target.Host, service))
        {
            return ExternalJson.Failure(operation, "streaming_resource_service_mismatch");
        }
        _sessionContext?.Activate(_browser);
        effectBoundary.Cross(cancellationToken);
        CdpNavigationResult navigation = await _browser.NavigateAsync(target, cancellationToken)
            .ConfigureAwait(false);
        if (!navigation.Verified)
        {
            return effectBoundary.Failure(
                operation, navigation.ErrorCode, navigation.EffectObserved);
        }
        Uri final = RequireWebUri(navigation.FinalUrl);
        if (!HostMatchesService(final.Host, service))
        {
            return ExternalJson.Failure(operation, "streaming_redirect_left_service", true);
        }
        if (final.AbsolutePath.Contains("login", StringComparison.OrdinalIgnoreCase)
            || final.AbsolutePath.Contains("signin", StringComparison.OrdinalIgnoreCase))
        {
            return ExternalJson.Failure(operation, "streaming_authentication_required", true);
        }
        JsonElement result = NavigationResult(navigation, "authenticated_cdp");
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("resourceUri", result.GetProperty("finalUrl").GetString());
            writer.WriteString("targetId", result.GetProperty("targetId").GetString());
            writer.WriteString("authority", "authenticated_cdp_session");
            writer.WriteEndObject();
        }));
    }

    private async ValueTask<ExternalCapabilityReceipt> PlayStreamingNamedAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string service = ExternalJson.RequiredString(arguments, "service");
        string title = ExternalJson.RequiredString(arguments, "title").Trim();
        if (service != "netflix" || title.Length == 0)
            return ExternalJson.Failure(operation, "streaming_named_argument_invalid");
        _sessionContext?.Activate(_browser);
        effectBoundary.Cross(cancellationToken);
        CdpStreamingPlaybackResult playback = await _browser.PlayNetflixAsync(
            title, cancellationToken).ConfigureAwait(false);
        if (!playback.Verified)
            return effectBoundary.Failure(
                operation, playback.ErrorCode, playback.EffectObserved);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("service", service); writer.WriteString("title", title);
            writer.WriteString("finalUrl", playback.FinalUrl);
            writer.WriteString("pageTitle", playback.PageTitle);
            writer.WriteString("targetId", playback.TargetId);
            writer.WriteString("playbackStatus", "playing");
            writer.WriteNumber("observedProgressSeconds", playback.ObservedProgressSeconds);
            writer.WriteString("authority", "netflix_cdp_video_progress_postread");
            writer.WriteEndObject();
        }), playback.EffectObserved);
    }

    private async ValueTask<ExternalCapabilityReceipt> PlayYouTubeAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string query = ExternalJson.RequiredString(arguments, "query");
        Uri search = new("https://www.youtube.com/results?search_query="
            + Uri.EscapeDataString(query));
        using var request = new HttpRequestMessage(HttpMethod.Get, search);
        request.Headers.UserAgent.ParseAdd("Mozilla/5.0 BAXY/1.0");
        using HttpResponseMessage response = await _http.SendAsync(
            request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        string html = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        if (Encoding.UTF8.GetByteCount(html) > 4_000_000)
            return effectBoundary.Failure(operation, "youtube_search_response_too_large");
        Match video = Regex.Match(
            html,
            "\\\"videoRenderer\\\":\\{\\\"videoId\\\":\\\"([A-Za-z0-9_-]{11})\\\"",
            RegexOptions.CultureInvariant);
        if (!video.Success)
            return effectBoundary.Failure(operation, "youtube_result_not_found");
        Uri watchUri = new("https://www.youtube.com/watch?v=" + video.Groups[1].Value);
        _sessionContext?.Activate(_browser);
        effectBoundary.Cross(cancellationToken);
        CdpMediaPlaybackResult playback = await _browser.PlayYouTubeAsync(
            query, watchUri, cancellationToken)
            .ConfigureAwait(false);
        if (!playback.Verified)
            return effectBoundary.Failure(
                operation, playback.ErrorCode, playback.EffectObserved);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "youtube");
            writer.WriteString("query", query);
            writer.WriteString("title", playback.Title);
            writer.WriteString("finalUrl", playback.FinalUrl);
            writer.WriteString("targetId", playback.TargetId);
            writer.WriteString("playbackStatus", "playing");
            writer.WriteString("authority", "youtube_cdp_video_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, playback.EffectObserved);
    }

    // WEB1831 / H0060: Bing's RSS feed answered a Spanish question («por qué suele
    // fallar whatsapp») with navigational pages that share no word with it (measured
    // 2026-09-18 on REDPC: Gmail, WhatsApp home pages, unrelated feeds), so every
    // honest search ended web_search_results_irrelevant. The same engine's HTML page,
    // asked with the product's own User-Agent, lists ten organic results that answer
    // the question, so the provider reads that page; the pertinence gate stays.
    private const string SearchEndpoint = "https://www.bing.com/search";

    private async ValueTask<ExternalCapabilityReceipt> SearchAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string query = ExternalJson.RequiredString(arguments, "query").Trim();
        string[] queryTokens = SearchTokens(query);
        if (queryTokens.Length == 0)
        {
            throw new InvalidDataException("The search query has no verifiable terms.");
        }
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 5), 1, 20);
        Uri endpoint = new(SearchEndpoint + "?q=" + Uri.EscapeDataString(query)
            + SearchMarket(CultureInfo.CurrentCulture));
        using HttpResponseMessage response = await _http.GetAsync(
            endpoint, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        string page = await ReadBoundedTextAsync(response, 4_000_000, cancellationToken)
            .ConfigureAwait(false);
        var candidates = new List<SearchCandidate>();
        foreach ((string title, string url, string snippet) in ParseSearchPage(page))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                && parsed.Scheme is "http" or "https"
                && !parsed.Host.EndsWith("bing.com", StringComparison.OrdinalIgnoreCase)
                && title.Length is > 0 and <= 4_096
                && snippet.Length <= 16_384)
            {
                candidates.Add(new SearchCandidate(title, parsed, snippet, ObservedSearchTokens(title, parsed, snippet)));
            }
        }
        int structurallyValidItems = candidates.Count;
        if (structurallyValidItems == 0 && !IsSearchResultsPage(response, page))
        {
            // The engine answered with something other than a results page (a block,
            // a captcha, an error): nothing was searched, and the reply must not
            // pretend the web had no answer.
            return ExternalJson.FailureBeforeEffect(operation, "web_search_engine_unavailable");
        }
        string[] verifiableTerms = VerifiableSearchTerms(queryTokens, candidates);
        var results = new List<(string Title, string Url, string Snippet)>();
        var rejected = new List<(string Title, Uri Url, string Snippet)>();
        foreach (SearchCandidate candidate in candidates)
        {
            if (results.Count >= limit) break;
            if (IsSearchResultRelevant(verifiableTerms, candidate.Observed))
            {
                results.Add((candidate.Title, candidate.Url.AbsoluteUri, candidate.Snippet));
            }
            else if (_searchDiagnosticPath is not null && rejected.Count < 20)
            {
                rejected.Add((candidate.Title, candidate.Url, candidate.Snippet));
            }
        }
        if (structurallyValidItems > 0 && results.Count == 0)
        {
            RecordSearchRejection(query, queryTokens, structurallyValidItems, rejected);
            return ExternalJson.FailureBeforeEffect(
                operation, "web_search_results_irrelevant");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("query", query);
            writer.WriteNumber("count", results.Count);
            writer.WriteStartArray("results");
            foreach ((string title, string url, string snippet) in results)
            {
                writer.WriteStartObject();
                writer.WriteString("title", title);
                writer.WriteString("url", url);
                writer.WriteString("snippet", snippet);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "bing_html_https");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static async Task<string> ReadBoundedTextAsync(
        HttpResponseMessage response,
        int maximumBytes,
        CancellationToken cancellationToken)
    {
        using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken)
            .ConfigureAwait(false);
        using var buffer = new MemoryStream();
        byte[] chunk = ArrayPool<byte>.Shared.Rent(16 * 1024);
        try
        {
            int read;
            while ((read = await stream.ReadAsync(chunk, cancellationToken).ConfigureAwait(false)) > 0)
            {
                if (buffer.Length + read > maximumBytes) break;
                buffer.Write(chunk, 0, read);
            }
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(chunk);
        }
        return Encoding.UTF8.GetString(buffer.GetBuffer(), 0, (int)buffer.Length);
    }

    // The person's culture chooses the engine's language and country («setlang=es»,
    // «cc=AR»), so a Spanish question gets Spanish pages; an invariant culture adds
    // nothing and the engine decides.
    internal static string SearchMarket(CultureInfo culture)
    {
        string language = culture.TwoLetterISOLanguageName.ToLowerInvariant();
        if (language.Length != 2 || culture.Equals(CultureInfo.InvariantCulture)) return string.Empty;
        string market = "&setlang=" + language;
        try
        {
            if (!culture.IsNeutralCulture && culture.Name.Length >= 5)
            {
                string region = new RegionInfo(culture.Name).TwoLetterISORegionName.ToUpperInvariant();
                if (region.Length == 2) market += "&cc=" + region;
            }
        }
        catch (ArgumentException)
        {
        }
        return market;
    }

    private static readonly Regex SearchResultEntry = new(
        "<li class=\"b_algo\"",
        RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    private static readonly Regex SearchResultHeading = new(
        "<h2[^>]*>\\s*<a\\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    private static readonly Regex SearchResultSnippet = new(
        "<p\\b[^>]*class=\"b_lineclamp[^\"]*\"[^>]*>(.*?)</p>|<div class=\"b_caption\"[^>]*>.*?<p\\b[^>]*>(.*?)</p>|</h2>.*?<p\\b[^>]*>(.*?)</p>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    private static readonly Regex HtmlTag = new(
        "<[^>]+>",
        RegexOptions.Singleline | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    // Each organic result is a «b_algo» list item whose heading anchor carries the
    // engine's click redirect; the real target travels base64-encoded in its «u»
    // parameter (prefixed «a1»). Advertising and engine-internal links keep the
    // engine's host and are discarded by the caller.
    internal static IEnumerable<(string Title, string Url, string Snippet)> ParseSearchPage(string page)
    {
        MatchCollection entries = SearchResultEntry.Matches(page);
        for (int index = 0; index < entries.Count; index++)
        {
            int blockStart = entries[index].Index;
            int blockEnd = index + 1 < entries.Count ? entries[index + 1].Index : page.Length;
            string block = page.Substring(blockStart, blockEnd - blockStart);
            Match heading = SearchResultHeading.Match(block);
            if (!heading.Success) continue;
            Match snippet = SearchResultSnippet.Match(block);
            string rawSnippet = snippet.Success
                ? (snippet.Groups[1].Success ? snippet.Groups[1].Value
                    : snippet.Groups[2].Success ? snippet.Groups[2].Value
                    : snippet.Groups[3].Value)
                : string.Empty;
            yield return (
                HtmlText(heading.Groups[2].Value),
                ResolveSearchLink(System.Net.WebUtility.HtmlDecode(heading.Groups[1].Value)),
                HtmlText(rawSnippet));
        }
    }

    private static string HtmlText(string fragment)
    {
        string text = System.Net.WebUtility.HtmlDecode(HtmlTag.Replace(fragment, " "));
        return string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }

    internal static string ResolveSearchLink(string href)
    {
        string absolute = href.StartsWith("//", StringComparison.Ordinal) ? "https:" + href
            : href.StartsWith('/') ? "https://www.bing.com" + href
            : href;
        if (!Uri.TryCreate(absolute, UriKind.Absolute, out Uri? uri)) return absolute;
        if (!uri.Host.EndsWith("bing.com", StringComparison.OrdinalIgnoreCase)) return absolute;
        foreach (string pair in uri.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            int separator = pair.IndexOf('=');
            if (separator <= 0 || pair[..separator] != "u") continue;
            string encoded = pair[(separator + 1)..];
            if (encoded.StartsWith("a1", StringComparison.Ordinal)) encoded = encoded[2..];
            encoded = encoded.Replace('-', '+').Replace('_', '/');
            encoded += new string('=', (4 - encoded.Length % 4) % 4);
            try
            {
                string decoded = Encoding.UTF8.GetString(Convert.FromBase64String(encoded));
                if (Uri.TryCreate(decoded, UriKind.Absolute, out Uri? target)
                    && target.Scheme is "http" or "https")
                {
                    return target.AbsoluteUri;
                }
            }
            catch (FormatException)
            {
            }
        }
        return absolute;
    }

    // A genuine answer carries the engine's result list container even when it is
    // empty; a block, a captcha or an error page does not.
    private static bool IsSearchResultsPage(HttpResponseMessage response, string page) =>
        response.IsSuccessStatusCode
        && page.Contains("id=\"b_results\"", StringComparison.Ordinal);

    private void RecordSearchRejection(
        string query,
        string[] queryTokens,
        int structurallyValidItems,
        List<(string Title, Uri Url, string Snippet)> rejected)
    {
        if (_searchDiagnosticPath is null) return;
        try
        {
            // These unverified search items stay in private diagnostics, never receipts.
            JsonElement diagnostic = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("schema", "baxy.web-search-rejection.v1");
                writer.WriteString("timestampUtc", DateTimeOffset.UtcNow);
                writer.WriteBoolean("verified", false);
                writer.WriteString("query", query);
                writer.WriteStartArray("queryTerms");
                foreach (string term in queryTokens) writer.WriteStringValue(term);
                writer.WriteEndArray();
                writer.WriteNumber("structurallyValidItems", structurallyValidItems);
                writer.WriteNumber("omittedItems", structurallyValidItems - rejected.Count);
                writer.WriteStartArray("rejectedItems");
                foreach ((string title, Uri url, string snippet) in rejected)
                {
                    HashSet<string> observed = ObservedSearchTokens(title, url, snippet);
                    writer.WriteStartObject();
                    writer.WriteString("title", title);
                    writer.WriteString("url", url.AbsoluteUri[..Math.Min(url.AbsoluteUri.Length, 4096)]);
                    writer.WriteString("snippet", snippet[..Math.Min(snippet.Length, 4096)]);
                    writer.WriteBoolean("textTruncated", url.AbsoluteUri.Length > 4096 || snippet.Length > 4096);
                    writer.WriteStartArray("missingTerms");
                    foreach (string term in queryTokens)
                        if (!MatchesSearchTerm(term, observed)) writer.WriteStringValue(term);
                    writer.WriteEndArray();
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteEndObject();
            });
            byte[] line = Encoding.UTF8.GetBytes(diagnostic.GetRawText() + "\n");
            if (line.Length > 1024 * 1024) return;
            using WindowsPrivateDirectoryLease directory = WindowsPrivateStorage.AcquireDirectory(
                Path.GetDirectoryName(_searchDiagnosticPath)!, createMissing: true, protectLeaf: true);
            WindowsPrivateFileLease file;
            if (WindowsPrivateStorage.TryOpenFile(
                    _searchDiagnosticPath, FileAccess.ReadWrite, FileShare.None,
                    deleteAccess: false, out WindowsPrivateFileLease? existing))
                file = existing;
            else
                file = WindowsPrivateStorage.CreateFile(_searchDiagnosticPath);
            using (file)
            {
                if (file.Stream.Length + line.Length > 16 * 1024 * 1024) return;
                file.Stream.Position = file.Stream.Length;
                file.Stream.Write(line);
                file.Stream.Flush(flushToDisk: true);
            }
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or ArgumentException
            or NotSupportedException or System.Security.SecurityException)
        {
            // A missing diagnostic must not change the failed search into success.
        }
    }

    private static string[] SearchTokens(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var normalized = new StringBuilder(decomposed.Length);
        bool separatorPending = false;
        foreach (char character in decomposed)
        {
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(character);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(character))
            {
                if (separatorPending && normalized.Length > 0)
                {
                    normalized.Append(' ');
                }
                normalized.Append(char.ToLowerInvariant(character));
                separatorPending = false;
            }
            else
            {
                separatorPending = true;
            }
        }

        return normalized.ToString()
            .Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Where(static token => token.Length >= 2 && !IsSearchStopWord(token))
            .Distinct(StringComparer.Ordinal)
            .ToArray();
    }

    private readonly record struct SearchCandidate(
        string Title,
        Uri Url,
        string Snippet,
        HashSet<string> Observed);

    private static HashSet<string> ObservedSearchTokens(string title, Uri uri, string snippet) =>
        new(SearchTokens(string.Concat(
            title, " ", uri.Host, " ", SafeUnescapedPath(uri), " ", snippet)), StringComparer.Ordinal);

    // The person's words reach the engine as typed («porqeu», «suele», «mucho»); a
    // term that no result on the page repeats, even inflected, cannot be verified
    // against that page and does not count against any result. The terms that at
    // least one result repeats are the ones a result is judged by.
    private static string[] VerifiableSearchTerms(string[] queryTokens, List<SearchCandidate> candidates) =>
        queryTokens
            .Where(token => candidates.Any(candidate => MatchesSearchTerm(token, candidate.Observed)))
            .ToArray();

    // A result is pertinent when it repeats at least half (rounded up) of the
    // verifiable terms; with no verifiable term at all, every result is rejected,
    // because nothing on the page shares a content word with the request.
    private static bool IsSearchResultRelevant(string[] verifiableTerms, HashSet<string> observed)
    {
        if (verifiableTerms.Length == 0)
        {
            return false;
        }

        int matched = verifiableTerms.Count(term => MatchesSearchTerm(term, observed));
        return matched >= (verifiableTerms.Length + 1) / 2;
    }

    private static bool MatchesSearchTerm(string token, HashSet<string> observed) =>
        observed.Contains(token)
        || WeatherSynonyms.Any(family => family.Contains(token) && family.Any(observed.Contains))
        || SharesInflectedStem(token, observed);

    // «fallar» and «fallas» share the stem «fall»; «suele» and «suelen» share «suel».
    // Only words of five letters or more take part, and the shared prefix must keep
    // all but the last two letters of the query word, so «casa» never matches «caso».
    private static bool SharesInflectedStem(string queryToken, HashSet<string> observed)
    {
        if (queryToken.Length < 5) return false;
        string stem = queryToken[..(queryToken.Length - 2)];
        if (stem.Length < 4) return false;
        foreach (string candidate in observed)
        {
            if (candidate.Length >= 4 && candidate.StartsWith(stem, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    // WEB1445 «qué clima hace hoy»: the engine's local forecast says «tiempo» or
    // «weather» where the person said «clima»; the words name one concept.
    private static readonly string[][] WeatherSynonyms =
    [
        ["clima", "tiempo", "weather", "meteo", "meteorologico", "meteorologica", "pronostico", "forecast"],
        ["lluvia", "lluvias", "llueve", "llover", "llovera", "rain", "raining"],
        ["manana", "tomorrow"],
        ["temperatura", "temperature", "temperaturas", "temperatures"],
    ];

    private static string SafeUnescapedPath(Uri uri)
    {
        try
        {
            return Uri.UnescapeDataString(uri.AbsolutePath);
        }
        catch (UriFormatException)
        {
            return uri.AbsolutePath;
        }
    }

    private static bool IsSearchStopWord(string token) => token is
        "a" or "an" or "and" or "the" or "to" or "for" or "from" or "in" or "of" or "on"
        or "search" or "find"
        or "de" or "del" or "el" or "en" or "la" or "las" or "los" or "para" or "por"
        or "un" or "una" or "y" or "busca" or "buscar"
        // WEB1267: «hoy»/«today» name the moment of the request, not a word the
        // result must repeat («noticias de hoy» found nothing; «today's news»
        // matched the TV show TODAY).
        or "hoy" or "today" or "ahora" or "now" or "todays"
        // H0060: a question asked in the person's words carries interrogatives and
        // auxiliaries («por qué suele fallar», «why does it fail») that name the
        // question, not the answer; the page is judged by its content words.
        or "que" or "porque" or "como" or "cual" or "cuales" or "cuando" or "donde"
        or "quien" or "quienes" or "es" or "son" or "esta" or "estan" or "hay" or "se"
        or "me" or "mi" or "mis" or "tu" or "su" or "sus" or "lo" or "le" or "les"
        or "al" or "con" or "sin" or "sobre" or "si" or "no" or "ya" or "muy" or "mas"
        or "why" or "how" or "what" or "which" or "when" or "where" or "who" or "whom"
        or "is" or "are" or "was" or "were" or "do" or "does" or "did" or "can" or "could"
        or "should" or "would" or "will" or "it" or "its" or "my" or "your" or "this"
        or "that" or "with" or "without" or "about" or "at" or "by" or "or" or "not"
        or "so" or "very" or "more" or "please";

    private static JsonElement NavigationResult(CdpNavigationResult value, string authority) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedUrl", value.RequestedUrl);
            writer.WriteString("finalUrl", value.FinalUrl);
            writer.WriteString("targetId", value.TargetId);
            writer.WriteString("authority", authority);
            writer.WriteEndObject();
        });

    private static Uri RequireWebUri(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? uri)
            || uri.Scheme is not ("http" or "https")
            || string.IsNullOrWhiteSpace(uri.Host)
            || !string.IsNullOrEmpty(uri.UserInfo))
        {
            throw new InvalidDataException("URL is not an exact web resource.");
        }
        return uri;
    }

    private static bool HostMatchesService(string host, string service)
    {
        string[] suffixes = service switch
        {
            "netflix" => ["netflix.com"],
            "prime_video" => ["primevideo.com", "amazon.com"],
            "youtube" => ["youtube.com", "youtu.be"],
            _ => [],
        };
        return suffixes.Any(suffix => string.Equals(host, suffix, StringComparison.OrdinalIgnoreCase)
            || host.EndsWith("." + suffix, StringComparison.OrdinalIgnoreCase));
    }
}

internal sealed record CdpNavigationResult(
    bool Verified,
    bool EffectObserved,
    string RequestedUrl,
    string FinalUrl,
    string TargetId,
    string ErrorCode);

internal sealed record CdpBrowserControlResult(
    bool Verified,
    bool EffectObserved,
    string Action,
    string TargetId,
    string ObservedState,
    string ErrorCode);

internal sealed record CdpPageReadResult(
    bool Verified,
    string TargetId,
    string Url,
    string Title,
    string Text,
    bool Truncated,
    string ErrorCode);

internal sealed record CdpBrowserTab(string TargetId, string Title, string Url);

internal sealed record CdpBrowserTabsResult(
    bool Verified,
    IReadOnlyList<CdpBrowserTab> Tabs,
    int TotalCount,
    bool Truncated,
    string ErrorCode);

internal sealed record CdpMediaPlaybackResult(
    bool Verified,
    bool EffectObserved,
    string Query,
    string FinalUrl,
    string Title,
    string TargetId,
    string ErrorCode);

internal sealed record CdpStreamingPlaybackResult(
    bool Verified,
    bool EffectObserved,
    string RequestedTitle,
    string FinalUrl,
    string PageTitle,
    string TargetId,
    double ObservedProgressSeconds,
    string ErrorCode);

internal sealed class CdpBrowserSessionContext
{
    private CdpBrowserSession? _active;

    internal CdpBrowserSession? Active => Volatile.Read(ref _active);

    internal void Activate(CdpBrowserSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        Volatile.Write(ref _active, session);
    }

    internal void Deactivate(CdpBrowserSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        _ = Interlocked.CompareExchange(ref _active, null, session);
    }
}

internal class CdpBrowserSession : IDisposable
{
    private readonly string _profile;
    private readonly string? _browserExecutable;
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(10) };
    private Process? _ownedProcess;
    private Uri? _endpoint;
    private int _nextCommandId;

    internal CdpBrowserSession(string profile, string? browserExecutable = null)
    {
        _profile = Path.GetFullPath(profile);
        _browserExecutable = browserExecutable is null
            ? null
            : Path.GetFullPath(browserExecutable);
    }

    internal virtual string? ObservedExecutablePath
    {
        get
        {
            try
            {
                if (_browserExecutable is null || _ownedProcess is null || _ownedProcess.HasExited)
                    return null;
                string? observed = _ownedProcess.MainModule?.FileName;
                return observed is not null && string.Equals(
                    Path.GetFullPath(observed), _browserExecutable, StringComparison.OrdinalIgnoreCase)
                    ? observed : null;
            }
            catch (Exception exception) when (exception is InvalidOperationException
                or System.ComponentModel.Win32Exception or NotSupportedException)
            {
                return null;
            }
        }
    }

    internal virtual async ValueTask<CdpNavigationResult> NavigateAsync(
        Uri target,
        CancellationToken cancellationToken)
    {
        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: true, cancellationToken)
            .ConfigureAwait(false);
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
        string beforeUrl = await EvaluateStringAsync(socket, "location.href", cancellationToken)
            .ConfigureAwait(false);
        string beforeDocument = await EvaluateStringAsync(
            socket,
            "String(performance.timeOrigin || performance.timing.navigationStart)",
            cancellationToken).ConfigureAwait(false);
        int navigateId = Interlocked.Increment(ref _nextCommandId);
        await SendAsync(socket, navigateId, "Page.navigate", target.AbsoluteUri, cancellationToken)
            .ConfigureAwait(false);
        JsonElement navigate = await ReceiveCommandAsync(socket, navigateId, cancellationToken)
            .ConfigureAwait(false);
        if (navigate.TryGetProperty("error", out _))
        {
            return new(false, false, target.AbsoluteUri, string.Empty, targetId, "cdp_navigation_rejected");
        }

        for (int attempt = 0; attempt <= 40; attempt++)
        {
            if (attempt > 0)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }

            string snapshot = await EvaluateStringAsync(
                socket,
                "document.readyState + '\\u001f' + location.href + '\\u001f' + " +
                "String(performance.timeOrigin || performance.timing.navigationStart)",
                cancellationToken)
                .ConfigureAwait(false);
            string[] fields = snapshot.Split('\u001f', 3);
            string readyState = fields.Length == 3 ? fields[0] : string.Empty;
            string? final = fields.Length == 3 ? fields[1] : null;
            string document = fields.Length == 3 ? fields[2] : string.Empty;
            if (Uri.TryCreate(final, UriKind.Absolute, out Uri? finalUri)
                && finalUri.Scheme is "http" or "https"
                && readyState is "interactive" or "complete"
                && !string.Equals(finalUri.AbsoluteUri, "about:blank", StringComparison.Ordinal)
                && (!string.Equals(finalUri.AbsoluteUri, beforeUrl, StringComparison.Ordinal)
                    || (
                        string.Equals(
                            target.AbsoluteUri,
                            beforeUrl,
                            StringComparison.Ordinal)
                        && !string.Equals(
                            document,
                            beforeDocument,
                            StringComparison.Ordinal))))
            {
                return new(true, true, target.AbsoluteUri, finalUri.AbsoluteUri, targetId, string.Empty);
            }
        }
        return new(false, true, target.AbsoluteUri, string.Empty, targetId, "cdp_final_url_not_verified");
    }

    internal virtual async ValueTask<CdpBrowserControlResult> ControlAsync(
        string action,
        CancellationToken cancellationToken)
    {
        if (action is not ("back" or "close" or "close_all" or "fullscreen_video" or "new_tab" or "reload"
            or "scroll_down" or "scroll_up"))
            return new(false, false, action, string.Empty, string.Empty, "browser_control_action_invalid");
        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        if (action == "close_all")
        {
            // H0444 «cerrá todas las pestañas»: every open page target in the
            // product's own CDP browser is closed. The product never attaches to
            // the owner's browser sessions, so only the tabs it opened are closed.
            // The post-read verifies that no page target remains; when closing the
            // last tab ends the browser, the loss of its endpoint is that absence.
            IReadOnlyList<string> pageTargets = await CollectPageTargetIdsAsync(
                endpoint, cancellationToken).ConfigureAwait(false);
            int closed = 0;
            foreach (string id in pageTargets)
            {
                try
                {
                    using HttpResponseMessage response = await _http.GetAsync(
                        new Uri(endpoint, "json/close/" + Uri.EscapeDataString(id)), cancellationToken)
                        .ConfigureAwait(false);
                    if (response.IsSuccessStatusCode)
                        closed++;
                }
                catch (Exception exception) when (
                    IsEndpointLossAfterClose(exception, cancellationToken))
                {
                    if (OwnsEndpoint)
                        _endpoint = null;
                    return new(true, true, action, string.Empty,
                        "tabs_closed:" + closed.ToString(CultureInfo.InvariantCulture) + ":endpoint_closed",
                        string.Empty);
                }
            }
            for (int attempt = 0; attempt < 20; attempt++)
            {
                try
                {
                    if ((await CollectPageTargetIdsAsync(endpoint, cancellationToken)
                            .ConfigureAwait(false)).Count == 0)
                        return new(true, true, action, string.Empty,
                            "tabs_closed:" + closed.ToString(CultureInfo.InvariantCulture), string.Empty);
                }
                catch (Exception exception) when (
                    IsEndpointLossAfterClose(exception, cancellationToken))
                {
                    if (OwnsEndpoint)
                        _endpoint = null;
                    return new(true, true, action, string.Empty,
                        "tabs_closed:" + closed.ToString(CultureInfo.InvariantCulture) + ":endpoint_closed",
                        string.Empty);
                }
                await Task.Delay(100, cancellationToken).ConfigureAwait(false);
            }
            return new(false, true, action, string.Empty, string.Empty, "cdp_close_all_not_verified");
        }
        if (action == "new_tab")
        {
            // BROWSER1493 «abrí una pestaña nueva»: a new blank page target in
            // the product's own browser, verified by its presence in /json/list.
            using var request = new HttpRequestMessage(
                HttpMethod.Put, new Uri(endpoint, "json/new?about%3Ablank"));
            using HttpResponseMessage response = await _http.SendAsync(request, cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                return new(false, false, action, string.Empty, string.Empty, "cdp_new_tab_rejected");
            using Stream createdStream = await response.Content.ReadAsStreamAsync(cancellationToken)
                .ConfigureAwait(false);
            using JsonDocument created = await JsonDocument.ParseAsync(
                createdStream, cancellationToken: cancellationToken).ConfigureAwait(false);
            if (!created.RootElement.TryGetProperty("id", out JsonElement createdId)
                || createdId.GetString() is not { Length: > 0 } newTargetId)
                return new(false, true, action, string.Empty, string.Empty, "cdp_new_tab_not_verified");
            for (int attempt = 0; attempt < 20; attempt++)
            {
                if (await TargetExistsAsync(endpoint, newTargetId, cancellationToken).ConfigureAwait(false))
                    return new(true, true, action, newTargetId, "target_created", string.Empty);
                await Task.Delay(100, cancellationToken).ConfigureAwait(false);
            }
            return new(false, true, action, newTargetId, string.Empty, "cdp_new_tab_not_verified");
        }
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: false, cancellationToken)
            .ConfigureAwait(false);
        if (action == "close")
        {
            using HttpResponseMessage response = await _http.GetAsync(
                new Uri(endpoint, "json/close/" + Uri.EscapeDataString(targetId)), cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                return new(false, false, action, targetId, string.Empty, "cdp_close_rejected");
            for (int attempt = 0; attempt < 20; attempt++)
            {
                try
                {
                    if (!await TargetExistsAsync(endpoint, targetId, cancellationToken)
                            .ConfigureAwait(false))
                    {
                        return new(true, true, action, targetId, "target_absent", string.Empty);
                    }
                }
                catch (Exception exception) when (
                    OwnsEndpoint
                    && IsEndpointLossAfterClose(exception, cancellationToken))
                {
                    // Closing the sole page can terminate the browser and its
                    // private CDP endpoint before /json/list is observable.
                    // A successful /json/close followed by loss of an endpoint
                    // owned by this session is the terminal absence postread.
                    _endpoint = null;
                    return new(
                        true,
                        true,
                        action,
                        targetId,
                        "target_absent_endpoint_closed",
                        string.Empty);
                }
                await Task.Delay(100, cancellationToken).ConfigureAwait(false);
            }
            return new(false, true, action, targetId, string.Empty, "cdp_close_not_verified");
        }

        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
        if (action == "back")
        {
            JsonElement history = await CommandAsync(
                socket, "Page.getNavigationHistory", null, cancellationToken).ConfigureAwait(false);
            JsonElement result = history.GetProperty("result");
            int current = result.GetProperty("currentIndex").GetInt32();
            JsonElement entries = result.GetProperty("entries");
            if (current <= 0)
                return new(true, false, action, targetId, "history_start", string.Empty);
            JsonElement target = entries[current - 1];
            int entryId = target.GetProperty("id").GetInt32();
            string expectedUrl = target.GetProperty("url").GetString()!;
            JsonElement navigated = await CommandAsync(socket, "Page.navigateToHistoryEntry", writer =>
                writer.WriteNumber("entryId", entryId), cancellationToken).ConfigureAwait(false);
            if (navigated.TryGetProperty("error", out _))
                return new(false, false, action, targetId, string.Empty, "cdp_history_rejected");
            for (int attempt = 0; attempt <= 30; attempt++)
            {
                if (attempt > 0)
                {
                    await Task.Delay(100, cancellationToken).ConfigureAwait(false);
                }

                JsonElement observedHistory = await CommandAsync(
                    socket,
                    "Page.getNavigationHistory",
                    null,
                    cancellationToken).ConfigureAwait(false);
                JsonElement observedResult = observedHistory.GetProperty("result");
                int observedIndex = observedResult.GetProperty("currentIndex").GetInt32();
                JsonElement observedEntries = observedResult.GetProperty("entries");
                if (observedIndex == current - 1
                    && observedIndex >= 0
                    && observedIndex < observedEntries.GetArrayLength()
                    && observedEntries[observedIndex].GetProperty("id").GetInt32() == entryId)
                {
                    string observedUrl = await EvaluateStringAsync(
                        socket,
                        "location.href",
                        cancellationToken).ConfigureAwait(false);
                    if (string.Equals(observedUrl, expectedUrl, StringComparison.Ordinal))
                    {
                        return new(true, true, action, targetId, observedUrl, string.Empty);
                    }
                }
            }
            return new(false, true, action, targetId, string.Empty, "cdp_history_not_verified");
        }

        if (action == "reload")
        {
            string beforeUrl = await EvaluateStringAsync(socket, "location.href", cancellationToken)
                .ConfigureAwait(false);
            string beforeDocument = await EvaluateStringAsync(
                socket,
                "String(performance.timeOrigin || performance.timing.navigationStart)",
                cancellationToken).ConfigureAwait(false);
            JsonElement reloaded = await CommandAsync(
                socket, "Page.reload", null, cancellationToken).ConfigureAwait(false);
            if (reloaded.TryGetProperty("error", out _))
                return new(false, false, action, targetId, string.Empty, "cdp_reload_rejected");
            string expectedPrefix = "complete|" + beforeUrl + "|";
            for (int attempt = 0; attempt <= 50; attempt++)
            {
                if (attempt > 0)
                {
                    await Task.Delay(100, cancellationToken).ConfigureAwait(false);
                }

                string observed = await EvaluateStringAsync(
                    socket,
                    "document.readyState + '|' + location.href + '|' + " +
                    "String(performance.timeOrigin || performance.timing.navigationStart)",
                    cancellationToken)
                    .ConfigureAwait(false);
                if (observed.StartsWith(expectedPrefix, StringComparison.Ordinal)
                    && !string.Equals(
                        observed[expectedPrefix.Length..],
                        beforeDocument,
                        StringComparison.Ordinal))
                    return new(true, true, action, targetId, observed, string.Empty);
            }
            return new(false, true, action, targetId, string.Empty, "cdp_reload_not_verified");
        }

        if (action == "fullscreen_video")
        {
            string dispatch = await EvaluateStringAsync(
                socket,
                "(()=>{const v=document.querySelector('video');if(!v)return 'video_missing';" +
                "v.requestFullscreen();return 'requested';})()",
                cancellationToken,
                userGesture: true).ConfigureAwait(false);
            if (dispatch != "requested")
                return new(false, false, action, targetId, dispatch, "cdp_video_missing");
            for (int attempt = 0; attempt <= 20; attempt++)
            {
                if (attempt > 0)
                {
                    await Task.Delay(100, cancellationToken).ConfigureAwait(false);
                }

                string observed = await EvaluateStringAsync(
                    socket,
                    "document.fullscreenElement ? document.fullscreenElement.tagName : ''",
                    cancellationToken).ConfigureAwait(false);
                if (observed == "VIDEO")
                    return new(true, true, action, targetId, "fullscreen:VIDEO", string.Empty);
            }
            return new(false, true, action, targetId, string.Empty, "cdp_fullscreen_not_verified");
        }

        double before = await EvaluateNumberAsync(socket, "window.scrollY", cancellationToken)
            .ConfigureAwait(false);
        string expression = action == "scroll_down"
            ? "window.scrollBy(0, Math.max(300, innerHeight * 0.8)); window.scrollY"
            : "window.scrollBy(0, -Math.max(300, innerHeight * 0.8)); window.scrollY";
        double after = await EvaluateNumberAsync(socket, expression, cancellationToken)
            .ConfigureAwait(false);
        bool moved = Math.Abs(after - before) > 0.5;
        string state = moved ? $"scroll_y:{after.ToString(CultureInfo.InvariantCulture)}" : "scroll_boundary";
        return new(true, moved, action, targetId, state, string.Empty);
    }

    internal virtual async ValueTask<CdpPageReadResult> ReadPageAsync(
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        if (maximumCharacters is < 256 or > 32_768)
            return new(false, string.Empty, string.Empty, string.Empty, string.Empty, false,
                "browser_page_limit_invalid");
        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: false, cancellationToken).ConfigureAwait(false);
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
        for (int attempt = 0; attempt < 40; attempt++)
        {
            string snapshot = await EvaluateStringAsync(
                socket,
                "(()=>{const max=" + maximumCharacters.ToString(CultureInfo.InvariantCulture) + ";"
                + "const raw=(document.body?.innerText||document.documentElement?.innerText||'')"
                + ".replace(/\\u0000/g,'').trim();return JSON.stringify({url:location.href,"
                + "title:document.title||'',text:raw.slice(0,max),truncated:raw.length>max,"
                + "readyState:document.readyState});})()",
                cancellationToken).ConfigureAwait(false);
            CdpPageReadResult observed = ParsePageSnapshot(
                targetId,
                maximumCharacters,
                snapshot);
            if (observed.Verified)
            {
                return observed;
            }

            if (attempt < 39)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }
        }

        return new(false, targetId, string.Empty, string.Empty, string.Empty, false,
            "browser_page_snapshot_invalid");
    }

    internal static CdpPageReadResult ParsePageSnapshot(
        string targetId,
        int maximumCharacters,
        string snapshot)
    {
        using JsonDocument document = JsonDocument.Parse(snapshot);
        JsonElement root = document.RootElement;
        string? url = root.TryGetProperty("url", out JsonElement urlElement)
            && urlElement.ValueKind == JsonValueKind.String ? urlElement.GetString() : null;
        string title = root.TryGetProperty("title", out JsonElement titleElement)
            && titleElement.ValueKind == JsonValueKind.String ? titleElement.GetString() ?? string.Empty : string.Empty;
        string text = root.TryGetProperty("text", out JsonElement textElement)
            && textElement.ValueKind == JsonValueKind.String ? textElement.GetString() ?? string.Empty : string.Empty;
        bool truncated = root.TryGetProperty("truncated", out JsonElement truncatedElement)
            && truncatedElement.ValueKind is JsonValueKind.True or JsonValueKind.False
            && truncatedElement.GetBoolean();
        string readyState = root.TryGetProperty("readyState", out JsonElement readyElement)
            && readyElement.ValueKind == JsonValueKind.String ? readyElement.GetString() ?? string.Empty : string.Empty;
        if (!Uri.TryCreate(url, UriKind.Absolute, out Uri? observed)
            || observed.Scheme is not ("http" or "https")
            || readyState is not ("interactive" or "complete")
            || title.Length > 4_096
            || text.Length > maximumCharacters)
        {
            return new(false, targetId, string.Empty, string.Empty, string.Empty, false,
                "browser_page_snapshot_invalid");
        }
        return new(true, targetId, observed.AbsoluteUri, title, text, truncated, string.Empty);
    }

    internal virtual async ValueTask<CdpBrowserTabsResult> ListTabsAsync(
        int limit,
        CancellationToken cancellationToken)
    {
        if (limit is < 1 or > 50)
            return new(false, [], 0, false, "browser_tabs_limit_invalid");
        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        using Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument targets = await JsonDocument.ParseAsync(
            stream, cancellationToken: cancellationToken).ConfigureAwait(false);
        var tabs = new List<CdpBrowserTab>();
        int webTargetCount = 0;
        foreach (JsonElement target in targets.RootElement.EnumerateArray())
        {
            if (!target.TryGetProperty("type", out JsonElement type) || type.GetString() != "page"
                || !target.TryGetProperty("id", out JsonElement id)
                || !target.TryGetProperty("title", out JsonElement title)
                || !target.TryGetProperty("url", out JsonElement url)
                || id.ValueKind != JsonValueKind.String
                || title.ValueKind != JsonValueKind.String
                || url.ValueKind != JsonValueKind.String
                || !Uri.TryCreate(url.GetString(), UriKind.Absolute, out Uri? parsed)
                || parsed.Scheme is not ("http" or "https"))
            {
                continue;
            }
            webTargetCount++;
            if (tabs.Count >= limit) continue;
            string observedTitle = title.GetString() ?? string.Empty;
            if (observedTitle.Length > 4_096) observedTitle = observedTitle[..4_096];
            tabs.Add(new(id.GetString()!, observedTitle, parsed.AbsoluteUri));
        }
        return new(true, tabs, webTargetCount, webTargetCount > tabs.Count, string.Empty);
    }

    internal virtual async ValueTask<CdpMediaPlaybackResult> PlayYouTubeAsync(
        string query,
        Uri watchUri,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(query) || Encoding.UTF8.GetByteCount(query) > 1_024)
            return new(false, false, query, string.Empty, string.Empty, string.Empty,
                "youtube_query_invalid");
        if (watchUri.Scheme != Uri.UriSchemeHttps
            || !watchUri.Host.EndsWith("youtube.com", StringComparison.OrdinalIgnoreCase)
            || !(watchUri.AbsolutePath.Equals("/watch", StringComparison.OrdinalIgnoreCase)
                || watchUri.AbsolutePath.StartsWith("/embed/", StringComparison.OrdinalIgnoreCase)))
            return new(false, false, query, string.Empty, string.Empty, string.Empty,
                "youtube_watch_uri_invalid");
        CdpNavigationResult navigation = await NavigateAsync(watchUri, cancellationToken)
            .ConfigureAwait(false);
        if (!navigation.Verified)
            return new(false, navigation.EffectObserved, query, navigation.FinalUrl,
                string.Empty, navigation.TargetId, navigation.ErrorCode);

        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: false, cancellationToken).ConfigureAwait(false);
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);

        string playbackFailure = "youtube_playback_not_verified_video_missing";
        for (int attempt = 0; attempt <= 120; attempt++)
        {
            if (attempt > 0)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }

            string observed = await EvaluateStringAsync(
                socket,
                "(()=>{const v=document.querySelector('video');if(!v)return 'video_missing';"
                + "if(v.paused){v.play().catch(()=>{});}const body=(document.body?.innerText||'').toLowerCase();"
                + "const gate=body.includes('sign in to confirm')?'bot':"
                + "body.includes('video unavailable')?'unavailable':"
                + "body.includes('before you continue')?'consent':'none';"
                + "return [location.href,document.title,v.readyState,v.paused?'paused':'playing',"
                + "v.networkState,v.currentSrc?'source':'no_source',gate].join('\\u001f');})()",
                cancellationToken,
                userGesture: true).ConfigureAwait(false);
            string[] fields = observed.Split('\u001f');
            if (fields.Length == 7)
            {
                bool watchPage = fields[0].Contains(
                    "youtube.com/watch", StringComparison.OrdinalIgnoreCase)
                    || fields[0].Contains("youtube.com/embed/", StringComparison.OrdinalIgnoreCase);
                string ready = int.TryParse(
                    fields[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out int state)
                    ? Math.Clamp(state, 0, 4).ToString(CultureInfo.InvariantCulture)
                    : "unknown";
                string playback = fields[3] is "paused" or "playing"
                    ? fields[3]
                    : "unknown";
                string network = int.TryParse(
                    fields[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out int networkState)
                    ? Math.Clamp(networkState, 0, 3).ToString(CultureInfo.InvariantCulture)
                    : "unknown";
                string source = fields[5] is "source" or "no_source" ? fields[5] : "unknown";
                string gate = fields[6] is "bot" or "unavailable" or "consent" or "none"
                    ? fields[6]
                    : "unknown";
                playbackFailure = $"youtube_playback_not_verified_"
                    + $"{(watchPage ? "watch" : "other")}_ready{ready}_{playback}_"
                    + $"network{network}_{source}_{gate}";
            }
            if (fields.Length == 7
                && (fields[0].Contains("youtube.com/watch", StringComparison.OrdinalIgnoreCase)
                    || fields[0].Contains("youtube.com/embed/", StringComparison.OrdinalIgnoreCase))
                && int.TryParse(fields[2], NumberStyles.Integer, CultureInfo.InvariantCulture,
                    out int readyState)
                && readyState >= 2
                && fields[3] == "playing")
            {
                return new(true, true, query, fields[0], fields[1], targetId, string.Empty);
            }
        }
        return new(false, true, query, string.Empty, string.Empty, targetId,
            playbackFailure);
    }

    internal virtual async ValueTask<CdpStreamingPlaybackResult> PlayNetflixAsync(
        string title,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(title) || Encoding.UTF8.GetByteCount(title) > 512)
            return new(false, false, title, string.Empty, string.Empty, string.Empty, 0,
                "netflix_title_invalid");
        var searchUri = new Uri("https://www.netflix.com/search?q="
            + Uri.EscapeDataString(title));
        CdpNavigationResult navigation = await NavigateAsync(searchUri, cancellationToken)
            .ConfigureAwait(false);
        if (!navigation.Verified)
            return new(false, navigation.EffectObserved, title, navigation.FinalUrl,
                string.Empty, navigation.TargetId, 0, navigation.ErrorCode);

        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: false, cancellationToken).ConfigureAwait(false);
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
        string titleLiteral = "\"" + JsonEncodedText.Encode(title).ToString() + "\"";
        double? baseline = null;
        string lastUrl = navigation.FinalUrl;
        string lastPageTitle = string.Empty;
        string failure = "netflix_title_or_play_control_not_found";
        for (int attempt = 0; attempt <= 120; attempt++)
        {
            if (attempt > 0)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }

            string observed = await EvaluateStringAsync(
                socket,
                "(()=>{const wanted=" + titleLiteral + ".toLowerCase();"
                + "const body=(document.body?.innerText||'').toLowerCase();"
                + "const auth=location.pathname.includes('/login')||body.includes('sign in')||"
                + "body.includes('iniciar sesión')||body.includes('inicia sesión');let action='none';"
                + "if(!auth&&location.pathname.startsWith('/search')){const links=[...document.querySelectorAll('a[href*=\"/title/\"]')];"
                + "const link=links.find(a=>((a.closest('[data-uia],.title-card,.slider-item')?.innerText||a.innerText||'').toLowerCase()).includes(wanted));"
                + "if(link){link.click();action='result_clicked';}}"
                + "if(!auth&&!location.pathname.includes('/watch/')){const controls=[...document.querySelectorAll('[data-uia=\"play-button\"],button,a')];"
                + "const play=controls.find(e=>{const s=((e.getAttribute('aria-label')||'')+' '+(e.innerText||'')).toLowerCase();"
                + "return s==='play'||s.includes('reproducir')||s.startsWith('play ');});"
                + "if(play){play.click();action='play_clicked';}}"
                + "const v=document.querySelector('video');if(v&&v.paused){v.play().catch(()=>{});}"
                + "const matched=(document.title.toLowerCase()+' '+body).includes(wanted);"
                + "return [location.href,document.title,auth?'auth':'ok',matched?'matched':'unmatched',"
                + "v?v.readyState:-1,v?(v.paused?'paused':'playing'):'missing',v?v.currentTime:0,action].join('\\u001f');})()",
                cancellationToken,
                userGesture: true).ConfigureAwait(false);
            string[] fields = observed.Split('\u001f');
            if (fields.Length != 8) continue;
            lastUrl = fields[0]; lastPageTitle = fields[1];
            if (fields[2] == "auth")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    "netflix_authentication_required");
            bool watch = lastUrl.Contains("netflix.com/watch/", StringComparison.OrdinalIgnoreCase);
            bool ready = int.TryParse(fields[4], NumberStyles.Integer,
                CultureInfo.InvariantCulture, out int readyState) && readyState >= 2;
            bool progressing = double.TryParse(fields[6], NumberStyles.Float,
                CultureInfo.InvariantCulture, out double currentTime);
            if (watch && fields[3] == "matched" && ready
                && fields[5] == "playing" && progressing)
            {
                if (baseline is not null && currentTime >= baseline.Value + 0.5)
                    return new(true, true, title, lastUrl, lastPageTitle, targetId,
                        currentTime - baseline.Value, string.Empty);
                baseline ??= currentTime;
                failure = "netflix_video_progress_not_observed";
            }
        }
        return new(false, true, title, lastUrl, lastPageTitle, targetId, 0, failure);
    }

    public virtual void Dispose()
    {
        _http.Dispose();
        try
        {
            if (_ownedProcess is { HasExited: false })
            {
                _ownedProcess.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
        _ownedProcess?.Dispose();
    }

    private async ValueTask<Uri> EnsureEndpointAsync(CancellationToken cancellationToken)
    {
        if (_endpoint is not null)
        {
            return _endpoint;
        }
        string? configured = Environment.GetEnvironmentVariable("BAXY_CDP_ENDPOINT");
        if (_browserExecutable is null
            && Uri.TryCreate(configured, UriKind.Absolute, out Uri? explicitEndpoint)
            && explicitEndpoint.Scheme == Uri.UriSchemeHttp
            && explicitEndpoint.IsLoopback)
        {
            _endpoint = explicitEndpoint;
            return explicitEndpoint;
        }

        Directory.CreateDirectory(_profile);
        if (new DirectoryInfo(_profile).LinkTarget is not null)
        {
            throw new IOException("Browser profile cannot be a link.");
        }
        string activePort = Path.Combine(_profile, "DevToolsActivePort");
        if (File.Exists(activePort))
        {
            File.Delete(activePort);
        }
        string browser = _browserExecutable ?? ResolveEdge();
        var start = new ProcessStartInfo(browser)
        {
            UseShellExecute = _browserExecutable is null,
        };
        start.ArgumentList.Add("--remote-debugging-port=0");
        start.ArgumentList.Add("--remote-allow-origins=*");
        start.ArgumentList.Add("--no-first-run");
        start.ArgumentList.Add("--no-default-browser-check");
        // The private automation session renders for CDP, not for the person:
        // GPU acceleration only adds a GPU process to the product's tree
        // (WEB1261: 3874 MiB with the local model, over the 3800 MiB budget).
        start.ArgumentList.Add("--disable-gpu");
        start.ArgumentList.Add("--user-data-dir=" + _profile);
        start.ArgumentList.Add("about:blank");
        _ownedProcess = Process.Start(start) ?? throw new IOException("CDP browser could not start.");
        for (int attempt = 0; attempt < 80; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (File.Exists(activePort))
            {
                string[] lines = await File.ReadAllLinesAsync(activePort, cancellationToken)
                    .ConfigureAwait(false);
                if (lines.Length >= 1 && ushort.TryParse(lines[0], out ushort port) && port > 0)
                {
                    Uri candidate = new($"http://127.0.0.1:{port}/");
                    for (int readyAttempt = 0; readyAttempt < 40; readyAttempt++)
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        using var readiness = CancellationTokenSource.CreateLinkedTokenSource(
                            cancellationToken);
                        readiness.CancelAfter(TimeSpan.FromMilliseconds(300));
                        try
                        {
                            using HttpResponseMessage response = await _http.GetAsync(
                                new Uri(candidate, "json/version"), readiness.Token)
                                .ConfigureAwait(false);
                            if (response.IsSuccessStatusCode)
                            {
                                _endpoint = candidate;
                                return candidate;
                            }
                        }
                        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
                        {
                        }
                        catch (HttpRequestException)
                        {
                        }
                        await Task.Delay(100, cancellationToken).ConfigureAwait(false);
                    }
                    throw new TimeoutException("Browser did not publish a responsive CDP endpoint.");
                }
            }
            await Task.Delay(100, cancellationToken).ConfigureAwait(false);
        }
        throw new TimeoutException("Edge did not publish a CDP endpoint.");
    }

    private async ValueTask<(string TargetId, Uri WebSocket)> ResolveTargetAsync(
        Uri endpoint,
        bool createIfMissing,
        CancellationToken cancellationToken)
    {
        using Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument targets = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        foreach (JsonElement target in targets.RootElement.EnumerateArray())
        {
            if (target.TryGetProperty("type", out JsonElement type)
                && type.GetString() == "page"
                && target.TryGetProperty("id", out JsonElement id)
                && target.TryGetProperty("webSocketDebuggerUrl", out JsonElement socket)
                && Uri.TryCreate(socket.GetString(), UriKind.Absolute, out Uri? webSocket))
            {
                return (id.GetString()!, webSocket);
            }
        }
        if (createIfMissing)
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Put, new Uri(endpoint, "json/new?about%3Ablank"));
            using HttpResponseMessage response = await _http.SendAsync(request, cancellationToken)
                .ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            using Stream createdStream = await response.Content.ReadAsStreamAsync(cancellationToken)
                .ConfigureAwait(false);
            using JsonDocument created = await JsonDocument.ParseAsync(
                createdStream, cancellationToken: cancellationToken).ConfigureAwait(false);
            JsonElement root = created.RootElement;
            if (root.TryGetProperty("id", out JsonElement createdId)
                && root.TryGetProperty("webSocketDebuggerUrl", out JsonElement createdSocket)
                && Uri.TryCreate(createdSocket.GetString(), UriKind.Absolute, out Uri? webSocket))
            {
                return (createdId.GetString()!, webSocket);
            }
        }
        throw new IOException("CDP session has no page target.");
    }

    private async ValueTask<IReadOnlyList<string>> CollectPageTargetIdsAsync(
        Uri endpoint,
        CancellationToken cancellationToken)
    {
        using Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument targets = await JsonDocument.ParseAsync(
            stream, cancellationToken: cancellationToken).ConfigureAwait(false);
        var ids = new List<string>();
        foreach (JsonElement target in targets.RootElement.EnumerateArray())
        {
            if (target.TryGetProperty("type", out JsonElement type)
                && type.GetString() == "page"
                && target.TryGetProperty("id", out JsonElement id)
                && id.GetString() is { Length: > 0 } value)
            {
                ids.Add(value);
            }
        }
        return ids;
    }

    private async ValueTask<bool> TargetExistsAsync(
        Uri endpoint,
        string targetId,
        CancellationToken cancellationToken)
    {
        using Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument targets = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        return targets.RootElement.EnumerateArray().Any(target =>
            target.TryGetProperty("id", out JsonElement id)
            && string.Equals(id.GetString(), targetId, StringComparison.Ordinal));
    }

    private bool OwnsEndpoint => _ownedProcess is not null;

    internal static bool IsEndpointLossAfterClose(
        Exception exception,
        CancellationToken cancellationToken) =>
        exception is HttpRequestException or IOException or JsonException
        || exception is OperationCanceledException && !cancellationToken.IsCancellationRequested;

    private async ValueTask<JsonElement> CommandAsync(
        ClientWebSocket socket,
        string method,
        Action<Utf8JsonWriter>? parameters,
        CancellationToken cancellationToken)
    {
        int id = Interlocked.Increment(ref _nextCommandId);
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("id", id);
            writer.WriteString("method", method);
            writer.WriteStartObject("params");
            parameters?.Invoke(writer);
            writer.WriteEndObject();
            writer.WriteEndObject();
        }
        await socket.SendAsync(buffer.WrittenMemory, WebSocketMessageType.Text, true, cancellationToken)
            .ConfigureAwait(false);
        return await ReceiveCommandAsync(socket, id, cancellationToken).ConfigureAwait(false);
    }

    private async ValueTask<string> EvaluateStringAsync(
        ClientWebSocket socket,
        string expression,
        CancellationToken cancellationToken,
        bool userGesture = false)
    {
        JsonElement response = await CommandAsync(socket, "Runtime.evaluate", writer =>
        {
            writer.WriteString("expression", expression);
            writer.WriteBoolean("returnByValue", true);
            if (userGesture) writer.WriteBoolean("userGesture", true);
        }, cancellationToken).ConfigureAwait(false);
        return response.GetProperty("result").GetProperty("result").GetProperty("value").GetString()
            ?? string.Empty;
    }

    private async ValueTask<double> EvaluateNumberAsync(
        ClientWebSocket socket, string expression, CancellationToken cancellationToken)
    {
        JsonElement response = await CommandAsync(socket, "Runtime.evaluate", writer =>
        {
            writer.WriteString("expression", expression);
            writer.WriteBoolean("returnByValue", true);
        }, cancellationToken).ConfigureAwait(false);
        return response.GetProperty("result").GetProperty("result").GetProperty("value").GetDouble();
    }

    private static async ValueTask SendAsync(
        ClientWebSocket socket,
        int id,
        string method,
        string? value,
        CancellationToken cancellationToken)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("id", id);
            writer.WriteString("method", method);
            writer.WriteStartObject("params");
            if (method == "Page.navigate")
            {
                writer.WriteString("url", value);
            }
            else
            {
                writer.WriteString("expression", "location.href");
                writer.WriteBoolean("returnByValue", true);
            }
            writer.WriteEndObject();
            writer.WriteEndObject();
        }
        await socket.SendAsync(buffer.WrittenMemory, WebSocketMessageType.Text, true, cancellationToken)
            .ConfigureAwait(false);
    }

    private static async ValueTask<JsonElement> ReceiveCommandAsync(
        ClientWebSocket socket,
        int expectedId,
        CancellationToken cancellationToken)
    {
        byte[] chunk = new byte[16 * 1024];
        for (int message = 0; message < 256; message++)
        {
            using var collected = new MemoryStream();
            WebSocketReceiveResult received;
            do
            {
                received = await socket.ReceiveAsync(chunk, cancellationToken).ConfigureAwait(false);
                if (received.MessageType == WebSocketMessageType.Close)
                {
                    throw new WebSocketException("CDP closed before the command completed.");
                }
                collected.Write(chunk, 0, received.Count);
                if (collected.Length > 1024 * 1024)
                {
                    throw new IOException("CDP message exceeded its bound.");
                }
            }
            while (!received.EndOfMessage);
            using JsonDocument document = JsonDocument.Parse(collected.ToArray());
            if (document.RootElement.TryGetProperty("id", out JsonElement id)
                && id.TryGetInt32(out int actual)
                && actual == expectedId)
            {
                return document.RootElement.Clone();
            }
        }
        throw new IOException("CDP command response was not observed.");
    }

    private static string ResolveEdge()
    {
        string[] candidates =
        [
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                "Microsoft", "Edge", "Application", "msedge.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "Microsoft", "Edge", "Application", "msedge.exe"),
        ];
        return candidates.FirstOrDefault(File.Exists)
            ?? throw new FileNotFoundException("Microsoft Edge is not installed.");
    }
}
