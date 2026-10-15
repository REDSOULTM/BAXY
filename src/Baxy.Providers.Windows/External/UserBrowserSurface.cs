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
internal sealed partial class UserBrowserSurface : IUserBrowserWindowLocator
{
    internal const string NavigationUnconfirmed = "user_browser_navigation_unconfirmed";
    internal const string PlaybackUnconfirmed = "user_browser_playback_unconfirmed";
    internal const string StreamingPlaybackUnconfirmed = "user_browser_streaming_playback_unconfirmed";
    internal const string StreamingProfileChoice = "user_browser_streaming_profile_choice";
    internal const string AddressAuthority = "user_browser_uia_address_postread";
    internal const string TitleAuthority = "user_browser_window_title_address";
    // Ronda 23 (t4-c10, t3-c06): a search engine's results page arrived as a window whose title changed after the link
    // was opened and names every word searched; the address field was stale (see SearchTitleArrives).
    internal const string SearchTitleAuthority = "user_browser_window_title_search";
    // Review r10a finding 6: the front window already showed the destination before the link was opened and no window
    // changed; the arrival is that page still on show, not a page seen to open (said «ya estaba abierta», never «Abrí»).
    internal const string AlreadyShownAuthority = "user_browser_front_already_showed";

    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(250);
    private const int NavigationPolls = 40;
    // Ronda 23: with the browser already running and no window of it changing title in this long (six seconds), the
    // link left no trace to wait on, and the navigation ends as unconfirmed instead of running out the horizon.
    internal const int QuietNavigationPolls = 24;
    private const int PlaybackPolls = 60;
    // Tanda t4-r6 «no po, en spotify»: a YouTube page that never played held the turn for the whole 15 s. Every
    // YouTube play verified in the 2026-10-08 tandas did so in 1.1-5.8 s; 8 s in which the running browser's media
    // sessions stay exactly as they were before the page was opened (no new session, no title or state change) is
    // the clear negative that ends the wait as unconfirmed. Any trace keeps the whole horizon.
    internal const int SilentPlaybackPolls = 32;
    // A playback that pays a start of its own before it can play gets 30 s. HBO Max took 12-15 s from its play control
    // to a playing session (Opera GX, 2026-10-06). A YouTube page in a browser this request launched: with Opera GX
    // closed (redpc tandas 2026-10-11/12), eleven first plays were verified 9-16.5 s after the link was opened and
    // three ran out the 15 s horizon (fin1 t2, fin4 t1, r29m t2) while the same page, browser up, played in 3 s.
    internal const int SlowStartPlaybackPolls = 120;
    private const int AddressReads = 3;
    // After a redirect of the same site, how long the destination itself may still arrive (about a second).
    private const int RedirectSettlePolls = 4;
    // When the front window already showed the destination, how long before its address is read again (two seconds).
    private const int SamePagePolls = 8;
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
        NavigationBaseline before = await BaselineAsync(browser, cancellationToken).ConfigureAwait(false);
        if (!TryOpen(target, effectBoundary, cancellationToken))
            return null;
        PageObservation seen = await ObserveNavigationAsync(
            browser, target, address => SameSite(target, address), before, cancellationToken).ConfigureAwait(false);
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
            writer.WriteString("authority", seen.Authority);
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
        NavigationBaseline before = await BaselineAsync(browser, cancellationToken).ConfigureAwait(false);
        if (!TryOpen(target, effectBoundary, cancellationToken))
            return null;
        Func<Uri, bool> ofService = address => SameSite(target, address)
            || WebBrowserAdapter.HostMatchesService(address.Host, service);
        PageObservation seen = await ObserveNavigationAsync(browser, target, ofService, before, cancellationToken)
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
            writer.WriteString("authority", seen.Authority);
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
        // A browser that is not running yet has a launch of its own to pay before any page plays.
        bool browserRunning = _platform.ListWindows(browser.ProcessName).Count > 0;
        if (!TryOpen(video.WatchUri, effectBoundary, cancellationToken))
            return null;
        // Ronda 19 (t1-c01 «ponme algo de los prisioneros», Opera closed): a browser this request launched has no
        // session of its own before the page, so whatever session it shows now is the page's, whatever its title.
        UserMediaSession? playing = await AwaitPlaybackAsync(
            browser, video.Title, before, browserRunning ? PlaybackPolls : SlowStartPlaybackPolls, cancellationToken,
            silentPollsLimit: browserRunning ? SilentPlaybackPolls : null,
            coldLaunch: !browserRunning).ConfigureAwait(false);
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
        NavigationBaseline windowsBefore = await BaselineAsync(browser, cancellationToken).ConfigureAwait(false);
        if (!TryOpen(search.Address, effectBoundary, cancellationToken))
            return null;
        Func<Uri, bool> ofService = address => SameSite(search.Address, address)
            || WebBrowserAdapter.HostMatchesService(address.Host, service);
        PageObservation seen = await ObserveNavigationAsync(
                browser, search.Address, ofService, windowsBefore, cancellationToken)
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
            browser, title, sessionsBefore, SlowStartPlaybackPolls, cancellationToken, anyNewBrowserSession: true)
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
        UserBrowserFrame? frame = await ReadFrameAsync(window.Handle, cancellationToken).ConfigureAwait(false);
        IReadOnlyList<UserBrowserTab> tabs = frame?.Tabs ?? [];
        if (tabs.Count == 0)
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

    /// <summary>
    /// The front window of the person's default browser for a computer-use mission on «the browser»: their browser
    /// whatever BAXY_BROWSER says, since the mission acts on what the person sees.
    /// </summary>
    public nint FrontWindow() =>
        _platform.ResolveDefault() is { } browser && FrontWindow(browser) is { } window ? window.Handle : 0;

    /// <summary>The browser window the person sees on top (windows come in z-order), if the browser runs at all.</summary>
    private UserBrowserWindow? FrontWindow(UserBrowserIdentity browser)
    {
        IReadOnlyList<UserBrowserWindow> windows = _platform.ListWindows(browser.ProcessName);
        return windows.Count > 0 ? windows[0] : null;
    }

    /// <summary>
    /// Ronda 23 (t4-c10, t3-c06): the destination is a known search engine's results page
    /// (src/baxy_mind/data/search_addresses.v1.json) and the window title, which changed after the link was opened (the
    /// caller passes only changed windows), is that results page: its page part (the title without the browser's own
    /// trailing segment) has the engine's label after a first segment that is, folded, exactly the text searched.
    /// Revisión 1 r24u (bloqueante 2): the words were looked for in the whole title, so «busca opera en google» arrived
    /// by «www.google.com - Opera» (the browser's segment named the word) and a video of another window that named the
    /// words arrived too. The browser's segment is <paramref name="browserSegment"/>, learned from the titles before
    /// the link (<see cref="BrowserTitleSegment"/>); with none learned the last segment is taken for it.
    /// </summary>
    internal static bool SearchTitleArrives(
        Uri target, string? title, string? browserSegment = null, IReadOnlyList<SearchAddress>? engines = null)
    {
        if (string.IsNullOrWhiteSpace(title) || SearchAddresses.SearchedText(target, engines) is not { } searched)
            return false;
        string asked = Fold(searched);
        if (asked.Length == 0)
            return false;
        List<string> segments = TitleSegments(title);
        if (segments.Count > 0 && (browserSegment is null || Fold(segments[^1]) == Fold(browserSegment)))
            segments.RemoveAt(segments.Count - 1);
        // The results page is the text searched and the engine's label: a bare first segment (an address, an error or
        // a page named by the words alone) is no results page.
        return segments.Count >= 2 && Fold(segments[0]) == asked;
    }

    private static readonly string[] TitleSeparators = [" - ", " – ", " — ", " | "];

    internal static List<string> TitleSegments(string title) =>
        [.. title.Split(TitleSeparators, StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)];

    /// <summary>
    /// Revisión 1 r24u: the browser's own trailing title segment («… - Opera», «… - Microsoft Edge»), read from the
    /// titles its windows had before the link: the last segment every such title of two segments or more shares. Null
    /// when no title had one or they disagree (never an application name written here).
    /// </summary>
    internal static string? BrowserTitleSegment(IEnumerable<string> titlesBefore)
    {
        string? shared = null;
        foreach (string title in titlesBefore)
        {
            List<string> segments = TitleSegments(title ?? string.Empty);
            if (segments.Count < 2)
                continue;
            if (shared is null)
                shared = segments[^1];
            else if (Fold(shared) != Fold(segments[^1]))
                return null;
        }
        return shared;
    }

    private readonly record struct PageObservation(Uri? Address, nint Window, string Authority = AddressAuthority);

    /// <summary>
    /// The address a window title names: the browser titles its window «&lt;tab title&gt; - &lt;browser&gt;», and a tab
    /// still loading (or with no title of its own) is titled with its address without the scheme. Null when the
    /// tab title is not an address.
    /// </summary>
    internal static Uri? TitleAddress(string? title)
    {
        if (string.IsNullOrWhiteSpace(title))
            return null;
        int suffix = title.LastIndexOf(" - ", StringComparison.Ordinal);
        string tab = suffix > 0 ? title[..suffix] : title;
        return tab.Contains('/', StringComparison.Ordinal) && TryAddress(tab, out Uri? address) ? address : null;
    }

    /// <summary>
    /// The browser before the link is opened: the title of each window and the address field of the front one, where
    /// the browser opens a link in a new tab. <paramref name="FrontAddress"/> is null when that field held no address:
    /// a new tab or the browser's start page leaves it empty (the read skips an empty field, as it skips Opera GX's
    /// empty <c>AddressBarViewGx</c>), so no page of any site was on show there.
    /// </summary>
    private sealed record NavigationBaseline(Dictionary<nint, string> Titles, nint Front, string? FrontAddress)
    {
        /// <summary>
        /// The address could only have come from the link just opened: its window is new, or it is the front window
        /// and its address field showed something else before (no address at all on a new tab or start page).
        /// Another window's earlier address is unknown, so an address there that is not the destination itself is
        /// never taken for the arrival.
        /// </summary>
        internal bool Fresh(nint window, Uri observed)
        {
            if (!Titles.ContainsKey(window))
                return true;
            if (window != Front)
                return false;
            return !(TryAddress(FrontAddress, out Uri? earlier) && SameAddress(earlier, observed));
        }
    }

    private async ValueTask<NavigationBaseline> BaselineAsync(
        UserBrowserIdentity browser, CancellationToken cancellationToken)
    {
        IReadOnlyList<UserBrowserWindow> windows = _platform.ListWindows(browser.ProcessName);
        Dictionary<nint, string> titles = windows
            .GroupBy(window => window.Handle)
            .ToDictionary(group => group.Key, group => group.First().Title);
        if (windows.Count == 0)
            return new(titles, nint.Zero, null);
        nint front = windows[0].Handle;
        string? address = await _platform.ReadAddressAsync(front, cancellationToken).ConfigureAwait(false);
        return new(titles, front, string.IsNullOrWhiteSpace(address) ? null : address.Trim());
    }

    /// <summary>
    /// After the link is opened, a window of the person's browser changes (a new tab is active, or a new window
    /// appears). Its address field is read and the navigation arrives when the address is the destination asked for
    /// (<see cref="ReachedTarget"/>). An address of the same site (for a streaming service, any of its hosts) that is
    /// not the destination counts only as a redirect of this link: fresh in that window (see
    /// <see cref="NavigationBaseline.Fresh"/>) and not the same page with another query. A redirect waits a moment for
    /// the destination itself (a consent page that gives way to the results) and is then reported as where the link
    /// landed. Any other address —another site, or a tab the person already had— is never reported, and with no
    /// address that qualifies the navigation stays unconfirmed.
    /// Semilla r8 («ok pero lo puedes buscar en google…» after that same search was opened): when the front window
    /// already showed the destination, the tab the link opens carries the same title, so no window changes and the
    /// wait used to end unconfirmed after ten seconds. Then the front window's address is read again after a moment:
    /// the destination there is what the person sees, and the navigation arrives.
    /// </summary>
    private async ValueTask<PageObservation> ObserveNavigationAsync(
        UserBrowserIdentity browser,
        Uri target,
        Func<Uri, bool> ofSite,
        NavigationBaseline before,
        CancellationToken cancellationToken)
    {
        bool alreadyShown = TryAddress(before.FrontAddress, out Uri? shown) && ReachedTarget(target, shown);
        int reads = 0;
        var readTitles = new Dictionary<nint, string>();
        PageObservation redirect = new(null, nint.Zero);
        int redirectUntil = NavigationPolls;
        // Semilla r8: an address read takes one to two seconds; the titles keep being polled while it runs, so the
        // moment a loading tab is titled with its address is not lost behind the read.
        Task<string?>? pending = null;
        nint pendingWindow = nint.Zero;
        int attempt = 0;
        bool clue = false;
        string? browserSegment = BrowserTitleSegment(before.Titles.Values);

        // The address read of a window: the arrival when it is the destination; a fresh address of the same site
        // is kept as a redirect.
        PageObservation? Arrived(string? text, nint window)
        {
            if (!TryAddress(text, out Uri? observed))
                return null;
            if (ReachedTarget(target, observed))
                return new(observed, window);
            if (ofSite(observed) && !ContradictsTarget(target, observed) && before.Fresh(window, observed))
            {
                if (redirect.Address is null)
                    redirectUntil = attempt + RedirectSettlePolls;
                redirect = new(observed, window);
            }
            return null;
        }

        for (; attempt < NavigationPolls && attempt <= redirectUntil && (reads < AddressReads || pending is not null);
            attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            List<UserBrowserWindow> changed = _platform.ListWindows(browser.ProcessName)
                .Where(window => !before.Titles.TryGetValue(window.Handle, out string? title)
                    || !string.Equals(title, window.Title, StringComparison.Ordinal))
                .ToList();
            foreach (UserBrowserWindow window in changed)
            {
                // Semilla r8: Opera GX's address field kept the previous tab's address for minutes while the window
                // title already named the new search. A tab still loading is titled with its own address: that
                // title, when it is the destination, is the arrival, read without UI Automation.
                if (TitleAddress(window.Title) is { } titled && ReachedTarget(target, titled))
                    return new(titled, window.Handle, TitleAuthority);
                // Ronda 23: a browser that titles a results page with the words searched while its address field keeps
                // the old address; a changed title that names every word searched is the asked results page.
                if (SearchTitleArrives(target, window.Title, browserSegment))
                    return new(target, window.Handle, SearchTitleAuthority);
            }
            if (changed.Count > 0)
                clue = true;
            if (!clue && pending is null && !alreadyShown && before.Titles.Count > 0
                && attempt + 1 >= QuietNavigationPolls)
                break;
            if (pending is { IsCompleted: true })
            {
                string? text = await pending.ConfigureAwait(false);
                pending = null;
                if (Arrived(text, pendingWindow) is { } arrival)
                    return arrival;
            }
            foreach (UserBrowserWindow window in changed)
            {
                if (pending is not null || reads >= AddressReads)
                    break;
                // A window is read again only once its title moved on: an address
                // field read while the new tab was still being built says nothing.
                if (readTitles.TryGetValue(window.Handle, out string? read)
                    && string.Equals(read, window.Title, StringComparison.Ordinal))
                    continue;
                readTitles[window.Handle] = window.Title;
                reads++;
                Task<string?> started = _platform.ReadAddressAsync(window.Handle, cancellationToken).AsTask();
                if (!started.IsCompleted)
                {
                    pending = started;
                    pendingWindow = window.Handle;
                    break;
                }
                if (Arrived(await started.ConfigureAwait(false), window.Handle) is { } arrival)
                    return arrival;
            }
            if (alreadyShown && attempt + 1 == SamePagePolls && redirect.Address is null)
            {
                alreadyShown = false;
                if (await FrontShowsAsync(browser, target, cancellationToken).ConfigureAwait(false) is { } front)
                    return front;
            }
        }
        if (alreadyShown && redirect.Address is null
            && await FrontShowsAsync(browser, target, cancellationToken).ConfigureAwait(false) is { } last)
            return last;
        return redirect;
    }

    /// <summary>
    /// The front window, when its address field shows the destination asked for. Only called when it showed it before
    /// the link: its authority says so (<see cref="AlreadyShownAuthority"/>).
    /// </summary>
    private async ValueTask<PageObservation?> FrontShowsAsync(
        UserBrowserIdentity browser, Uri target, CancellationToken cancellationToken)
    {
        if (FrontWindow(browser) is not { } front)
            return null;
        string? text = await _platform.ReadAddressAsync(front.Handle, cancellationToken).ConfigureAwait(false);
        return TryAddress(text, out Uri? observed) && ReachedTarget(target, observed)
            ? new PageObservation(observed, front.Handle, AlreadyShownAuthority)
            : null;
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
        bool anyNewBrowserSession = false,
        int? silentPollsLimit = null,
        bool coldLaunch = false)
    {
        int notPlaying = 0;
        bool nudged = false;
        bool traced = false;
        for (int attempt = 0; attempt < polls; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            IReadOnlyList<UserMediaSession> sessions = await _platform.ReadMediaSessionsAsync(cancellationToken)
                .ConfigureAwait(false);
            traced |= !BrowserSessionsUnchanged(browser, before, sessions);
            UserMediaSession? candidate = PlaybackCandidate(
                browser, expectedTitle, before, sessions, anyNewBrowserSession, coldLaunch);
            if (candidate is null)
            {
                if (!traced && attempt + 1 >= silentPollsLimit)
                    return null;
                continue;
            }
            if (candidate.PlaybackStatus == "playing")
                return candidate;
            // The page loaded the video but the browser held autoplay back: the
            // session's own play control is what a person would press. Only a
            // session that carries the asked title is pressed, never another one
            // the person had paused (or, in a browser this request launched, a session that was not there before).
            if (++notPlaying >= PausedPollsBeforePlay && !nudged
                && MayPressPlay(browser, expectedTitle, before, candidate, coldLaunch)
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
        bool anyNewBrowserSession,
        bool coldLaunch = false)
    {
        // A browser this request launched had no page of the person's playing: any session of it that was not there
        // before is the page's, as for a service whose session title is not the title asked for.
        anyNewBrowserSession |= coldLaunch;
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
    /// Whether the held-back session may get the one press of its own play control: it carries the title asked for,
    /// or the browser was launched by this request and the session is one of the browser's that was not there before
    /// (title and state). A session the person already had, paused, is never pressed.
    /// </summary>
    internal static bool MayPressPlay(
        UserBrowserIdentity browser,
        string expectedTitle,
        IReadOnlyList<UserMediaSession> before,
        UserMediaSession candidate,
        bool coldLaunch) =>
        TitlesMatch(candidate.Title, expectedTitle)
        || (coldLaunch && browser.OwnsMediaSession(candidate.SourceAppUserModelId) && !AlreadyThere(candidate, before));

    /// <summary>
    /// The person's browser shows exactly the media sessions it showed before the page was opened: the same
    /// sessions, titles and states, none added and none gone. Sessions of other applications do not count.
    /// </summary>
    internal static bool BrowserSessionsUnchanged(
        UserBrowserIdentity browser,
        IReadOnlyList<UserMediaSession> before,
        IReadOnlyList<UserMediaSession> sessions)
    {
        static string Key(UserMediaSession session) =>
            session.SourceAppUserModelId + "\u001f" + session.Title + "\u001f" + session.PlaybackStatus;
        string[] earlier = before.Where(session => browser.OwnsMediaSession(session.SourceAppUserModelId))
            .Select(Key).Order(StringComparer.Ordinal).ToArray();
        string[] now = sessions.Where(session => browser.OwnsMediaSession(session.SourceAppUserModelId))
            .Select(Key).Order(StringComparer.Ordinal).ToArray();
        return earlier.SequenceEqual(now, StringComparer.Ordinal);
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
