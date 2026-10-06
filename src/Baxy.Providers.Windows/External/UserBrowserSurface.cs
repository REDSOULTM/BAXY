using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Opens web pages, YouTube videos and streaming titles in the person's own
/// default browser —their profile and their signed-in sessions— and verifies
/// the effect without taking that browser over: the address field read through
/// UI Automation for a navigation, the system media session (SMTC) for playback.
/// Chromium ignores --remote-debugging-port on the default profile since
/// Chromium 136, so CDP on the person's browser would mean restarting it with
/// another profile; this surface never does that (documentacion/NAVEGADOR_USUARIO.md).
/// </summary>
internal sealed class UserBrowserSurface
{
    internal const string NavigationUnconfirmed = "user_browser_navigation_unconfirmed";
    internal const string PlaybackUnconfirmed = "user_browser_playback_unconfirmed";
    internal const string StreamingPlaybackUnconfirmed = "user_browser_streaming_playback_unconfirmed";
    internal const string StreamingProfileChoice = "user_browser_streaming_profile_choice";
    internal const string AddressAuthority = "user_browser_uia_address_postread";

    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(250);
    private const int NavigationPolls = 40;
    private const int PlaybackPolls = 60;
    // HBO Max took 12-15 s from its play control to a playing session (Opera GX, 2026-10-06).
    private const int StreamingPolls = 120;
    private const int AddressReads = 3;
    private const int PausedPollsBeforePlay = 8;

    private readonly IUserBrowserPlatform _platform;
    private readonly Func<string, string?> _environment;

