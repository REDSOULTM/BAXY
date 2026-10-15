using System.Buffers;
using System.Diagnostics;
using System.Globalization;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Providers.Windows.External;

internal sealed class WebBrowserAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly CdpBrowserSession _browser;
    private readonly CdpBrowserSessionContext? _sessionContext;
    // Owner 2026-10-02: pages, videos and streaming open in the person's own
    // browser (their default, their sessions). The product's CDP browser stays
    // as the fallback when no default browser resolves or it cannot launch.
    private readonly UserBrowserSurface? _userBrowser;
    private bool _userBrowserInUse;
    private readonly HttpClient _http;
    private readonly PublicPlaceLocator _locator;
    private readonly WikipediaSearchSource _wikipedia;
    private readonly OpenStreetMapPlaceSource _places;
    private readonly FrankfurterRateSource _rates;
    private readonly EspnScheduleSource _sports;
    private readonly SearchPageReader _pages;
    // Private diagnostics of a playback that failed; null in tests.
    private readonly string? _capturesDirectory;

    // El perfil del navegador colgaba del directorio del turno, de modo que cada
    // turno estrenaba uno. Dos cosas no sobreviven a eso, y las dos hacen falta
    // para el video: la sesion iniciada en el servicio, y el componente Widevine
    // —Chrome lo instala como componente, y en un perfil recien creado todavia
    // no esta—. La sesion del navegador es del equipo y de la persona, como su
    // Steam o su WhatsApp: no es estado del turno. Vive donde vive el resto de
    // lo suyo, y un turno con perfil nuevo la encuentra igual.
    internal static string SharedBrowserProfile(string dataRoot, string leaf)
    {
        try
        {
            string local = Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData);
            if (!string.IsNullOrWhiteSpace(local))
                return Path.Combine(local, "BAXY", "browser-session-v1", leaf);
        }
        catch (Exception exception) when (exception is ArgumentException
            or PlatformNotSupportedException)
        {
            // Sin carpeta de usuario se vuelve al comportamiento anterior.
        }

        return Path.Combine(dataRoot, leaf + "-browser-profile");
    }

    internal WebBrowserAdapter(string dataRoot, CdpBrowserSessionContext? sessionContext)
    {
        _browser = new CdpBrowserSession(SharedBrowserProfile(dataRoot, "edge"));
        _sessionContext = sessionContext;
        _userBrowser = new UserBrowserSurface(new WindowsUserBrowserPlatform());
        _capturesDirectory = Path.Combine(dataRoot, "captures");
        _http = new HttpClient(new SocketsHttpHandler
        {
            AutomaticDecompression = System.Net.DecompressionMethods.All,
        })
        { Timeout = TimeSpan.FromSeconds(20) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY/1.0 structured-search");
        _locator = new PublicPlaceLocator(_http.GetStringAsync);
        _wikipedia = new WikipediaSearchSource(_http);
        _places = new OpenStreetMapPlaceSource(_http);
        _rates = new FrankfurterRateSource(_http);
        _sports = new EspnScheduleSource(_http);
        _pages = new SearchPageReader();
    }

    internal WebBrowserAdapter(
        CdpBrowserSession browser,
        HttpClient http,
        CdpBrowserSessionContext? sessionContext = null,
        UserBrowserSurface? userBrowser = null,
        EspnScheduleSource? sports = null)
    {
        _browser = browser ?? throw new ArgumentNullException(nameof(browser));
        _http = http ?? throw new ArgumentNullException(nameof(http));
        _sessionContext = sessionContext;
        _userBrowser = userBrowser;
        _locator = new PublicPlaceLocator(_http.GetStringAsync);
        _wikipedia = new WikipediaSearchSource(_http);
        _places = new OpenStreetMapPlaceSource(_http);
        _rates = new FrankfurterRateSource(_http);
        _sports = sports ?? new EspnScheduleSource(_http);
        _pages = new SearchPageReader(_http);
    }

    public bool CanHandle(string operation) => operation is
        "browser.control" or "browser.navigate" or "browser.page.read" or "browser.tabs.list"
        or "media.play.youtube" or "media.control" or "media.status"
        or "streaming.navigate" or "streaming.play.named" or "web.search" or "web.fetch";

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
                "media.control" => await ControlYouTubeTabAsync(
                    operation, arguments, effectBoundary, cancellationToken).ConfigureAwait(false),
                "media.status" => await ReadYouTubeTabAsync(operation, cancellationToken)
                    .ConfigureAwait(false),
                "streaming.navigate" => await StreamingAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "streaming.play.named" => await PlayStreamingNamedAsync(
                    operation, arguments, effectBoundary, cancellationToken).ConfigureAwait(false),
                "web.search" => await SearchAsync(
                    operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                "web.fetch" => await FetchAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
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
        _pages.Dispose();
    }

    private async ValueTask<ExternalCapabilityReceipt> ControlAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string action = ExternalJson.RequiredString(arguments, "action");
        // Owner 2026-10-06: the person's tabs are in their own browser; a browser BAXY keeps aside is never the
        // answer to «cierra la pestaña» or «vuelve atrás».
        if (_userBrowser?.Resolve() is { } userBrowser)
            return await _userBrowser.ControlAsync(operation, userBrowser, action, effectBoundary, cancellationToken)
                .ConfigureAwait(false);
        if (UserBrowserHoldsThePage)
            return ExternalJson.FailureBeforeEffect(operation, UserBrowserTabsNotAutomatable);
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
        if (_userBrowser?.Resolve() is { } userBrowser
            && await _userBrowser.NavigateAsync(
                operation, userBrowser, target, effectBoundary, cancellationToken).ConfigureAwait(false)
                is { } opened)
        {
            UseUserBrowser();
            return opened;
        }
        UseProductBrowser();
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
        // The page read is the one BAXY last opened: a page it opened in a browser of its own (a named browser that is
        // not the person's default) is read there, not in the person's browser in front of it (2026-10-15 E016: Chrome
        // showed example.com and the read returned the person's Opera tab).
        CdpBrowserSession? active = _sessionContext?.Active;
        if (active is null && _userBrowser?.Resolve() is { } userBrowser)
            return await _userBrowser.ReadPageAsync(operation, userBrowser, maximumCharacters, cancellationToken)
                .ConfigureAwait(false);
        CdpBrowserSession browser = active ?? _browser;
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

    // web.fetch: one public page read as a stranger would (SearchPageReader: no cookie, no referrer, public addresses
    // only, each redirect checked again), returned as readable text within the asked bound. What it observes is the
    // address the text was finally read from: the text is that page's, nothing is said about any other.
    private async ValueTask<ExternalCapabilityReceipt> FetchAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // A page comes in pages, as file.read gives a file: the paging fields go before the text, which the mind cuts
        // at 6 000 characters (BAXY Renew e2e 2026-10-15: RFC 2324's 418 was past the first 8 000 and unreachable).
        int maximumCharacters = Math.Clamp(
            ExternalJson.OptionalInt(arguments, "maximumCharacters", 4_000), 500, 20_000);
        int offset = Math.Max(0, ExternalJson.OptionalInt(arguments, "offset", 0));
        if (!Uri.TryCreate(ExternalJson.RequiredString(arguments, "url").Trim(), UriKind.Absolute, out Uri? address)
            || !SearchPageReader.IsPublicPageAddress(address))
            return ExternalJson.Failure(operation, "web_fetch_address_not_public");
        SearchPageReader.PageRead read = await _pages.ReadPageAsync(address, cancellationToken).ConfigureAwait(false);
        if (read.Html is null || read.Final is null)
            return ExternalJson.Failure(operation, read.Error ?? "web_fetch_page_unreadable");
        (string title, string whole) = PageText.Prose(read.Html);
        int start = Math.Min(offset, whole.Length);
        string text = whole.Substring(start, Math.Min(maximumCharacters, whole.Length - start));
        bool hasMore = start + text.Length < whole.Length;
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedUrl", address.AbsoluteUri);
            writer.WriteString("finalUrl", read.Final.AbsoluteUri);
            writer.WriteString("title", title);
            writer.WriteNumber("totalCharacters", whole.Length);
            // The body is read up to 1.5 MB: past it the page goes on, unread, and its text here ends there.
            writer.WriteBoolean("bodyTruncated", read.Truncated);
            writer.WriteNumber("offset", start);
            writer.WriteBoolean("hasMore", hasMore);
            if (hasMore)
                writer.WriteNumber("nextOffset", start + text.Length);
            writer.WriteString("authority", "public_http_get_html_text");
            writer.WriteString("text", text);
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> ListTabsAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 50);
        if (_userBrowser?.Resolve() is { } userBrowser)
            return await _userBrowser.ListTabsAsync(operation, userBrowser, limit, cancellationToken)
                .ConfigureAwait(false);
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
        if (_userBrowser?.Resolve() is { } userBrowser
            && await _userBrowser.StreamingNavigateAsync(
                operation, userBrowser, service, target, effectBoundary, cancellationToken)
                .ConfigureAwait(false) is { } opened)
        {
            UseUserBrowser();
            return opened;
        }
        UseProductBrowser();
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
        if (service is not ("netflix" or "disney_plus" or "hbo_max") || title.Length == 0)
            return ExternalJson.Failure(operation, "streaming_named_argument_invalid");
        if (_userBrowser?.Resolve() is { } userBrowser
            && await _userBrowser.PlayStreamingNamedAsync(
                operation, userBrowser, service, title, effectBoundary, cancellationToken)
                .ConfigureAwait(false) is { } started)
        {
            UseUserBrowser();
            return started;
        }
        // HBO Max only plays where the person is signed in: the product's own browser has no session of theirs and no
        // route of its own for it, so nothing is opened there.
        if (service == "hbo_max")
            return ExternalJson.FailureBeforeEffect(operation, HboMaxNeedsDefaultBrowser);
        UseProductBrowser();
        effectBoundary.Cross(cancellationToken);
        CdpStreamingPlaybackResult playback = service == "disney_plus"
            ? await _browser.PlayDisneyAsync(title, cancellationToken).ConfigureAwait(false)
            : await _browser.PlayNetflixAsync(title, cancellationToken).ConfigureAwait(false);
        if (playback.Candidates is { } candidates)
            return UserBrowserSurface.StreamingTitleCandidates(operation, service, title, candidates);
        if (!playback.Verified)
        {
            // Un fallo que no dice donde se quedo obliga a adivinar. Se anota la
            // ultima pagina observada, que es lo que separa «no eligio perfil» de
            // «no encontro la tarjeta» y de «no vio avanzar el video».
            RecordStreamingRejection(title, playback);
            return effectBoundary.Failure(
                operation, playback.ErrorCode, playback.EffectObserved);
        }
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("title", playback.Title);
            writer.WriteString("finalUrl", playback.FinalUrl);
            writer.WriteString("pageTitle", playback.PageTitle);
            writer.WriteString("targetId", playback.TargetId);
            writer.WriteString("playbackStatus", "playing");
            writer.WriteNumber("observedProgressSeconds", playback.ObservedProgressSeconds);
            writer.WriteString("authority", service == "disney_plus"
                ? "disney_cdp_video_progress_postread" : "netflix_cdp_video_progress_postread");
            writer.WriteEndObject();
        }), playback.EffectObserved);
    }

    private void RecordStreamingRejection(string title, CdpStreamingPlaybackResult playback)
    {
        if (_capturesDirectory is null)
            return;
        try
        {
            string path = Path.Combine(_capturesDirectory, "streaming-playback-rejections.jsonl");
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            string line = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("schema", "baxy.streaming-playback-rejection.v1");
                writer.WriteString("utc", DateTimeOffset.UtcNow.ToString("o"));
                writer.WriteString("title", title);
                writer.WriteString("error", playback.ErrorCode);
                writer.WriteString("lastUrl", playback.FinalUrl);
                writer.WriteString("lastPageTitle", playback.PageTitle);
                writer.WriteString("lastObserved", playback.LastObserved);
                writer.WriteEndObject();
            }).GetRawText();
            File.AppendAllText(path, line + Environment.NewLine, Encoding.UTF8);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or ArgumentException)
        {
            // Un diagnostico que no se puede escribir no cambia el resultado.
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> PlayYouTubeAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string query = ExternalJson.RequiredString(arguments, "query");
        YouTubeSearchResult video = await YouTubeSearch.FirstVideoAsync(_http, query, cancellationToken)
            .ConfigureAwait(false);
        if (!video.Found)
            return effectBoundary.Failure(operation, video.ErrorCode);
        if (_userBrowser?.Resolve() is { } userBrowser
            && await _userBrowser.PlayYouTubeAsync(
                operation, userBrowser, query, video, effectBoundary, cancellationToken)
                .ConfigureAwait(false) is { } started)
        {
            UseUserBrowser();
            return started;
        }
        Uri watchUri = video.WatchUri;
        UseProductBrowser();
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

    // Owner's test 2026-09-21 (turn 148, «para la canción» right after a YouTube
    // playback): the playback lives in a tab of this session and SMTC may not see
    // it, so the request fell to the Spotify automation and ended in an ambiguous
    // failure. The tab this session plays is driven and read here; with no such
    // tab the adapter stands aside (no effect, no browser launched) and the chain
    // goes on to the next player.
    // How media.status names the YouTube tab this session plays, and so how media.control's sourceApp names it.
    private const string YouTubeTabSourceAppUserModelId = "BAXY YouTube (Edge)";

    private async ValueTask<ExternalCapabilityReceipt> ControlYouTubeTabAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string action;
        try
        {
            action = ExternalJson.RequiredString(arguments, "action");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "media_control_action_invalid");
        }
        // The tab is the player the model named only by the id media.status gives it, compared whole (BAXY Renew
        // audit 2026-10-15: «youtube», «edge» or «browser» anywhere in the argument).
        if (arguments.TryGetProperty("sourceApp", out JsonElement sourceApp)
            && sourceApp.ValueKind == JsonValueKind.String
            && sourceApp.GetString() is { Length: > 0 } requestedSource
            && !string.Equals(requestedSource, YouTubeTabSourceAppUserModelId, StringComparison.OrdinalIgnoreCase))
        {
            return ExternalJson.FailureBeforeEffect(operation, "media_source_app_not_youtube_tab");
        }
        if (action is not ("play" or "pause" or "stop" or "toggle"))
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_tab_action_unsupported");
        }
        if (!_browser.HasEndpoint)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_tab_not_found");
        }
        effectBoundary.Cross(cancellationToken);
        CdpMediaControlResult? control = await _browser.ControlYouTubeAsync(action, cancellationToken)
            .ConfigureAwait(false);
        if (control is null)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_tab_not_found");
        }
        if (control.ErrorCode == YouTubeVideoNotPlaying)
        {
            // Nothing was sent to the tab. The failure carries what was read, so a later adapter that finds no
            // player of its own does not replace it (WindowsExternalCapabilityProvider.InvokeAsync).
            return new ExternalCapabilityReceipt(
                operation, EffectObserved: false, Verified: false, YouTubeTabResult(action, control), control.ErrorCode);
        }
        if (!control.Verified)
        {
            return effectBoundary.Failure(operation, control.ErrorCode, control.EffectObserved);
        }
        return ExternalJson.Success(operation, YouTubeTabResult(action, control), control.EffectObserved);
    }

    internal const string YouTubeVideoNotPlaying = "youtube_playing_video_not_found";

    private static JsonElement YouTubeTabResult(string action, CdpMediaControlResult control) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "youtube");
            writer.WriteString("sourceAppUserModelId", YouTubeTabSourceAppUserModelId);
            writer.WriteString("action", action);
            writer.WriteString("title", control.Title);
            writer.WriteBoolean("titleObserved", control.Title.Length > 0);
            writer.WriteString("finalUrl", control.Url);
            writer.WriteString("targetId", control.TargetId);
            writer.WriteString("playbackStatus", control.PlaybackStatus);
            writer.WriteString("authority", "youtube_cdp_video_postread");
            writer.WriteEndObject();
        });

    private async ValueTask<ExternalCapabilityReceipt> ReadYouTubeTabAsync(
        string operation,
        CancellationToken cancellationToken)
    {
        if (!_browser.HasEndpoint)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_tab_not_found");
        }
        CdpMediaControlResult? status = await _browser.ControlYouTubeAsync(null, cancellationToken)
            .ConfigureAwait(false);
        if (status is null || !status.Verified)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_tab_not_found");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "youtube");
            writer.WriteString("sourceAppUserModelId", YouTubeTabSourceAppUserModelId);
            writer.WriteString("title", status.Title);
            writer.WriteBoolean("titleObserved", status.Title.Length > 0);
            writer.WriteString("artist", string.Empty);
            writer.WriteString("finalUrl", status.Url);
            writer.WriteString("playbackStatus", status.PlaybackStatus);
            writer.WriteString("authority", "youtube_cdp_video_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // web.search (BAXY Renew, 2026-10-15): the model names the source (source) and fills its typed arguments; the
    // provider asks only that source and returns what it returned, bounded by limit. Nothing here reads what the query
    // says: no source is chosen by its words, no result is judged, no page is read for its sentences (the model calls
    // web.fetch on the result it wants to read). Each source is open and keyless (D32, owner 2026-09-28: search works on
    // its own, with no account or key of anybody's, and only the query leaves; terms of use in
    // artifacts/comprobaciones/C03/BUSQUEDA_SIN_CLAVES_D32_2026-09-28.md):
    //   web          → DuckDuckGo lite: title, url and snippet as the engine gave them;
    //   news         → the search feed of Google News: title, outlet, url and time of each item;
    //   encyclopedia → Wikipedia's open API in «language»: title, url and the article's opening as the API gives it;
    //   currency     → Frankfurter, with the ISO 4217 codes «from» and «to» and «amount»: the rate, its date and the
    //                  amount converted;
    //   sports       → ESPN's public calendar, with «team» and «wants» (next|last): the match as ESPN gives it;
    //   places       → OpenStreetMap Nominatim, with «kind» (written in English) inside «place»: names, addresses and
    //                  distances from the place's centre.
    // With nearby (web, news, encyclopedia, places), this PC's city and country, read from its public address
    // (PublicPlaceLocator, https only), join the query or are the place: that is all of the PC that leaves, and the
    // receipt says the query as it was sent. A source that did not answer is web_search_unavailable (the reply says
    // it could not look it up); one that answered with nothing, web_search_no_results.
    // Bing's HTML page is not a source: the Microsoft Services Agreement §14.f.i keeps Bing material «for your
    // noncommercial, personal use only»; §3.a.vi forbids «impermissible scraping»; bing.com/robots.txt disallows
    // /search. DuckDuckGo's terms and policy say nothing about automated queries, but the service throttles them.
    private const string GeneralSearchEndpoint = "https://lite.duckduckgo.com/lite/";
    private const string GeneralSearchAuthority = "duckduckgo_lite_https";
    private const string NewsSearchAuthority = "google_news_rss_search";
    private const string SearchUnavailable = "web_search_unavailable";
    private const string SearchNoResults = "web_search_no_results";

    private async ValueTask<ExternalCapabilityReceipt> SearchAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string query = ExternalJson.RequiredString(arguments, "query").Trim();
        string source = OptionalText(arguments, "source") ?? "web";
        string language = OptionalText(arguments, "language") ?? "es";
        if (language is not ("es" or "en")) throw new InvalidDataException("The search language is es or en.");
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 5), 1, 10);
        bool nearby = arguments.TryGetProperty("nearby", out JsonElement nearbyValue)
            && nearbyValue.ValueKind == JsonValueKind.True;
        switch (source)
        {
            case "currency":
                return await CurrencyAsync(operation, query, CurrencyArguments(arguments), cancellationToken)
                    .ConfigureAwait(false);
            case "sports":
                return await SportsAsync(operation, query, SportsArguments(arguments), cancellationToken)
                    .ConfigureAwait(false);
            case "places":
                string? place = OptionalText(arguments, "place");
                if (place is null && !nearby) throw new InvalidDataException("A places search names its place.");
                string kind = ExternalJson.RequiredString(arguments, "kind").Trim();
                string? city = await NearAsync(nearby, cancellationToken).ConfigureAwait(false);
                if (nearby && city is null)
                    return ExternalJson.FailureBeforeEffect(operation, "web_search_place_unavailable");
                return await PlacesAsync(operation, query,
                        new OpenStreetMapPlaceSource.PlaceAsk(kind, string.Join(", ", new[] { place, city }.OfType<string>())),
                        limit, language, cancellationToken)
                    .ConfigureAwait(false);
            case "web" or "news" or "encyclopedia":
                string? near = await NearAsync(nearby, cancellationToken).ConfigureAwait(false);
                if (nearby && near is null)
                    return ExternalJson.FailureBeforeEffect(operation, "web_search_place_unavailable");
                string sent = near is null ? query : query + " " + near;
                return source switch
                {
                    "web" => await WebAsync(operation, sent, limit, cancellationToken).ConfigureAwait(false),
                    "news" => await NewsAsync(operation, sent, language, limit, cancellationToken).ConfigureAwait(false),
                    _ => await EncyclopediaAsync(operation, sent, language, limit, cancellationToken)
                        .ConfigureAwait(false),
                };
            default:
                throw new InvalidDataException("Unknown search source.");
        }
    }

    // A string argument the model may leave out (absent, null or blank: null), trimmed.
    private static string? OptionalText(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
        && value.GetString() is { } text && !string.IsNullOrWhiteSpace(text)
            ? text.Trim()
            : null;

    // Uso real tanda 4c: with nearby, this PC's city, read from its public address, and its country (M81: «Curico»
    // alone is also in Indiana). Only their names leave; no coordinates, nothing of the person. Null without nearby, or
    // when the PC's place could not be read.
    private async Task<string?> NearAsync(bool nearby, CancellationToken cancellationToken)
    {
        if (!nearby) return null;
        if (await _locator.LocateAsync(cancellationToken).ConfigureAwait(false) is not { } place) return null;
        string country = place.Country.Trim();
        return country.Length > 0 && !place.Name.Contains(country, StringComparison.OrdinalIgnoreCase)
            ? place.Name + ", " + country
            : place.Name;
    }

    private static FrankfurterRateSource.CurrencyAsk CurrencyArguments(JsonElement arguments)
    {
        string from = CurrencyCode(arguments, "from");
        string to = CurrencyCode(arguments, "to");
        if (from == to) throw new InvalidDataException("A conversion names two different currencies.");
        decimal amount = 1m;
        if (arguments.TryGetProperty("amount", out JsonElement value) && value.ValueKind != JsonValueKind.Null)
        {
            if (value.ValueKind != JsonValueKind.Number || !value.TryGetDecimal(out amount) || amount <= 0)
                throw new InvalidDataException("The amount is a positive number.");
        }
        return new FrankfurterRateSource.CurrencyAsk(amount, from, to);
    }

    private static string CurrencyCode(JsonElement arguments, string name)
    {
        string code = ExternalJson.RequiredString(arguments, name).Trim().ToUpperInvariant();
        return code.Length == 3 && code.All(char.IsAsciiLetterUpper)
            ? code
            : throw new InvalidDataException("A currency is its ISO 4217 code.");
    }

    private static EspnScheduleSource.MatchAsk SportsArguments(JsonElement arguments) =>
        new(ExternalJson.RequiredString(arguments, "team").Trim(), (OptionalText(arguments, "wants") ?? "next") switch
        {
            "next" => EspnScheduleSource.Wanted.Next,
            "last" => EspnScheduleSource.Wanted.Last,
            _ => throw new InvalidDataException("wants is next or last."),
        });

    private async Task<ExternalCapabilityReceipt> WebAsync(
        string operation,
        string query,
        int limit,
        CancellationToken cancellationToken)
    {
        (List<(string Title, string Url, string Snippet)> Results, bool IsResultsPage) reading;
        try
        {
            reading = await ReadGeneralSearchAsync(query, cancellationToken).ConfigureAwait(false);
        }
        catch (HttpRequestException)
        {
            return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        }
        // A block, a captcha or an error page: nothing was searched, and the reply must not pretend the web had no
        // answer.
        if (reading.Results.Count == 0 && !reading.IsResultsPage)
            return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        return SearchReceipt(operation, "web", query, GeneralSearchAuthority, reading.Results.Take(limit).ToList(),
            static (writer, result) =>
            {
                writer.WriteString("title", result.Title);
                writer.WriteString("url", result.Url);
                writer.WriteString("snippet", result.Snippet);
            });
    }

    private async Task<ExternalCapabilityReceipt> NewsAsync(
        string operation,
        string query,
        string language,
        int limit,
        CancellationToken cancellationToken)
    {
        List<GoogleNewsFeed.Headline>? items = await ReadNewsAsync(query, language, cancellationToken)
            .ConfigureAwait(false);
        if (items is null) return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        return SearchReceipt(operation, "news", query, NewsSearchAuthority, items.Take(limit).ToList(),
            static (writer, item) =>
            {
                writer.WriteString("title", item.Title);
                writer.WriteString("source", item.Source);
                writer.WriteString("url", item.Url);
                writer.WriteString("published", item.PublishedAt);
            });
    }

    private async Task<ExternalCapabilityReceipt> EncyclopediaAsync(
        string operation,
        string query,
        string language,
        int limit,
        CancellationToken cancellationToken)
    {
        List<(string Title, string Url, string Extract)>? articles = await _wikipedia
            .SearchAsync(language, query, limit, cancellationToken).ConfigureAwait(false);
        if (articles is null) return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        return SearchReceipt(operation, "encyclopedia", query, WikipediaSearchSource.Authority(language),
            articles.Take(limit).ToList(),
            static (writer, article) =>
            {
                writer.WriteString("title", article.Title);
                writer.WriteString("url", article.Url);
                writer.WriteString("extract", article.Extract);
            });
    }

    private async Task<ExternalCapabilityReceipt> CurrencyAsync(
        string operation,
        string query,
        FrankfurterRateSource.CurrencyAsk ask,
        CancellationToken cancellationToken)
    {
        List<FrankfurterRateSource.Rate>? rates = await _rates.ReadAsync(ask, cancellationToken).ConfigureAwait(false);
        if (rates is null) return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        Uri asked = FrankfurterRateSource.RateUri(ask);
        return SearchReceipt(operation, "currency", query, FrankfurterRateSource.Authority, rates,
            (writer, rate) =>
            {
                writer.WriteString("from", rate.From);
                writer.WriteString("to", rate.To);
                writer.WriteNumber("amount", rate.Amount);
                writer.WriteNumber("rate", rate.Value);
                writer.WriteString("date", rate.Date);
                writer.WriteNumber("converted", rate.Converted);
                writer.WriteString("url", asked.AbsoluteUri);
            },
            sent: writer =>
            {
                writer.WriteString("from", ask.From);
                writer.WriteString("to", ask.To);
            });
    }

    private async Task<ExternalCapabilityReceipt> SportsAsync(
        string operation,
        string query,
        EspnScheduleSource.MatchAsk ask,
        CancellationToken cancellationToken)
    {
        List<EspnScheduleSource.Match>? matches = await _sports.ReadAsync(ask, cancellationToken).ConfigureAwait(false);
        if (matches is null) return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        return SearchReceipt(operation, "sports", query, EspnScheduleSource.Authority, matches,
            static (writer, match) =>
            {
                writer.WriteString("team", match.Team);
                writer.WriteString("opponent", match.Opponent);
                writer.WriteString("homeAway", match.Home ? "home" : "away");
                writer.WriteString("start", match.Start.ToString("yyyy-MM-dd'T'HH:mmzzz", CultureInfo.InvariantCulture));
                writer.WriteBoolean("startTimeAnnounced", match.StartTimeAnnounced);
                writer.WriteString("state", match.State);
                writer.WriteBoolean("completed", match.Completed);
                writer.WriteString("statusDetail", match.StatusDetail);
                writer.WriteString("teamScore", match.TeamScore);
                writer.WriteString("opponentScore", match.OpponentScore);
                writer.WriteString("competition", match.Competition);
                writer.WriteString("venue", match.Venue);
                writer.WriteString("url", match.Url);
            },
            sent: writer =>
            {
                writer.WriteString("team", ask.Team);
                writer.WriteString("wants", ask.Wants == EspnScheduleSource.Wanted.Next ? "next" : "last");
            });
    }

    private async Task<ExternalCapabilityReceipt> PlacesAsync(
        string operation,
        string query,
        OpenStreetMapPlaceSource.PlaceAsk ask,
        int limit,
        string language,
        CancellationToken cancellationToken)
    {
        OpenStreetMapPlaceSource.PlaceReading? reading = await _places
            .SearchNearAsync(ask, limit, language, cancellationToken).ConfigureAwait(false);
        if (reading is not { } read) return ExternalJson.FailureBeforeEffect(operation, SearchUnavailable);
        return SearchReceipt(operation, "places", query, OpenStreetMapPlaceSource.Authority, read.Places,
            static (writer, place) =>
            {
                writer.WriteString("name", place.Name);
                writer.WriteString("address", place.Address);
                writer.WriteString("url", place.Url);
                if (place.DistanceMeters is int meters)
                    writer.WriteNumber("distanceMeters", meters);
            },
            sent: writer =>
            {
                writer.WriteString("kind", ask.Kind);
                writer.WriteString("place", ask.Place);
                if (read.Resolved is { } resolved)
                    writer.WriteString("placeFound", resolved);
            });
    }

    // The one receipt shape of web.search: the source asked, the query (as sent to a text source: web, news,
    // encyclopedia), what a typed source was sent instead («sent»: currency, sports, places), the results as the source
    // gave them and their count, and «authority», the source that answered (duckduckgo_lite_https,
    // google_news_rss_search, wikipedia_es_api, wikipedia_en_api, frankfurter_reference_rates, espn_public_schedule,
    // openstreetmap_nominatim). No result is web_search_no_results: the source answered with nothing.
    private static ExternalCapabilityReceipt SearchReceipt<T>(
        string operation,
        string source,
        string query,
        string authority,
        List<T> results,
        Action<Utf8JsonWriter, T> writeResult,
        Action<Utf8JsonWriter>? sent = null)
    {
        if (results.Count == 0) return ExternalJson.FailureBeforeEffect(operation, SearchNoResults);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("source", source);
            writer.WriteString("query", query);
            if (sent is not null)
            {
                writer.WriteStartObject("sent");
                sent(writer);
                writer.WriteEndObject();
            }
            writer.WriteStartArray("results");
            foreach (T item in results)
            {
                writer.WriteStartObject();
                writeResult(writer, item);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteNumber("resultCount", results.Count);
            writer.WriteString("authority", authority);
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // The search feed of Google News, in the edition of «language»: each item with its outlet and time. Null when the
    // feed did not answer with its RSS.
    private async Task<List<GoogleNewsFeed.Headline>?> ReadNewsAsync(
        string query,
        string language,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get,
            GoogleNewsFeed.SearchUri(query, language));
        request.Headers.TryAddWithoutValidation("User-Agent", WikipediaSearchSource.UserAgent);
        try
        {
            using HttpResponseMessage response = await _http
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode) return null;
            string feed = await ReadBoundedTextAsync(response, 2_000_000, cancellationToken)
                .ConfigureAwait(false);
            return GoogleNewsFeed.Parse(feed, 20)
                .Where(static headline => Uri.TryCreate(headline.Url, UriKind.Absolute, out Uri? link)
                    && link.Scheme == Uri.UriSchemeHttps)
                .Select(static headline => headline with { Url = headline.Url.Split('?')[0] })
                .ToList();
        }
        catch (HttpRequestException)
        {
            return null;
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
        catch (XmlException)
        {
            return null;
        }
    }

    // The lite endpoint answers only a form post (a GET returns its search form with no results). Each result is kept
    // as the engine gave it when it is structurally one: an http or https address that is not the engine's own, a
    // title and bounded lengths.
    private async Task<(List<(string Title, string Url, string Snippet)> Results, bool IsResultsPage)>
        ReadGeneralSearchAsync(string query, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, GeneralSearchEndpoint)
        {
            Content = new FormUrlEncodedContent(new[]
            {
                new KeyValuePair<string, string>("q", query),
            }),
        };
        using HttpResponseMessage response = await _http
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        string page = await ReadBoundedTextAsync(response, 4_000_000, cancellationToken)
            .ConfigureAwait(false);
        var results = new List<(string Title, string Url, string Snippet)>();
        foreach ((string title, string url, string snippet) in ParseDuckDuckGoLitePage(page))
        {
            if (Uri.TryCreate(url, UriKind.Absolute, out Uri? parsed)
                && parsed.Scheme is "http" or "https"
                && !parsed.Host.EndsWith("duckduckgo.com", StringComparison.OrdinalIgnoreCase)
                && title.Length is > 0 and <= 4_096
                && snippet.Length <= 16_384)
            {
                results.Add((title, parsed.AbsoluteUri, snippet));
            }
        }
        return (results, IsDuckDuckGoResultsPage(response, page));
    }

    internal static async Task<string> ReadBoundedTextAsync(
        HttpResponseMessage response,
        int maximumBytes,
        CancellationToken cancellationToken)
    {
        (byte[] body, _) = await ReadBoundedBytesAsync(response, maximumBytes, cancellationToken).ConfigureAwait(false);
        return Encoding.UTF8.GetString(body);
    }

    // The body up to maximumBytes, and whether more was left unread.
    internal static async Task<(byte[] Body, bool Truncated)> ReadBoundedBytesAsync(
        HttpResponseMessage response,
        int maximumBytes,
        CancellationToken cancellationToken)
    {
        using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken)
            .ConfigureAwait(false);
        using var buffer = new MemoryStream();
        byte[] chunk = ArrayPool<byte>.Shared.Rent(16 * 1024);
        bool truncated = false;
        try
        {
            int read;
            while ((read = await stream.ReadAsync(chunk, cancellationToken).ConfigureAwait(false)) > 0)
            {
                if (buffer.Length + read > maximumBytes)
                {
                    truncated = true;
                    break;
                }
                buffer.Write(chunk, 0, read);
            }
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(chunk);
        }
        return (buffer.ToArray(), truncated);
    }

    private static readonly Regex HtmlTag = new(
        "<[^>]+>",
        RegexOptions.Singleline | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    private static string HtmlText(string fragment)
    {
        string text = System.Net.WebUtility.HtmlDecode(HtmlTag.Replace(fragment, " "));
        return string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }

    private static readonly Regex DuckDuckGoResultLink = new(
        "<a\\b[^>]*href=[\"']([^\"']+)[\"'][^>]*class=[\"']result-link[\"'][^>]*>(.*?)</a>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    private static readonly Regex DuckDuckGoResultSnippet = new(
        "<td\\b[^>]*class=[\"']result-snippet[\"'][^>]*>(.*?)</td>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    // The lite endpoint lists each result as an anchor of class «result-link» whose
    // href is already the real target, followed by its snippet cell; a result without
    // a snippet keeps an empty one instead of borrowing the next result's.
    internal static IEnumerable<(string Title, string Url, string Snippet)> ParseDuckDuckGoLitePage(string page)
    {
        MatchCollection links = DuckDuckGoResultLink.Matches(page);
        for (int index = 0; index < links.Count; index++)
        {
            int blockStart = links[index].Index + links[index].Length;
            int blockEnd = index + 1 < links.Count ? links[index + 1].Index : page.Length;
            Match snippet = DuckDuckGoResultSnippet.Match(page, blockStart, blockEnd - blockStart);
            yield return (
                HtmlText(links[index].Groups[2].Value),
                System.Net.WebUtility.HtmlDecode(links[index].Groups[1].Value),
                snippet.Success ? HtmlText(snippet.Groups[1].Value) : string.Empty);
        }
    }

    // The lite endpoint marks its results table in the page itself; a block or an
    // error page carries neither that mark nor a single result link.
    private static bool IsDuckDuckGoResultsPage(HttpResponseMessage response, string page) =>
        response.IsSuccessStatusCode
        && (page.Contains("Web results are present", StringComparison.Ordinal)
            || DuckDuckGoResultLink.IsMatch(page));

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

    internal const string UserBrowserTabsNotAutomatable = "user_browser_tabs_not_automatable";

    // The last page was opened in the person's browser and no CDP session took
    // over since: its tabs are not BAXY's to read or drive (no debug port on the
    // person's profile), and acting on the product browser instead would act on
    // a page the person is not looking at.
    private bool UserBrowserHoldsThePage =>
        _sessionContext?.UserBrowserHoldsThePage ?? _userBrowserInUse;

    private void UseUserBrowser()
    {
        _userBrowserInUse = true;
        _sessionContext?.UseUserBrowser();
    }

    private void UseProductBrowser()
    {
        _userBrowserInUse = false;
        _sessionContext?.Activate(_browser);
    }

    internal const string HboMaxNeedsDefaultBrowser = "hbo_max_needs_default_browser";

    internal static bool HostMatchesService(string host, string service)
    {
        string[] suffixes = service switch
        {
            "netflix" => ["netflix.com"],
            "disney_plus" => ["disneyplus.com"],
            // HBO Max (Chile, 2026-10-06) plays on play.hbomax.com and signs in on auth.hbomax.com; max.com was its
            // name in 2024-2025 and still redirects.
            "hbo_max" => ["hbomax.com", "max.com"],
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

/// <summary>
/// A YouTube tab of this session read or driven through its &lt;video&gt; element
/// (owner's test 2026-09-21, turn 148: «para la canción» right after a YouTube
/// playback must stop what was just played, not fall to another player).
/// </summary>
internal sealed record CdpMediaControlResult(
    bool Verified,
    bool EffectObserved,
    string Action,
    string Title,
    string Url,
    string TargetId,
    string PlaybackStatus,
    string ErrorCode);

internal sealed record CdpStreamingPlaybackResult(
    bool Verified,
    bool EffectObserved,
    // En una reproducción verificada es el nombre de la ficha que el buscador del
    // servicio eligió: lo que de verdad se puso, que no tiene por qué escribirse
    // como se pidió. En los caminos que no llegan a elegir nada es el pedido.
    string Title,
    string FinalUrl,
    string PageTitle,
    string TargetId,
    double ObservedProgressSeconds,
    string ErrorCode,
    // La última lectura de la sonda, tal cual, para que un rechazo diga en qué
    // condición se quedó en vez de obligar a una corrida por hipótesis.
    string LastObserved = "",
    // Sin ficha que se llame como el pedido: los nombres que la búsqueda enseñó.
    IReadOnlyList<string>? Candidates = null);

internal sealed class CdpBrowserSessionContext
{
    private CdpBrowserSession? _active;

    internal CdpBrowserSession? Active => Volatile.Read(ref _active);

    private volatile bool _userBrowserHoldsThePage;

    /// <summary>
    /// The last page went to the person's own browser (M122): no CDP session is
    /// the active one, and the tab steps that need CDP say so instead of acting
    /// on a product browser the person is not looking at.
    /// </summary>
    internal bool UserBrowserHoldsThePage => _userBrowserHoldsThePage && Active is null;

    internal void Activate(CdpBrowserSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        _userBrowserHoldsThePage = false;
        Volatile.Write(ref _active, session);
    }

    internal void UseUserBrowser()
    {
        Volatile.Write(ref _active, null);
        _userBrowserHoldsThePage = true;
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
    // Pasada r15b v3-57 (revisión): null while this session started the browser it drives; after reattaching to the
    // browser a previous session left open for the person, the page targets this session created there. Only those
    // are acted on: the person's own tabs in that window are never navigated, read or closed.
    private HashSet<string>? _sessionTargets;

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
        JsonElement navigate = await CommandAsync(
            socket, "Page.navigate", writer => writer.WriteString("url", target.AbsoluteUri), cancellationToken)
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
            // the owner's browser sessions, so only the tabs it opened are closed;
            // in a browser it reattached to, only the tabs this session opened.
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
            _sessionTargets?.Add(newTargetId);
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
                || _sessionTargets is not null && !_sessionTargets.Contains(id.GetString()!)
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

    internal virtual bool HasEndpoint => _endpoint is not null;

    /// <summary>
    /// Drives (pause/stop/play/toggle) or, with a null action, reads the first
    /// YouTube watch tab of this session that carries a &lt;video&gt;. Null when the
    /// session never started or no such tab exists: the adapter then stands aside
    /// and never launches a browser to look for one.
    /// </summary>
    internal virtual async ValueTask<CdpMediaControlResult?> ControlYouTubeAsync(
        string? action,
        CancellationToken cancellationToken)
    {
        if (_endpoint is not { } endpoint)
            return null;
        using Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument targets = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        var candidates = new List<(string TargetId, Uri WebSocket)>();
        foreach (JsonElement target in targets.RootElement.EnumerateArray())
        {
            if (target.TryGetProperty("type", out JsonElement type) && type.GetString() == "page"
                && target.TryGetProperty("url", out JsonElement url)
                && url.GetString() is { } pageUrl
                && (pageUrl.Contains("youtube.com/watch", StringComparison.OrdinalIgnoreCase)
                    || pageUrl.Contains("youtube.com/embed/", StringComparison.OrdinalIgnoreCase))
                && target.TryGetProperty("id", out JsonElement id)
                && id.GetString() is { Length: > 0 } candidateId
                && (_sessionTargets is null || _sessionTargets.Contains(candidateId))
                && target.TryGetProperty("webSocketDebuggerUrl", out JsonElement socketUrl)
                && Uri.TryCreate(socketUrl.GetString(), UriKind.Absolute, out Uri? webSocket))
            {
                candidates.Add((candidateId, webSocket));
            }
        }
        const string probe = "(()=>{const v=document.querySelector('video');if(!v)return 'video_missing';"
            + "return [location.href,document.title,v.paused?'paused':'playing',v.ended?'ended':'live'].join('\\u001f');})()";
        foreach ((string targetId, Uri webSocket) in candidates)
        {
            using var socket = new ClientWebSocket();
            await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
            string[] before = (await EvaluateStringAsync(socket, probe, cancellationToken).ConfigureAwait(false))
                .Split('\u001f');
            if (before.Length != 4)
                continue;
            string status = before[3] == "ended" ? "stopped" : before[2];
            if (action is null)
                return new(true, false, "status", before[1], before[0], targetId, status, string.Empty);
            string wanted = action switch
            {
                "pause" or "stop" => "paused",
                "play" => "playing",
                "toggle" => before[2] == "playing" ? "paused" : "playing",
                _ => string.Empty,
            };
            if (wanted.Length == 0)
                return new(false, false, action, before[1], before[0], targetId, status,
                    "youtube_tab_action_unsupported");
            // Tanda 5 «pausar el audiolibro»: the tab's video had ended; the pause was sent, nothing changed, and the
            // reply said the change «could not be observed». Pausing or stopping a video that is not playing
            // changes nothing: the state is the fact, read before anything is sent.
            if (wanted == "paused" && before[2] == "paused")
                return new(false, false, action, before[1], before[0], targetId, status,
                    WebBrowserAdapter.YouTubeVideoNotPlaying);
            string command = wanted == "paused"
                ? "(()=>{const v=document.querySelector('video');if(v)v.pause();return 'ok';})()"
                : "(()=>{const v=document.querySelector('video');if(v)v.play().catch(()=>{});return 'ok';})()";
            await EvaluateStringAsync(socket, command, cancellationToken, userGesture: true).ConfigureAwait(false);
            string[] after = before;
            for (int attempt = 0; attempt < 12; attempt++)
            {
                if (attempt > 0)
                    await Task.Delay(250, cancellationToken).ConfigureAwait(false);
                after = (await EvaluateStringAsync(socket, probe, cancellationToken).ConfigureAwait(false))
                    .Split('\u001f');
                if (after.Length == 4 && after[2] == wanted)
                    break;
            }
            bool verified = after.Length == 4 && after[2] == wanted;
            string observed = after.Length == 4 ? (action == "stop" && verified ? "stopped" : after[2]) : "unknown";
            return new(verified, verified && before[2] != after[2], action, before[1], before[0], targetId,
                observed, verified ? string.Empty : "youtube_tab_playback_state_not_verified");
        }
        return null;
    }

    // M89: 60 polls of 250 ms = 15 s of a watch page that never got its video source.
    internal const int YouTubeStallReloadAttempt = 60;

    /// <summary>A watch page whose video has no data yet (readyState 0, with or without a source: ctx-dueno
    /// «ready0 network2 no_source», v3r w10-t4 «ready0 playing network2 source») and no gate (sign-in,
    /// consent, unavailable) in front: a stalled load, which one reload clears.</summary>
    internal static bool YouTubeWatchPageStalled(bool watchPage, string ready, string gate) =>
        watchPage && ready == "0" && gate == "none";

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
        bool reloaded = false;
        // ctx-dueno-01..03 (2026-09-22, notebook): the first watch page of a fresh
        // profile stayed «ready0 network2 no_source» for the whole 30 s and the
        // same query verified in 6 s a minute later; the probe now waits 45 s.
        // M89 (DEV-D v3r D-w10-t4, the run's first watch page): it stayed so for all
        // 45 s again, and the next watch page of the same profile played in 6 s. A
        // page stalled that way for 15 s is reloaded once, within the same 45 s.
        for (int attempt = 0; attempt <= 180; attempt++)
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
                if (!reloaded && attempt >= YouTubeStallReloadAttempt
                    && YouTubeWatchPageStalled(watchPage, ready, gate))
                {
                    reloaded = true;
                    _ = await CommandAsync(socket, "Page.reload", null, cancellationToken)
                        .ConfigureAwait(false);
                }
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

    // Lo común a las búsquedas de Netflix y Disney+: fold pliega mayúsculas, tildes y
    // espacios para comparar un nombre con el pedido; still(cards) cuenta las vueltas
    // en que el conjunto de fichas no cambia y dice si ya lleva tres segundos quieto.
    private const string StreamingCardScript =
        "const fold=s=>(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/\\s+/g,' ').trim().toLowerCase();"
        + "const still=cards=>{const hrefs=cards.map(a=>a.getAttribute('href')||'').join(',');"
        + "if(hrefs!==window.__baxyLastHrefs){window.__baxyLastHrefs=hrefs;window.__baxyNoHit=0;}"
        + "window.__baxyNoHit=(window.__baxyNoHit||0)+1;return window.__baxyNoHit>12;};";

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
        string searchLiteral = "\"" + JsonEncodedText.Encode(searchUri.AbsoluteUri).ToString() + "\"";
        double? baseline = null;
        string lastUrl = navigation.FinalUrl;
        string lastPageTitle = string.Empty;
        string chosenId = string.Empty;
        string lastObserved = string.Empty;
        string chosenName = string.Empty;
        string failure = "netflix_title_or_play_control_not_found";
        // Con la sesión iniciada el camino es más largo de lo que era: elegir perfil,
        // volver a la búsqueda, abrir el título y esperar al reproductor son tres
        // navegaciones. A 250 ms por vuelta, 120 daban treinta segundos y se agotaban
        // antes de llegar; 240 dan un minuto y caben en el turno, que tiene dos.
        for (int attempt = 0; attempt <= 240; attempt++)
        {
            if (attempt > 0)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }

            string observed = await EvaluateStringAsync(
                socket,
                "(()=>{" + StreamingCardScript + "const wanted=fold(" + titleLiteral + ");"
                + "let chosenId='',chosenName='';"
                + "const body=(document.body?.innerText||'').toLowerCase();"
                + "const auth=location.pathname.includes('/login')||body.includes('sign in')||"
                + "body.includes('iniciar sesión')||body.includes('inicia sesión');let action='none';"
                // Con la sesión iniciada, Netflix enseña primero «¿Quién está viendo?»
                // (medido: data-uia profile-gate-screen con cinco tiles). El perfil lo
                // elige la persona: aquí se para y se dice.
                + "if(!auth&&document.querySelector('[data-uia=\"profile-gate-screen\"]')){"
                + "return [location.href,document.title,'ok','unmatched',-1,'missing',0,'profile',chosenId,chosenName].join('\\u001f');}"
                // Fuera de la búsqueda y del reproductor (la portada tras elegir perfil)
                // se vuelve a la búsqueda, que es donde estaba el título que se pidió.
                + "if(!auth&&!location.pathname.startsWith('/search')&&!location.pathname.includes('/watch/')){"
                + "location.href=" + searchLiteral + ";action='search_again';"
                + "return [location.href,document.title,'ok','unmatched',-1,'missing',0,action,chosenId,chosenName].join('\\u001f');}"
                // La búsqueda de Netflix ya no da enlaces «/title/»: cada resultado es
                // un «standard-card», un <a> cuyo href lleva «jbv=<id del vídeo>».
                // Medido contra la página real: buscando sólo «/title/» lo único que
                // aparecía eran las notificaciones del menú. Del card se saca el id y
                // se va al reproductor, que es a donde lleva pulsarlo. Sólo se toma la
                // tarjeta que se llama como el título pedido; si el conjunto de tarjetas
                // lleva tres segundos quieto sin ninguna así, sus nombres vuelven como
                // candidatos (en el campo del nombre, separados por U+001E).
                + "if(!auth&&location.pathname.startsWith('/search')){"
                + "const cards=[...document.querySelectorAll('a[data-uia=\"standard-card\"],a[href*=\"jbv=\"]')];"
                + "const named=cards.map(a=>({a,n:((a.getAttribute('aria-label')||a.innerText||'').trim())}));"
                + "const hit=named.find(x=>fold(x.n)===wanted);"
                + "if(hit){chosenName=hit.n;const id=(hit.a.getAttribute('href')||'').match(/jbv=(\\d+)/);"
                + "if(id){chosenId=id[1];location.href='https://www.netflix.com/watch/'+id[1];action='watch_nav';}"
                + "else{hit.a.click();action='result_clicked';}"
                + "return [location.href,document.title,'ok','unmatched',-1,'missing',0,action,chosenId,chosenName].join('\\u001f');}"
                + "if(cards.length&&still(cards)){"
                + "return [location.href,document.title,'ok','unmatched',-1,'missing',0,'no_exact','',named.map(x=>x.n).filter(n=>n).join('\\u001e')].join('\\u001f');}}"
                + "if(!auth&&!location.pathname.includes('/watch/')){const controls=[...document.querySelectorAll('[data-uia=\"play-button\"],button,a')];"
                + "const play=controls.find(e=>{const s=((e.getAttribute('aria-label')||'')+' '+(e.innerText||'')).toLowerCase();"
                + "return s==='play'||s.includes('reproducir')||s.startsWith('play ');});"
                + "if(play){play.click();action='play_clicked';}}"
                + "const v=document.querySelector('video');if(v&&v.paused){v.play().catch(()=>{});}"
                + "const matched=fold(document.title+' '+(document.body?.innerText||'')).includes(wanted);"
                + "return [location.href,document.title,auth?'auth':'ok',matched?'matched':'unmatched',"
                + "v?v.readyState:-1,v?(v.paused?'paused':'playing'):'missing',v?v.currentTime:0,action,chosenId,chosenName].join('\\u001f');})()",
                cancellationToken,
                userGesture: true).ConfigureAwait(false);
            lastObserved = observed;
            string[] fields = observed.Split('\u001f');
            if (fields.Length != 10) continue;
            lastUrl = fields[0]; lastPageTitle = fields[1];
            if (fields[2] == "auth")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    "netflix_authentication_required");
            if (fields[7] == "profile")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    UserBrowserSurface.StreamingProfileChoice);
            if (fields[7] == "no_exact")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    UserBrowserSurface.StreamingTitleNotFound, observed,
                    fields[9].Split('\u001e', StringSplitOptions.RemoveEmptyEntries));
            // La ficha elegida en la búsqueda se recuerda entre vueltas: el guion
            // vuelve a empezar en cada evaluación y para entonces ya está en la
            // página del reproductor, donde no quedan tarjetas que mirar.
            if (fields[8].Length > 0) chosenId = fields[8];
            if (fields[9].Length > 0) chosenName = fields[9];
            bool watch = lastUrl.Contains("netflix.com/watch/", StringComparison.OrdinalIgnoreCase);
            bool ready = int.TryParse(fields[4], NumberStyles.Integer,
                CultureInfo.InvariantCulture, out int readyState) && readyState >= 2;
            bool progressing = double.TryParse(fields[6], NumberStyles.Float,
                CultureInfo.InvariantCulture, out double currentTime);
            // Lo que prueba que se abrió lo pedido es la ficha que se eligió —la que se
            // llama como el pedido—, no que la página del reproductor repita el nombre.
            // Sin ficha elegida (navegación directa) se conserva la comprobación del
            // texto.
            // Medido: la ficha de «Stranger Things» es la 80057281 y el reproductor
            // acaba en /watch/80077368, porque la primera es la serie y la segunda el
            // episodio al que Netflix redirige. Exigir que la URL lleve el id elegido
            // rechazaba una reproducción correcta. Basta con haber elegido la ficha y
            // estar en un reproductor: la redirección es suya, no nuestra.
            bool opened = chosenId.Length > 0 || fields[3] == "matched";
            if (watch && opened && ready
                && fields[5] == "playing" && progressing)
            {
                if (baseline is not null && currentTime >= baseline.Value + 0.5)
                    return new(true, true,
                        chosenName.Length > 0 ? chosenName : title,
                        lastUrl, lastPageTitle, targetId,
                        currentTime - baseline.Value, string.Empty);
                baseline ??= currentTime;
                failure = "netflix_video_progress_not_observed";
            }
        }
        return new(false, true, title, lastUrl, lastPageTitle, targetId, 0, failure,
            lastObserved + "|remembered=" + chosenId + "/" + chosenName);
    }

    // VIDEO1947 «pon Daredevil en Disney+»: medido en el perfil compartido con la
    // sesión del dueño. El enlace frío /play/<id> se queda cargando para siempre
    // (el puente de identidad de login.disney.com falla: «Scope is not present»);
    // la ruta que reproduce es la de una persona: la búsqueda (/browse/search,
    // #searchInput), la ficha (a[data-testid="set-item"] → /browse/entity-<id>) y
    // su botón «Ver ahora» (a[data-testid="playback-action-button"]). Con el
    // agente de usuario de Edge el reproductor elige PlayReady y el renderizador
    // de Media Foundation de este PC falla (0x8004CD…); con uno de Chrome elige
    // Widevine y el vídeo avanza. El primer <video> de la página es un elemento
    // de fondo que nunca sale de readyState 0: se mira el que avanza.
    private const string DisneyChromeUserAgent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        + "Chrome/153.0.0.0 Safari/537.36";

    internal virtual async ValueTask<CdpStreamingPlaybackResult> PlayDisneyAsync(
        string title,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(title) || Encoding.UTF8.GetByteCount(title) > 512)
            return new(false, false, title, string.Empty, string.Empty, string.Empty, 0,
                "disney_title_invalid");
        Uri endpoint = await EnsureEndpointAsync(cancellationToken).ConfigureAwait(false);
        (string targetId, Uri webSocket) = await ResolveTargetAsync(
            endpoint, createIfMissing: true, cancellationToken).ConfigureAwait(false);
        using var socket = new ClientWebSocket();
        await socket.ConnectAsync(webSocket, cancellationToken).ConfigureAwait(false);
        // El override vive con esta sesión CDP: dura lo que dura el socket, sólo
        // para este destino; Netflix y las navegaciones nombradas no lo ven.
        await CommandAsync(socket, "Emulation.setUserAgentOverride", writer =>
        {
            writer.WriteString("userAgent", DisneyChromeUserAgent);
        }, cancellationToken).ConfigureAwait(false);
        const string searchUrl = "https://www.disneyplus.com/es-419/browse/search";
        JsonElement navigate = await CommandAsync(socket, "Page.navigate", writer =>
        {
            writer.WriteString("url", searchUrl);
        }, cancellationToken).ConfigureAwait(false);
        if (navigate.TryGetProperty("error", out _))
            return new(false, false, title, searchUrl, string.Empty, targetId, 0,
                "cdp_navigation_rejected");
        string titleLiteral = "\"" + JsonEncodedText.Encode(title).ToString() + "\"";
        double? baseline = null;
        string lastUrl = searchUrl;
        string lastPageTitle = string.Empty;
        string chosenHref = string.Empty;
        string chosenName = string.Empty;
        string lastObserved = string.Empty;
        // Tras una recarga de la búsqueda el cuadro vuelve vacío: se escribe de nuevo, pocas veces.
        int typed = 0;
        string failure = "disney_title_or_play_control_not_found";
        for (int attempt = 0; attempt <= 240; attempt++)
        {
            if (attempt > 0)
            {
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }

            string observed = await EvaluateStringAsync(
                socket,
                "(()=>{" + StreamingCardScript + "const wanted=fold(" + titleLiteral + ");"
                + "let chosenHref='',chosenName='',action='none';"
                + "const body=(document.body?.innerText||'').toLowerCase();"
                + "const auth=location.pathname.includes('/login')||location.pathname.includes('/begin')||"
                + "body.includes('inicia sesión')||body.includes('iniciar sesión')||body.includes('log in');"
                + "const p=location.pathname;"
                // El aria-label de la ficha trae el título y detrás la clasificación, el
                // estreno y el género («Daredevil Clasificación: 18+. Estreno: 2015. …»)
                // o la invitación a abrirla; el nombre es lo que hay antes de esos rótulos.
                // Una ficha de serie o película lleva a /browse/entity-<id>; una de
                // colección («Daredevil» como universo), a /browse/page-<id>, que no tiene
                // botón de reproducir: entre iguales se prefiere la ficha de la obra.
                + "const clean=s=>(s||'').split(/\\s+(?:(?:Clasificaci[oó]n|Rating|Estreno|Release|G[eé]nero|Genre)\\s*:|Selecciona esta opci[oó]n|Select this option)/)[0].trim();"
                + "const isEntity=a=>(a.getAttribute('href')||'').includes('/browse/entity-');"
                // VIDEO1951: una página de Disney+ puede quedarse sin renderizar (título
                // «Disney+» y ningún control durante el resto del minuto). Diez segundos
                // sin el control que toca —el cuadro de búsqueda, las fichas o el botón—
                // se recarga esa página una sola vez; la marca vive en la pestaña.
                + "const stalled=()=>{const k='baxyReload:'+p;window.__baxyStall=(window.__baxyStall||0)+1;"
                + "if(window.__baxyStall>40&&!sessionStorage.getItem(k)){sessionStorage.setItem(k,'1');window.__baxyStall=0;location.reload();return 'reload';}return 'none';};"
                // Sólo se elige la ficha que se llama como el pedido. Sin ninguna así, cuando
                // el conjunto lleva tres segundos quieto, la elección devuelve los nombres
                // de las fichas (una lista) para decirlos como candidatos.
                + "const pick=list=>list.find(x=>x.t===wanted);"
                + "const choose=cards=>{const named=cards.map(a=>({a,t:fold(clean(a.getAttribute('aria-label')||a.innerText)),n:clean(a.getAttribute('aria-label')||a.innerText)}));"
                + "const hit=pick(named.filter(x=>isEntity(x.a)))||pick(named);"
                + "if(hit)return hit;return still(cards)?named.map(x=>x.n).filter(n=>n):null;};"
                + "const near=names=>[location.href,document.title,'ok',-1,'missing',0,'no_exact','',names.join('\\u001e'),'cards'].join('\\u001f');"
                // La búsqueda: el cuadro se enfoca aquí y el texto lo escribe CDP
                // (Input.insertText), porque el valor puesto por JS no dispara la
                // búsqueda de la página.
                + "if(!auth&&p.includes('/browse/search')){const input=document.querySelector('#searchInput,input[type=\"search\"]');"
                + "const cards=[...document.querySelectorAll('a[data-testid=\"set-item\"]')];"
                + "const hrefs=cards.map(a=>a.getAttribute('href')||'').join(',');"
                // VIDEO1947: la página de búsqueda trae fichas por defecto antes de que se
                // escriba nada, y con el texto recién escrito siguen ahí un instante. Las
                // fichas de antes de escribir se recuerdan y sólo se elige cuando cambian.
                + "if(!(input?.value||'').length){window.__baxyPreSearch=hrefs;window.__baxyNoHit=0;}"
                + "const fresh=cards.length&&hrefs!==(window.__baxyPreSearch??'');"
                + "if(fresh&&(input?.value||'').length){"
                + "const hit=choose(cards);if(Array.isArray(hit))return near(hit);"
                + "if(hit){chosenName=hit.n;chosenHref=hit.a.getAttribute('href')||'';if(chosenHref){location.href=chosenHref;action='entity_nav';}"
                + "return [location.href,document.title,'ok',-1,'missing',0,action,chosenHref,chosenName,'cards'].join('\\u001f');}}"
                + "if(input){window.__baxyStall=0;input.focus();return [location.href,document.title,'ok',-1,'missing',0,'input_focused','','',(input.value||'').length?'typed':'empty'].join('\\u001f');}"
                + "action=stalled();return [location.href,document.title,'ok',-1,'missing',0,action,'','','search'].join('\\u001f');}"
                // La colección: si la búsqueda llevó a una página de universo, la obra
                // se elige entre sus fichas con la misma lectura.
                + "if(!auth&&p.includes('/browse/page-')){const cards=[...document.querySelectorAll('a[data-testid=\"set-item\"]')].filter(isEntity);"
                + "const hit=cards.length?choose(cards):null;if(Array.isArray(hit))return near(hit);"
                + "if(hit){chosenName=hit.n;chosenHref=hit.a.getAttribute('href')||'';if(chosenHref){location.href=chosenHref;action='entity_nav';}}"
                + "else if(!cards.length){action=stalled();}"
                + "return [location.href,document.title,'ok',-1,'missing',0,action,chosenHref,chosenName,'page'].join('\\u001f');}"
                // La ficha: su botón de reproducir lleva al reproductor por la
                // propia aplicación (SPA), que es la ruta que arranca.
                + "if(!auth&&p.includes('/browse/entity-')){const play=document.querySelector('a[data-testid=\"playback-action-button\"],button[data-testid=\"playback-action-button\"]');"
                + "if(play){play.click();action='play_clicked';}else{action=stalled();}"
                + "return [location.href,document.title,'ok',-1,'missing',0,action,'','','entity'].join('\\u001f');}"
                // El reproductor: el <video> que avanza es la prueba.
                + "const vids=[...document.querySelectorAll('video')];"
                + "const v=vids.find(x=>x.readyState>=2&&!x.paused)||vids.find(x=>x.readyState>=2)||vids[vids.length-1];"
                + "if(v&&v.paused&&v.readyState>=2){v.play().catch(()=>{});}"
                + "return [location.href,document.title,auth?'auth':'ok',v?v.readyState:-1,v?(v.paused?'paused':'playing'):'missing',v?v.currentTime:0,action,'','',p.includes('/play/')?'player':'other'].join('\\u001f');})()",
                cancellationToken,
                userGesture: true).ConfigureAwait(false);
            lastObserved = observed;
            string[] fields = observed.Split('\u001f');
            if (fields.Length != 10) continue;
            lastUrl = fields[0]; lastPageTitle = fields[1];
            if (fields[2] == "auth")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    "disney_authentication_required");
            if (fields[6] == "no_exact")
                return new(false, true, title, lastUrl, lastPageTitle, targetId, 0,
                    UserBrowserSurface.StreamingTitleNotFound, observed,
                    fields[8].Split('\u001e', StringSplitOptions.RemoveEmptyEntries));
            if (fields[7].Length > 0) chosenHref = fields[7];
            if (fields[8].Length > 0) chosenName = fields[8];
            if (fields[6] == "input_focused" && typed < 3 && fields[9] == "empty")
            {
                await CommandAsync(socket, "Input.insertText", writer =>
                {
                    writer.WriteString("text", title);
                }, cancellationToken).ConfigureAwait(false);
                typed++;
                continue;
            }
            bool player = fields[9] == "player";
            bool ready = int.TryParse(fields[3], NumberStyles.Integer,
                CultureInfo.InvariantCulture, out int readyState) && readyState >= 2;
            bool progressing = double.TryParse(fields[5], NumberStyles.Float,
                CultureInfo.InvariantCulture, out double currentTime);
            if (player && chosenHref.Length > 0 && ready && fields[4] == "playing" && progressing)
            {
                // El reproductor titula la pestaña «<título> | Disney+»: es el nombre
                // observado más limpio que hay; la ficha elegida queda de reserva.
                string pageName = lastPageTitle.Contains(" | ", StringComparison.Ordinal)
                    ? lastPageTitle[..lastPageTitle.IndexOf(" | ", StringComparison.Ordinal)].Trim()
                    : string.Empty;
                if (baseline is not null && currentTime >= baseline.Value + 0.5)
                    return new(true, true,
                        pageName.Length > 0 ? pageName : chosenName.Length > 0 ? chosenName : title,
                        lastUrl, lastPageTitle, targetId,
                        currentTime - baseline.Value, string.Empty);
                baseline ??= currentTime;
                failure = "disney_video_progress_not_observed";
            }
        }
        return new(false, true, title, lastUrl, lastPageTitle, targetId, 0, failure,
            lastObserved + "|remembered=" + chosenHref + "/" + chosenName);
    }

    // Pasada r15b v3-57: the browser is the person's window (the page they asked for), so BAXY closing leaves it open;
    // only the connection is released. A later session on the same profile reattaches to it (TryReattachAsync).
    public virtual void Dispose()
    {
        _http.Dispose();
        _ownedProcess?.Dispose();
    }

    internal const string OwnerRecordName = "baxy-browser-owner";

    /// <summary>The launch of the CDP browser: outside BAXY's kill-on-close job, inheriting none of its handles.</summary>
    internal static InvokerLaunch.LaunchPlan LaunchPlan(string browser, string profile)
    {
        static string Quoted(string argument) =>
            argument.Contains(' ', StringComparison.Ordinal) ? "\"" + argument + "\"" : argument;
        string[] arguments =
        [
            // The port is bound to loopback and the profile is BAXY's own. No --remote-allow-origins: BAXY's own
            // client sends no Origin, so it still connects, while any web page (in this browser or in another one
            // on the machine) that finds the port is refused, now that the browser outlives BAXY.
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            // The window is the person's, but it is started while BAXY's local model holds the GPU: GPU
            // acceleration adds a GPU process and its video memory to the same card (WEB1261: 3874 MiB with the
            // local model, over the 3800 MiB budget). Pages and video still render in software; a person who
            // keeps it open for hours of video pays CPU, not the model's VRAM. Owner's call to change.
            "--disable-gpu",
            "--user-data-dir=" + profile,
            "about:blank",
        ];
        return new InvokerLaunch.LaunchPlan(
            browser,
            string.Join(' ', arguments.Select(Quoted)),
            Path.GetDirectoryName(browser) ?? Environment.SystemDirectory);
    }

    /// <summary>The owner record «pid start-ticks» of the browser this profile's sessions started; null when unreadable.</summary>
    internal static (int ProcessId, long StartTicks)? ParseOwnerRecord(string? record)
    {
        string[] parts = (record ?? string.Empty).Trim().Split(' ');
        return parts.Length == 2
            && int.TryParse(parts[0], NumberStyles.None, CultureInfo.InvariantCulture, out int processId)
            && processId > 0
            && long.TryParse(parts[1], NumberStyles.None, CultureInfo.InvariantCulture, out long startTicks)
            ? (processId, startTicks)
            : null;
    }

    internal static string OwnerRecord(int processId, long startTicks) =>
        processId.ToString(CultureInfo.InvariantCulture) + " " + startTicks.ToString(CultureInfo.InvariantCulture);

    // The browser a previous session of this profile started and left open for the person: the very process the
    // owner record names (same id and start time, the same executable) answering on the port its profile published.
    internal async ValueTask<Uri?> TryReattachAsync(
        string activePort, string browser, CancellationToken cancellationToken)
    {
        string ownerPath = Path.Combine(_profile, OwnerRecordName);
        if (!File.Exists(activePort) || !File.Exists(ownerPath))
            return null;
        Process? process = null;
        try
        {
            if (ParseOwnerRecord(await File.ReadAllTextAsync(ownerPath, cancellationToken).ConfigureAwait(false))
                    is not { } owner
                || (await File.ReadAllLinesAsync(activePort, cancellationToken).ConfigureAwait(false))
                    is not [string first, ..]
                || !ushort.TryParse(first, out ushort port) || port == 0)
                return null;
            process = Process.GetProcessById(owner.ProcessId);
            if (process.HasExited
                || process.StartTime.ToUniversalTime().Ticks != owner.StartTicks
                || process.MainModule?.FileName is not { } image
                || !string.Equals(Path.GetFullPath(image), Path.GetFullPath(browser), StringComparison.OrdinalIgnoreCase))
                return null;
            Uri candidate = new($"http://127.0.0.1:{port}/");
            using var readiness = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            readiness.CancelAfter(TimeSpan.FromMilliseconds(500));
            using HttpResponseMessage response = await _http.GetAsync(
                new Uri(candidate, "json/version"), readiness.Token).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                return null;
            _ownedProcess = process;
            process = null;
            _sessionTargets = new HashSet<string>(StringComparer.Ordinal);
            return candidate;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception or NotSupportedException or IOException
            or UnauthorizedAccessException or HttpRequestException)
        {
            return null;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
        finally
        {
            process?.Dispose();
        }
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
        string browser = _browserExecutable ?? ResolveEdge();
        if (await TryReattachAsync(activePort, browser, cancellationToken).ConfigureAwait(false) is { } reattached)
        {
            _endpoint = reattached;
            return reattached;
        }
        if (File.Exists(activePort))
        {
            File.Delete(activePort);
        }
        int processId = InvokerLaunch.StartOutsideBaxy(LaunchPlan(browser, _profile));
        try
        {
            _ownedProcess = processId > 0
                ? Process.GetProcessById(processId)
                : throw new IOException("CDP browser could not start.");
            await File.WriteAllTextAsync(
                Path.Combine(_profile, OwnerRecordName),
                OwnerRecord(processId, _ownedProcess.StartTime.ToUniversalTime().Ticks),
                cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            throw new IOException("CDP browser could not start.", exception);
        }
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

    /// <summary>
    /// The page target this session acts on: the first page of the list, restricted to <paramref name="sessionTargets"/>
    /// when the session reattached to a browser left open for the person (their own tabs are never chosen). Null when
    /// no such page exists.
    /// </summary>
    internal static (string TargetId, Uri WebSocket)? ChoosePageTarget(
        JsonElement targets,
        IReadOnlySet<string>? sessionTargets)
    {
        if (targets.ValueKind != JsonValueKind.Array)
            return null;
        foreach (JsonElement target in targets.EnumerateArray())
        {
            if (target.TryGetProperty("type", out JsonElement type)
                && type.GetString() == "page"
                && target.TryGetProperty("id", out JsonElement id)
                && id.GetString() is { Length: > 0 } targetId
                && (sessionTargets is null || sessionTargets.Contains(targetId))
                && target.TryGetProperty("webSocketDebuggerUrl", out JsonElement socket)
                && Uri.TryCreate(socket.GetString(), UriKind.Absolute, out Uri? webSocket))
            {
                return (targetId, webSocket);
            }
        }
        return null;
    }

    internal async ValueTask<(string TargetId, Uri WebSocket)> ResolveTargetAsync(
        Uri endpoint,
        bool createIfMissing,
        CancellationToken cancellationToken)
    {
        using (Stream stream = await _http.GetStreamAsync(new Uri(endpoint, "json/list"), cancellationToken)
            .ConfigureAwait(false))
        using (JsonDocument targets = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false))
        {
            if (ChoosePageTarget(targets.RootElement, _sessionTargets) is { } chosen)
                return chosen;
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
                && createdId.GetString() is { Length: > 0 } createdTarget
                && root.TryGetProperty("webSocketDebuggerUrl", out JsonElement createdSocket)
                && Uri.TryCreate(createdSocket.GetString(), UriKind.Absolute, out Uri? webSocket))
            {
                _sessionTargets?.Add(createdTarget);
                return (createdTarget, webSocket);
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
                && id.GetString() is { Length: > 0 } value
                && (_sessionTargets is null || _sessionTargets.Contains(value)))
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