    internal UserBrowserSurface(IUserBrowserPlatform platform, Func<string, string?>? environment = null)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _environment = environment ?? Environment.GetEnvironmentVariable;
    }

    /// <summary>
    /// The person's browser when pages should open there; null keeps the
    /// product's own CDP browser: BAXY_BROWSER=product asks for it, and a
    /// measurement fixture that points BAXY_CDP_ENDPOINT at its own browser
    /// keeps it too.
    /// </summary>
    internal UserBrowserIdentity? Resolve()
    {
        if (string.Equals(_environment("BAXY_BROWSER")?.Trim(), "product", StringComparison.OrdinalIgnoreCase)
            || !string.IsNullOrWhiteSpace(_environment("BAXY_CDP_ENDPOINT")))
            return null;
        return _platform.ResolveDefault();
    }

    /// <summary>A navigation in the person's browser; null when the browser could not be launched at all.</summary>
    internal async ValueTask<ExternalCapabilityReceipt?> NavigateAsync(
        string operation,
        UserBrowserIdentity browser,
        Uri target,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        Dictionary<nint, string> before = WindowTitles(browser);
        if (!TryOpen(target, effectBoundary, cancellationToken))
            return null;
        PageObservation seen = await ObserveNavigationAsync(
            browser, address => SameSite(target, address), before, cancellationToken).ConfigureAwait(false);
        if (seen.Address is null)
            return ExternalJson.FailureAfterEffect(operation, NavigationUnconfirmed);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedUrl", target.AbsoluteUri);
            writer.WriteString("finalUrl", seen.Address.AbsoluteUri);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("browserFamily", browser.Family);
            writer.WriteString("authority", AddressAuthority);
            writer.WriteEndObject();
        }));
    }

    internal async ValueTask<ExternalCapabilityReceipt?> StreamingNavigateAsync(
        string operation,
        UserBrowserIdentity browser,
        string service,
        Uri target,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        Dictionary<nint, string> before = WindowTitles(browser);
        if (!TryOpen(target, effectBoundary, cancellationToken))
            return null;
        Func<Uri, bool> ofService = address => SameSite(target, address)
            || WebBrowserAdapter.HostMatchesService(address.Host, service);
        PageObservation seen = await ObserveNavigationAsync(browser, ofService, before, cancellationToken)
            .ConfigureAwait(false);
        if (seen.Address is null)
            return ExternalJson.FailureAfterEffect(operation, NavigationUnconfirmed);
        Uri landed = await SettledAddressAsync(seen.Address, seen.Window, ofService, cancellationToken)
            .ConfigureAwait(false);
        if (!WebBrowserAdapter.HostMatchesService(landed.Host, service))
            return ExternalJson.Failure(operation, "streaming_redirect_left_service", true);
        if (AsksToSignIn(landed))
            return ExternalJson.Failure(operation, "streaming_authentication_required", true);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("resourceUri", landed.AbsoluteUri);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("authority", AddressAuthority);
            writer.WriteEndObject();
        }));
    }

    internal async ValueTask<ExternalCapabilityReceipt?> PlayYouTubeAsync(
        string operation,
        UserBrowserIdentity browser,
        string query,
        YouTubeSearchResult video,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        IReadOnlyList<UserMediaSession> before = await _platform.ReadMediaSessionsAsync(cancellationToken)
            .ConfigureAwait(false);
        if (!TryOpen(video.WatchUri, effectBoundary, cancellationToken))
            return null;
        UserMediaSession? playing = await AwaitPlaybackAsync(
            browser, video.Title, before, PlaybackPolls, cancellationToken).ConfigureAwait(false);
        if (playing is null)
            return ExternalJson.FailureAfterEffect(operation, PlaybackUnconfirmed);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "youtube");
            writer.WriteString("query", query);
            writer.WriteString("title", playing.Title.Length > 0 ? playing.Title : video.Title);
            writer.WriteString("finalUrl", video.WatchUri.AbsoluteUri);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("sourceAppUserModelId", playing.SourceAppUserModelId);
            writer.WriteString("playbackStatus", "playing");
            writer.WriteString("authority", "user_browser_smtc_postread");
            writer.WriteEndObject();
        }));
    }

    internal async ValueTask<ExternalCapabilityReceipt?> PlayStreamingNamedAsync(
        string operation,
        UserBrowserIdentity browser,
        string service,
        string title,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        StreamingSearch search = SearchFor(service, title);
        IReadOnlyList<UserMediaSession> sessionsBefore = await _platform.ReadMediaSessionsAsync(cancellationToken)
            .ConfigureAwait(false);
        Dictionary<nint, string> windowsBefore = WindowTitles(browser);
        if (!TryOpen(search.Address, effectBoundary, cancellationToken))
            return null;
        Func<Uri, bool> ofService = address => SameSite(search.Address, address)
            || WebBrowserAdapter.HostMatchesService(address.Host, service);
        PageObservation seen = await ObserveNavigationAsync(browser, ofService, windowsBefore, cancellationToken)
            .ConfigureAwait(false);
        if (seen.Address is null)
            return ExternalJson.FailureAfterEffect(operation, StreamingPlaybackUnconfirmed);
        Uri landed = await SettledAddressAsync(seen.Address, seen.Window, ofService, cancellationToken)
            .ConfigureAwait(false);
        if (AsksToSignIn(landed))
            return ExternalJson.Failure(operation, search.SignInCode, true);
        UserBrowserPageStep step = await _platform.StartTitleInPageAsync(
            seen.Window, title, search.TypeTitle, cancellationToken).ConfigureAwait(false);
        // "Who's watching?" is the person's choice: the page stays open on it and nothing is picked for them.
        if (step.Step == "profile")
            return ExternalJson.FailureAfterEffect(operation, StreamingProfileChoice);
        // No play control pressed: whatever plays now (a detail page's own trailer) is not the title asked for.
        if (!step.PlayInvoked)
            return ExternalJson.FailureAfterEffect(operation, StreamingPlaybackUnconfirmed);
        // The session is matched against the title asked for: Disney+ names it "Bluey | Disney+", HBO Max "The Last
        // of Us", while a card's own name runs on ("Coco Clasificación: 0+...").
        UserMediaSession? playing = await AwaitPlaybackAsync(
            browser, title, sessionsBefore, StreamingPolls, cancellationToken, anyNewBrowserSession: true)
            .ConfigureAwait(false);
        if (playing is null)
            return ExternalJson.FailureAfterEffect(operation, StreamingPlaybackUnconfirmed);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("title", step.Chosen.Length > 0 ? step.Chosen : title);
            writer.WriteString("sessionTitle", playing.Title);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("sourceAppUserModelId", playing.SourceAppUserModelId);
            writer.WriteString("playbackStatus", "playing");
            writer.WriteString("authority", "user_browser_smtc_postread");
            writer.WriteEndObject();
        }));
    }

    private sealed record StreamingSearch(Uri Address, bool TypeTitle, string SignInCode);

    /// <summary>
    /// Where each service searches in the person's session. Netflix and HBO Max take the title in the address
    /// (HBO Max's own search writes <c>search/result?q=</c>); Disney+ has no such parameter, so its search page gets
    /// the title typed into its own field. Disney+'s address carries no locale: the account's language decides.
    /// </summary>
    private static StreamingSearch SearchFor(string service, string title) => service switch
    {
        "netflix" => new(
            new Uri("https://www.netflix.com/search?q=" + Uri.EscapeDataString(title)),
            false, "netflix_authentication_required"),
        "hbo_max" => new(
            new Uri("https://play.hbomax.com/search/result?q="
                + Uri.EscapeDataString(title).Replace("%20", "+", StringComparison.Ordinal)),
            false, "hbo_max_authentication_required"),
        _ => new(new Uri("https://www.disneyplus.com/browse/search"), true, "disney_authentication_required"),
    };

    private bool TryOpen(Uri target, ExternalEffectBoundary effectBoundary, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            _platform.Open(target);
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception
            or InvalidOperationException or FileNotFoundException or ArgumentException)
        {
            // Nothing was launched: the caller keeps the product browser as fallback.
            return false;
        }
        // The link is out: from here the effect may have happened whatever the token says.
        effectBoundary.Cross(CancellationToken.None);
        return true;
    }

    internal const string BrowserNotRunning = "user_browser_not_running";
    internal const string PageUnreadable = "user_browser_page_unreadable";
    internal const string PageAuthority = "user_browser_uia_page_text";
    internal const string TabsAuthority = "user_browser_uia_tab_strip";

    /// <summary>
    /// Owner 2026-10-06: what the person asks of «the page» or «the tabs» is about their own browser, never about a
    /// browser BAXY keeps aside. The front window of their browser is read through UI Automation: the page's title and
    /// visible text (its RootWebArea document), nothing else of the browser.
    /// </summary>
    internal async ValueTask<ExternalCapabilityReceipt> ReadPageAsync(
        string operation,
        UserBrowserIdentity browser,
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        UserBrowserWindow? window = FrontWindow(browser);
        if (window is null)
            return ExternalJson.FailureBeforeEffect(operation, BrowserNotRunning);
        UserBrowserPageText? page = await _platform.ReadPageTextAsync(
            window.Handle, maximumCharacters, cancellationToken).ConfigureAwait(false);
        if (page is null)
            return ExternalJson.FailureBeforeEffect(operation, PageUnreadable);
        string? address = await _platform.ReadAddressAsync(window.Handle, cancellationToken).ConfigureAwait(false);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("url", address ?? string.Empty);
            writer.WriteString("title", page.Title);
            writer.WriteString("text", page.Text);
            writer.WriteBoolean("truncated", page.Truncated);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("authority", PageAuthority);
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    /// <summary>The tabs of the front window of the person's browser, read from its tab strip.</summary>
    internal async ValueTask<ExternalCapabilityReceipt> ListTabsAsync(
        string operation,
        UserBrowserIdentity browser,
        int limit,
        CancellationToken cancellationToken)
    {
        UserBrowserWindow? window = FrontWindow(browser);
        if (window is null)
            return ExternalJson.FailureBeforeEffect(operation, BrowserNotRunning);
        IReadOnlyList<UserBrowserTab>? tabs = await _platform.ReadTabsAsync(window.Handle, cancellationToken)
            .ConfigureAwait(false);
        if (tabs is null || tabs.Count == 0)
            return ExternalJson.FailureBeforeEffect(operation, PageUnreadable);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("count", tabs.Count);
            writer.WriteBoolean("truncated", tabs.Count > limit);
            writer.WriteStartArray("tabs");
            foreach (UserBrowserTab tab in tabs.Take(limit))
            {
                writer.WriteStartObject();
                writer.WriteString("title", tab.Title);
                writer.WriteBoolean("active", tab.Selected);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("authority", TabsAuthority);
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    /// <summary>The browser window the person sees on top (windows come in z-order), if the browser runs at all.</summary>
    private UserBrowserWindow? FrontWindow(UserBrowserIdentity browser)
    {
        IReadOnlyList<UserBrowserWindow> windows = _platform.ListWindows(browser.ProcessName);
        return windows.Count > 0 ? windows[0] : null;
    }

    private Dictionary<nint, string> WindowTitles(UserBrowserIdentity browser) =>
        _platform.ListWindows(browser.ProcessName)
            .GroupBy(window => window.Handle)
            .ToDictionary(group => group.Key, group => group.First().Title);

    private readonly record struct PageObservation(Uri? Address, nint Window);

    /// <summary>
    /// After the link is opened, a window of the person's browser changes (a new
    /// tab is active, or a new window appears). Its address field is read and
    /// only its site is compared with the one opened (for a streaming service,
    /// any of its hosts); an address of another site is never reported. With
    /// no readable address of that site the navigation stays unconfirmed.
    /// </summary>
    private async ValueTask<PageObservation> ObserveNavigationAsync(
        UserBrowserIdentity browser,
        Func<Uri, bool> opened,
        Dictionary<nint, string> before,
        CancellationToken cancellationToken)
    {
        int reads = 0;
        var readTitles = new Dictionary<nint, string>();
        for (int attempt = 0; attempt < NavigationPolls && reads < AddressReads; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            IEnumerable<UserBrowserWindow> changed = _platform.ListWindows(browser.ProcessName)
                .Where(window => !before.TryGetValue(window.Handle, out string? title)
                    || !string.Equals(title, window.Title, StringComparison.Ordinal));
            foreach (UserBrowserWindow window in changed)
            {
                if (reads >= AddressReads)
                    break;
                // A window is read again only once its title moved on: an address
                // field read while the new tab was still being built says nothing.
                if (readTitles.TryGetValue(window.Handle, out string? read)
                    && string.Equals(read, window.Title, StringComparison.Ordinal))
                    continue;
                readTitles[window.Handle] = window.Title;
                reads++;
                string? text = await _platform.ReadAddressAsync(window.Handle, cancellationToken)
                    .ConfigureAwait(false);
                if (TryAddress(text, out Uri? observed) && opened(observed))
                    return new(observed, window.Handle);
            }
        }
        return new(null, nint.Zero);
    }

    /// <summary>The address a moment later: a service that asks to sign in redirects after the first paint.</summary>
    private async ValueTask<Uri> SettledAddressAsync(
        Uri first, nint window, Func<Uri, bool> ofService, CancellationToken cancellationToken)
    {
        await _platform.DelayAsync(TimeSpan.FromMilliseconds(2_500), cancellationToken).ConfigureAwait(false);
        string? text = await _platform.ReadAddressAsync(window, cancellationToken).ConfigureAwait(false);
        return TryAddress(text, out Uri? later) && (SameSite(first, later) || ofService(later)) ? later : first;
    }

    private async ValueTask<UserMediaSession?> AwaitPlaybackAsync(
        UserBrowserIdentity browser,
        string expectedTitle,
        IReadOnlyList<UserMediaSession> before,
        int polls,
        CancellationToken cancellationToken,
        bool anyNewBrowserSession = false)
    {
        int notPlaying = 0;
        bool nudged = false;
        for (int attempt = 0; attempt < polls; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            IReadOnlyList<UserMediaSession> sessions = await _platform.ReadMediaSessionsAsync(cancellationToken)
                .ConfigureAwait(false);
            UserMediaSession? candidate = PlaybackCandidate(
                browser, expectedTitle, before, sessions, anyNewBrowserSession);
            if (candidate is null)
                continue;
            if (candidate.PlaybackStatus == "playing")
                return candidate;
            // The page loaded the video but the browser held autoplay back: the
            // session's own play control is what a person would press. Only a
            // session that carries the asked title is pressed, never another one
            // the person had paused.
            if (++notPlaying >= PausedPollsBeforePlay && !nudged
                && TitlesMatch(candidate.Title, expectedTitle)
                && candidate.PlaybackStatus is "paused" or "stopped" or "opened")
            {
                nudged = true;
                _ = await _platform.PlayMediaSessionAsync(candidate, cancellationToken).ConfigureAwait(false);
            }
        }
        return null;
    }

    /// <summary>
    /// The session the opened page started: one whose title is the expected
    /// one (the browser's own sessions first), or —for a service whose session
    /// title is not the title asked for— a session of the person's browser that
    /// had no session with that title before the page was opened.
    /// </summary>
    internal static UserMediaSession? PlaybackCandidate(
        UserBrowserIdentity browser,
        string expectedTitle,
        IReadOnlyList<UserMediaSession> before,
        IReadOnlyList<UserMediaSession> sessions,
        bool anyNewBrowserSession)
    {
        if (expectedTitle.Length > 0)
        {
            UserMediaSession? titled = sessions
                .Where(session => TitlesMatch(session.Title, expectedTitle)
                    && !(anyNewBrowserSession && AlreadyThere(session, before)))
                .OrderByDescending(session => browser.OwnsMediaSession(session.SourceAppUserModelId))
                .ThenByDescending(session => session.PlaybackStatus == "playing")
                .FirstOrDefault();
            if (titled is not null)
                return titled;
        }
        if (expectedTitle.Length > 0 && !anyNewBrowserSession)
            return null;
        // Without the title: a session of the person's browser whose title was
        // not there before the page was opened (paused or playing alike), so a
        // video the person already had is never taken for the new one.
        return sessions
            .Where(session => browser.OwnsMediaSession(session.SourceAppUserModelId)
                && !before.Any(earlier => string.Equals(earlier.SourceAppUserModelId,
                        session.SourceAppUserModelId, StringComparison.Ordinal)
                    && string.Equals(earlier.Title, session.Title, StringComparison.Ordinal)))
            .OrderByDescending(session => session.PlaybackStatus == "playing")
            .FirstOrDefault();
    }

    /// <summary>
    /// The same session, title and state as before the page was opened: a title the person had paused in another
    /// tab (Opera keeps one media session for the whole browser) is not what the new page started.
    /// </summary>
    private static bool AlreadyThere(UserMediaSession session, IReadOnlyList<UserMediaSession> before) =>
        before.Any(earlier => string.Equals(earlier.SourceAppUserModelId, session.SourceAppUserModelId,
                StringComparison.Ordinal)
            && string.Equals(earlier.Title, session.Title, StringComparison.Ordinal)
            && string.Equals(earlier.PlaybackStatus, session.PlaybackStatus, StringComparison.Ordinal));

    internal static bool TitlesMatch(string observed, string expected)
    {
        string left = Fold(observed);
        string right = Fold(expected);
        if (left.Length < 3 || right.Length < 3)
            return false;
        if (left == right || left.Contains(right, StringComparison.Ordinal)
            || right.Contains(left, StringComparison.Ordinal))
            return true;
        HashSet<string> a = left.Split(' ', StringSplitOptions.RemoveEmptyEntries).ToHashSet(StringComparer.Ordinal);
        HashSet<string> b = right.Split(' ', StringSplitOptions.RemoveEmptyEntries).ToHashSet(StringComparer.Ordinal);
        int shared = a.Count(b.Contains);
        return shared >= 2 && shared * 10 >= Math.Max(a.Count, b.Count) * 6;
    }

    internal static bool TryAddress(string? text, [System.Diagnostics.CodeAnalysis.NotNullWhen(true)] out Uri? address)
    {
        address = null;
        if (string.IsNullOrWhiteSpace(text))
            return false;
        string value = text.Trim();
        if (value.Any(char.IsWhiteSpace))
            return false;
        if (!value.Contains("://", StringComparison.Ordinal))
            value = "https://" + value;
        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? parsed)
            || parsed.Scheme is not ("http" or "https")
            || !parsed.Host.Contains('.', StringComparison.Ordinal))
            return false;
        address = parsed;
        return true;
    }

    /// <summary>The same site modulo «www.» and subdomains of the site opened (youtube.com → m.youtube.com).</summary>
    internal static bool SameSite(Uri requested, Uri observed)
    {
        string want = BareHost(requested.Host);
        string seen = BareHost(observed.Host);
        return string.Equals(want, seen, StringComparison.OrdinalIgnoreCase)
            || seen.EndsWith("." + want, StringComparison.OrdinalIgnoreCase)
            || want.EndsWith("." + seen, StringComparison.OrdinalIgnoreCase);
    }

    private static bool AsksToSignIn(Uri address) =>
        address.AbsolutePath.Contains("login", StringComparison.OrdinalIgnoreCase)
        || address.AbsolutePath.Contains("signin", StringComparison.OrdinalIgnoreCase)
        || address.AbsolutePath.Contains("sign-in", StringComparison.OrdinalIgnoreCase);

    private static string BareHost(string host)
    {
        string value = host.Trim().TrimEnd('.').ToLowerInvariant();
        return value.StartsWith("www.", StringComparison.Ordinal) ? value[4..] : value;
    }

    private static string Fold(string text)
    {
        string decomposed = (text ?? string.Empty).Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        bool space = false;
        foreach (char character in decomposed)
        {
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(character);
            if (category == UnicodeCategory.NonSpacingMark)
                continue;
            if (char.IsLetterOrDigit(character))
            {
                builder.Append(char.ToLowerInvariant(character));
                space = false;
            }
            else if (!space && builder.Length > 0)
            {
                builder.Append(' ');
                space = true;
            }
        }
        return builder.ToString().Trim();
    }

}
