using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

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
internal sealed partial class UserBrowserSurface
{
    internal const string MediaSessionsNotRead = "media_sessions_not_read_before";
    internal const string NavigationUnconfirmed = "user_browser_navigation_unconfirmed";
    internal const string PlaybackUnconfirmed = "user_browser_playback_unconfirmed";
    internal const string StreamingPlaybackUnconfirmed = "user_browser_streaming_playback_unconfirmed";
    internal const string StreamingProfileChoice = "user_browser_streaming_profile_choice";
    internal const string StreamingTitleNotFound = "streaming_title_not_found";
    internal const string StreamingOtherTitlePlaying = "streaming_other_title_playing";
    internal const string AddressAuthority = "user_browser_uia_address_postread";
    internal const string TitleAuthority = "user_browser_window_title_address";
    // Ronda 23 (t4-c10, t3-c06): a search engine's results page arrived as a window whose title changed after the link
    // was opened and names every word searched; the address field was stale (see SearchTitleArrives).
    internal const string SearchTitleAuthority = "user_browser_window_title_search";
    // Review r10a finding 6: the front window already showed the destination before the link was opened and no window
    // changed; the arrival is that page still on show, not a page seen to open (said «ya estaba abierta», never «Abrí»).
    internal const string AlreadyShownAuthority = "user_browser_front_already_showed";

    // Ronda final: the front showed the page before the link and still does: what is seen is the state from before,
    // not a navigation; the link was sent (a tab may have opened) and nothing read what it did.
    private static void WriteAlreadyShown(Utf8JsonWriter writer, PageObservation seen)
    {
        if (seen.Authority != AlreadyShownAuthority)
            return;
        writer.WriteBoolean("alreadyShown", true);
        writer.WriteBoolean("effectReadBack", false);
    }

    // Noche r7 (pre-web-comprobar): what an unconfirmed navigation's address field showed after the link (addressSeen),
    // so the result says what was checked and why it was not enough, never the address itself.
    internal const string AddressNotRead = "not_read";
    internal const string Unreadable = "unreadable";
    internal const string NoAddress = "no_address";
    internal const string PageFromBefore = "page_from_before";
    internal const string OtherPage = "other_page";
    internal const string SameSiteNotKnownNew = "same_site_not_known_new";

    /// <summary>
    /// Decisión del dueño (noche, pre-web-comprobar): an unconfirmed navigation says what was checked: the link was
    /// handed to the browser, whether a window of it changed after that, and what its address field showed
    /// (<see cref="PageObservation.Seen"/>). No address read from a tab is written: it may be another page of the person's.
    /// Uso real 2026-11-02: it read as «may or may not have happened» and the same link was opened six times; it says
    /// too what another call with it does and how the page is seen.
    /// </summary>
    private static ExternalCapabilityReceipt Unconfirmed(
        string operation, UserBrowserIdentity browser, Uri target, PageObservation seen) =>
        ExternalJson.FailureAfterEffect(operation, NavigationUnconfirmed) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("requestedUrl", target.AbsoluteUri);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteBoolean("linkSent", true);
                writer.WriteBoolean("windowChanged", seen.Changed);
                writer.WriteString("addressSeen", seen.Seen);
                // Encargo 34: the read of what it shows comes first, as the call the model makes.
                writer.WriteString("next", $"{Baxy.Kernel.Operations.WireNames.Call("browser.page.read", new())} reads "
                    + "what the browser shows now (input_visible_controls on its window sees it too); the link is out and "
                    + "BAXY no longer waits for it, and a call with it again hands it to " + browser.DisplayName + " again");
                writer.WriteEndObject();
            }),
        };

    internal const string BrowserWindowNotSeen = "user_browser_window_not_seen";

    // Banco de entorno del NB (2026-11-03, U06 and R17): a browser that was not running and shows no window of its own this
    // long after the link was handed over never started for it. Windows hands a link to the program its https association
    // names, and when that choice no longer holds it asks which app opens it instead («How do you want to open this?»:
    // Microsoft, «Default apps» and the UserChoice protection of Windows 11), so the shell's success says nothing about
    // the browser. Fifteen seconds: every cold launch measured here showed its page well before (Edge 2-4 s, encargo 43;
    // Opera GX played 9-16.5 s after the link, ronda 19, with its window up before that).
    internal const int AppearPolls = 60;

    /// <summary>
    /// The browser the link was handed to showed no window within <see cref="AppearPolls"/>: nothing was seen to open, so
    /// no address is told as opened. Its next leads with <paramref name="retry"/>, the same call made through the
    /// browser's own program (which does not go through Windows' association), when the catalog has one for it.
    /// </summary>
    private static ExternalCapabilityReceipt WindowNotSeen(
        string operation, UserBrowserIdentity browser, Uri target, bool throughShell, string? retry) =>
        ExternalJson.FailureAfterEffect(operation, BrowserWindowNotSeen) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("requestedUrl", target.AbsoluteUri);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteBoolean("linkSent", true);
                writer.WriteBoolean("browserWindowSeen", false);
                int seconds = (int)(Poll.TotalSeconds * AppearPolls);
                string unseen = throughShell
                    ? $"no window of {browser.DisplayName} appeared within {seconds} seconds of handing the link to "
                        + "Windows, so nothing was seen to open (Windows may be asking which app opens web links)"
                    : $"no window of {browser.DisplayName} appeared within {seconds} seconds of starting its program "
                        + "with the link, so nothing was seen to open";
                writer.WriteString("next", retry is null
                    ? unseen
                    : $"{retry} opens it with {browser.DisplayName}'s own program, without Windows' web-link "
                        + "association; " + unseen);
                writer.WriteEndObject();
            }),
        };

    // Whether a window of the browser is up, or comes up within AppearPolls.
    private async ValueTask<bool> AppearedAsync(UserBrowserIdentity browser, CancellationToken cancellationToken)
    {
        for (int poll = 0; ; poll++)
        {
            if (_platform.ListWindows(browser.ProcessName).Count > 0)
                return true;
            if (poll >= AppearPolls)
                return false;
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
        }
    }

    // The catalog's call that opens the page through a named browser's own program, when that browser is one it names.
    private static string? NamedCall(string operation, string family, System.Text.Json.Nodes.JsonObject arguments) =>
        Baxy.Kernel.Operations.ProductCatalog.GetRequired(operation).ArgumentsSchema.Properties
            .FirstOrDefault(static property => property.Name == "browser") is { } named
            && named.AllowedValues.Contains(family, StringComparer.Ordinal)
                ? Baxy.Kernel.Operations.WireNames.Call(operation, arguments)
                : null;

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
    // closed (development PC tandas 2026-10-11/12), eleven first plays were verified 9-16.5 s after the link was opened and
    // three ran out the 15 s horizon (fin1 t2, fin4 t1, r29m t2) while the same page, browser up, played in 3 s.
    internal const int SlowStartPlaybackPolls = 120;
    private const int AddressReads = 3;
    // After a redirect of the same site, how long the destination itself may still arrive (about a second).
    private const int RedirectSettlePolls = 4;
    // Noche r7 (R7-NB-5): when the address field of a window whose title moved on still shows the page from before the
    // link, how long before it is read once more although the title does not move (two seconds). That one read is
    // outside the AddressReads budget, so the title changes after it are still read and waited for.
    private const int StaleRereadPolls = 8;
    // A baseline read that failed this fast (not one that ran out its time) is tried once more.
    private static readonly TimeSpan BaselineRetryWithin = TimeSpan.FromSeconds(3);
    // When the front window already showed the destination, how long before its address is read again (two seconds).
    private const int SamePagePolls = 8;
    private const int PausedPollsBeforePlay = 8;
    // Encargo 43 (U06, 11 of 11 runs): a browser that holds a page's autoplay back (no gesture of the person on that
    // site yet) shows no media session at all, so there is no session to press. With no trace of it two seconds after
    // the link, the page's own play control is pressed, once; the page may still be loading, so a press that found no
    // page or no control is tried again after twice as long (2, 4, 8, 16 s). Measured live on Edge, closed before:
    // YouTube's page was up in 2-4 s, and the session played 6.7 s after the press (an advertisement first).
    internal const int PagePlayPolls = 8;

    internal const string PageNotFound = "page_not_found";
    internal const string PageHostNotFound = "page_host_not_found";
    internal const string PageRequiresSignIn = "page_requires_sign_in";
    // How long the status of the page that arrived is waited for before the navigation is told without it.
    private static readonly TimeSpan PageStatusWithin = TimeSpan.FromSeconds(4);

    private readonly IUserBrowserPlatform _platform;
    private readonly Func<string, string?> _environment;
    private readonly Func<Uri, CancellationToken, Task<SearchPageReader.PageStatus?>>? _pageStatus;

    internal UserBrowserSurface(
        IUserBrowserPlatform platform,
        Func<string, string?>? environment = null,
        Func<Uri, CancellationToken, Task<SearchPageReader.PageStatus?>>? pageStatus = null)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _environment = environment ?? Environment.GetEnvironmentVariable;
        _pageStatus = pageStatus;
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

    /// <summary>
    /// Feria 2026-10-27 (caso 19): the person's install of the browser a call named, whatever the default one is; null
    /// when Windows has none of that family registered. Throws when the registry cannot be read.
    /// </summary>
    internal UserBrowserIdentity? ResolveNamed(string family) => _platform.ResolveRegistered(family);

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
        if (before.Titles.Count == 0 && !await AppearedAsync(browser, cancellationToken).ConfigureAwait(false))
            return WindowNotSeen(operation, browser, target, throughShell: true, NamedCall(
                "browser.navigate.named", browser.Family, new() { ["browser"] = browser.Family, ["url"] = target.AbsoluteUri }));
        PageObservation seen = await ObserveNavigationAsync(
            browser, target, address => SameSite(target, address), before, cancellationToken).ConfigureAwait(false);
        if (seen.Address is null)
            return Unconfirmed(operation, browser, target, seen);
        // Uso real (Opera GX behind Spotify): the shell opened the tab, but this background process had no right to hand
        // the front over, so the page stayed behind and the text typed next went to the window in front. The page the
        // person asked to see is put in front, as a click on a link does.
        if (seen.Window != 0)
            _ = await _platform.BringToFrontAsync(seen.Window, cancellationToken).ConfigureAwait(false);
        string? pageTitle = await PageTitleAsync(browser, seen.Window, BrowserTitleSegment(before.Titles.Values),
            cancellationToken).ConfigureAwait(false);
        Uri asked = StatusAddress(target, seen.Address);
        SearchPageReader.PageStatus? status = await PageStatusAsync(asked, cancellationToken).ConfigureAwait(false);
        if (status is { HostNotFound: true })
            return HostNotFound(operation, browser, target, asked, pageTitle);
        if (status?.Code is (404 or 410) and int gone)
            return NotFound(operation, browser, target, seen.Address, pageTitle, gone);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedUrl", target.AbsoluteUri);
            writer.WriteString("finalUrl", seen.Address.AbsoluteUri);
            if (pageTitle is not null)
                writer.WriteString("pageTitle", pageTitle);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("browserFamily", browser.Family);
            writer.WriteString("authority", seen.Authority);
            WriteAlreadyShown(writer, seen);
            if (SearchNotDone(operation, browser, target) is { } search)
                writer.WriteString("next", search);
            writer.WriteEndObject();
        }));
    }

    // Uso-111 (N2, «abre el navegador y busca el clima»: the model opened a site's front page or a guessed one and said it
    // had looked, with nothing searched). An address with no query of its own searched nothing, whatever the person asked:
    // what they asked is the model's to read. Measured with the real model (held-out, 2 seeds): the search opened 2/21 with
    // no next, 5/18 with the fact first, 10/20 with the request first, as encargo 82 measured; 14/14 controls that asked
    // only for a site did not search.
    internal static string? SearchNotDone(string operation, UserBrowserIdentity browser, Uri target)
    {
        if (target.Query.Length > 0 || target.Fragment.Length > 0)
            return null;
        var arguments = new System.Text.Json.Nodes.JsonObject();
        if (operation == "browser.navigate.named")
            arguments["browser"] = browser.Family;
        arguments["url"] = "https://duckduckgo.com/?q=their+words";
        return "If the person asked to search for something, that is not done yet: only this page opened and nothing was "
            + $"searched on it; call {Baxy.Kernel.Operations.WireNames.Call(operation, arguments)} to open that search";
    }

    // Encargo 35 (bancos ab-d4-1d y uso-8ded, U31: a made-up address of a documentation site gave its «Page not
    // found» and was told as a navigation completed and verified; the model said the page did not exist and never
    // looked for the real one, 0 of 19 times). The address arrived, so the page did open (an effect), but the site
    // answered that it does not exist: the navigation fails, and its next leads with the search that finds the page's
    // real address, made of the failed address's own site and words (followed 15 of 15 times by the real model).
    private static ExternalCapabilityReceipt NotFound(
        string operation, UserBrowserIdentity browser, Uri target, Uri arrived, string? pageTitle, int status) =>
        ExternalJson.FailureAfterEffect(operation, PageNotFound, effectObserved: true) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("requestedUrl", target.AbsoluteUri);
                writer.WriteString("finalUrl", arrived.AbsoluteUri);
                if (pageTitle is not null)
                    writer.WriteString("pageTitle", pageTitle);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteString("browserFamily", browser.Family);
                writer.WriteNumber("httpStatus", status);
                string search = Baxy.Kernel.Operations.WireNames.Call(
                    "web.search", new() { ["query"] = AddressWords(arrived) });
                writer.WriteString("next", $"{search} finds the page's real address; the page this address shows does "
                    + $"not exist: its site answered {(status == 404 ? "404 Not Found" : "410 Gone")}");
                writer.WriteEndObject();
            }),
        };

    // Encargo 70 (uso real 03-11, F7: a site named without its address, the model wrote a guessed one whose host name does
    // not exist; the browser showed its own error page, titled with that host, and the navigation was told completed and
    // verified, then «Listo, abrí…»). The address field did show the address (the browser opened it: an effect), but no
    // site answers there: the navigation fails, and its next leads with the search that finds the site's real address,
    // written as the call (encargo 34: a next that starts with the call and its arguments is the one the model follows).
    // arrived: the address whose status was asked (StatusAddress), on the host the call wrote.
    private static ExternalCapabilityReceipt HostNotFound(
        string operation, UserBrowserIdentity browser, Uri target, Uri arrived, string? pageTitle) =>
        ExternalJson.FailureAfterEffect(operation, PageHostNotFound, effectObserved: true) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("requestedUrl", target.AbsoluteUri);
                writer.WriteString("finalUrl", arrived.AbsoluteUri);
                if (pageTitle is not null)
                    writer.WriteString("pageTitle", pageTitle);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteString("browserFamily", browser.Family);
                writer.WriteBoolean("hostResolved", false);
                // Encargo 82 (vivo del 81, 0 of 2; banco de decisiones, held-out): with the search written first the model
                // told the fact and stopped (4/30, rival p 0.000), with or without effectUncertain or a better query; only
                // saying what the person asked is not done moved it (30/30, and the 15/15 that asked for that address alone
                // kept to it). As encargo 61 measured: the call does not lead here, the request does.
                string search = Baxy.Kernel.Operations.WireNames.Call(
                    "web.search", new() { ["query"] = SiteWords(arrived) });
                writer.WriteString("next", "the person asked to open this site and it is not open: no site answers at "
                    + $"this address: its host name {arrived.IdnHost} does not resolve (DNS), so the page "
                    + $"{browser.DisplayName} shows is its own error page; call {search} to find its real address");
                writer.WriteEndObject();
            }),
        };

    // Encargo 58 (diagnóstico f11dcfa99, U06 4 of 6): YouTube showed, over the video, its dialog «Sign in to confirm
    // you’re not a bot» (playabilityStatus.errorScreen's reason, the text yt-dlp reports), and the call said only
    // «unconfirmed»; the model clicked into the sign-in page for up to 13 steps. The page opened (an effect) and nothing
    // plays until the person signs in, which is theirs: the dialog's own text and link are the fact.
    private static ExternalCapabilityReceipt SignInRequired(
        string operation, UserBrowserIdentity browser, Uri opened, (UserBrowserDialog Dialog, UserBrowserLink Link) wall) =>
        ExternalJson.FailureAfterEffect(operation, PageRequiresSignIn, effectObserved: true) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("openedUrl", opened.AbsoluteUri);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteString("pageDialog", wall.Dialog.Name);
                writer.WriteString("signInLink", wall.Link.Name);
                writer.WriteString("next", $"nothing played: the page opened shows its own dialog «{wall.Dialog.Name}» "
                    + $"over the video, and its link «{wall.Link.Name}» goes to a sign-in page; signing in is the "
                    + "person's own step, with their account, and until then a click in that dialog or this call again "
                    + "plays nothing");
                writer.WriteEndObject();
            }),
        };

    // The first link of a page's dialog whose address is a sign-in page (AsksToSignIn: its path is a login one).
    internal static (UserBrowserDialog Dialog, UserBrowserLink Link)? SignInDialog(IReadOnlyList<UserBrowserDialog>? dialogs)
    {
        foreach (UserBrowserDialog dialog in dialogs ?? [])
        {
            foreach (UserBrowserLink link in dialog.Links)
            {
                if (Uri.TryCreate(link.Address, UriKind.Absolute, out Uri? address)
                    && address.Scheme is "http" or "https" && AsksToSignIn(address))
                    return (dialog, link);
            }
        }

        return null;
    }

    // What the page's play step saw of a dialog that asks to sign in, kept for the failure that ends the wait.
    private sealed class SignInSeen
    {
        internal (UserBrowserDialog Dialog, UserBrowserLink Link)? Dialog { get; set; }
    }

    // The site and the words of an address's path, as a search is written: «docs.ejemplo.org guia entornos» for
    // https://docs.ejemplo.org/3/guia/entornos.html (no «www.», no extension, no segment that is only a number).
    internal static string AddressWords(Uri address)
    {
        string host = address.Host.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? address.Host[4..] : address.Host;
        IEnumerable<string> words = address.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries)
            .Select(static segment => Path.GetFileNameWithoutExtension(Uri.UnescapeDataString(segment))
                .Replace('-', ' ').Replace('_', ' ').Trim())
            .Where(static segment => segment.Length > 0 && !segment.All(char.IsDigit));
        return string.Join(' ', words.Prepend(host));
    }

    // Encargo 82: the words of a site whose host name does not exist, what a search can find it by: its name without
    // «www.» and the ending of its domain, in words («tienda-del-sur.cl» is «tienda del sur»).
    internal static string SiteWords(Uri address)
    {
        string host = address.Host.StartsWith("www.", StringComparison.OrdinalIgnoreCase) ? address.Host[4..] : address.Host;
        int ending = host.LastIndexOf('.');
        string name = ending > 0 ? host[..ending] : host;
        return string.Join(' ', name.Split(['.', '-', '_'], StringSplitOptions.RemoveEmptyEntries));
    }

    // Encargo 70 (revisión): the address whose status is asked: the one that arrived, but on the host the call wrote when
    // the address field shows that host without «www.» (Chrome and Opera hide it): a site may publish only one of the two
    // names, and the one in question is the one the call wrote.
    internal static Uri StatusAddress(Uri target, Uri arrived) =>
        !string.Equals(target.Host, arrived.Host, StringComparison.OrdinalIgnoreCase)
            && string.Equals(BareHost(target.Host), BareHost(arrived.Host), StringComparison.Ordinal)
            ? new UriBuilder(arrived) { Host = target.Host }.Uri
            : arrived;

    // The status the page that arrived answers with (SearchPageReader.StatusAsync), waited for a short while; null when
    // there is no way to ask or no answer in time: the navigation is then told as before.
    private async ValueTask<SearchPageReader.PageStatus?> PageStatusAsync(Uri arrived, CancellationToken cancellationToken)
    {
        if (_pageStatus is null)
            return null;
        using var within = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        within.CancelAfter(PageStatusWithin);
        try
        {
            return await _pageStatus(arrived, within.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
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
        if (before.Titles.Count == 0 && !await AppearedAsync(browser, cancellationToken).ConfigureAwait(false))
            return WindowNotSeen(operation, browser, target, throughShell: true, retry: null);
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
            WriteAlreadyShown(writer, seen);
            writer.WriteEndObject();
        }));
    }

    internal async ValueTask<ExternalCapabilityReceipt?> PlayYouTubeAsync(
        string operation,
        UserBrowserIdentity browser,
        string query,
        YouTubeSearchResult video,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken,
        bool named = false)
    {
        IReadOnlyList<UserMediaSession>? read = await _platform.ReadMediaSessionsAsync(cancellationToken)
            .ConfigureAwait(false);
        // A browser that is not running yet has a launch of its own to pay before any page plays.
        bool browserRunning = _platform.ListWindows(browser.ProcessName).Count > 0;
        // Auditoría final (regla 3): with the sessions before the page not all read, an old session (another app's of
        // the same title, too) cannot be told from the new one, nor kept from being pressed, so nothing is opened.
        if (read is null)
            return ExternalJson.FailureBeforeEffect(operation, MediaSessionsNotRead);
        IReadOnlyList<UserMediaSession> before = read;
        if (!TryOpen(video.WatchUri, effectBoundary, cancellationToken, named ? browser : null))
            return null;
        if (!browserRunning && !await AppearedAsync(browser, cancellationToken).ConfigureAwait(false))
            return WindowNotSeen(operation, browser, video.WatchUri, throughShell: !named, named ? null : NamedCall(
                "media.play.youtube", browser.Family, new() { ["query"] = query, ["browser"] = browser.Family }));
        // Ronda 19 (t1-c01 «ponme algo de los prisioneros», Opera closed): a browser this request launched has no
        // session of its own before the page, so whatever session it shows now is the page's, whatever its title.
        var signIn = new SignInSeen();
        UserMediaSession? playing = await AwaitPlaybackAsync(
            browser, video.Title, before, browserRunning ? PlaybackPolls : SlowStartPlaybackPolls, cancellationToken,
            silentPollsLimit: browserRunning ? SilentPlaybackPolls : null,
            coldLaunch: !browserRunning, ownSessionsOnly: named, page: video.WatchUri, signIn: signIn)
            .ConfigureAwait(false);
        if (playing is null && signIn.Dialog is { } wall)
            return SignInRequired(operation, browser, video.WatchUri, wall);
        // Caso 19: the page was opened, so the failure says where, as a success does.
        if (playing is null)
            return ExternalJson.FailureAfterEffect(operation, PlaybackUnconfirmed) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteString("openedUrl", video.WatchUri.AbsoluteUri);
                    writer.WriteString("browser", browser.DisplayName);
                    writer.WriteEndObject();
                }),
            };
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "youtube");
            writer.WriteString("query", query);
            // Uso real 2026-10-21: no video of the first ones held every word searched; YouTube's first one played.
            if (!video.TitleMatchesQuery)
                writer.WriteBoolean("titleMatchesQuery", false);
            // Ronda final: what played as the session read it; the page BAXY opened is the opened one, not a read
            // address.
            if (playing.Title.Length > 0)
                writer.WriteString("title", playing.Title);
            else
                writer.WriteString("requestedTitle", video.Title);
            writer.WriteString("openedUrl", video.WatchUri.AbsoluteUri);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("sourceAppUserModelId", playing.SourceAppUserModelId);
            writer.WriteString("playbackStatus", "playing");
            // Ronda final 14 (regla 3): the system's media session says playing for an advertisement too, and the
            // person's page is not read here: an advertisement is not ruled out.
            writer.WriteBoolean("adRuledOut", false);
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
        IReadOnlyList<UserMediaSession>? sessionsRead = await _platform.ReadMediaSessionsAsync(cancellationToken)
            .ConfigureAwait(false);
        if (sessionsRead is null)
            return ExternalJson.FailureBeforeEffect(operation, MediaSessionsNotRead);
        IReadOnlyList<UserMediaSession> sessionsBefore = sessionsRead;
        NavigationBaseline windowsBefore = await BaselineAsync(browser, cancellationToken).ConfigureAwait(false);
        if (!TryOpen(search.Address, effectBoundary, cancellationToken))
            return null;
        if (windowsBefore.Titles.Count == 0 && !await AppearedAsync(browser, cancellationToken).ConfigureAwait(false))
            return WindowNotSeen(operation, browser, search.Address, throughShell: true, retry: null);
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
        // No card was named as the title: nothing was pressed, and the names the page showed go back as candidates.
        if (step.Step == "title")
            return StreamingTitleCandidates(operation, service, title, step.Seen ?? []);
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
        // Uso real 03-11: a session that started after the play control and names another title is what plays, never
        // the title asked for, whatever card was pressed.
        bool? matches = SessionNamesTitle(playing, landed, title, step.Chosen);
        if (matches == false)
            return ExternalJson.FailureAfterEffect(operation, StreamingOtherTitlePlaying, effectObserved: true) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("service", service);
                    writer.WriteString("requested", title);
                    WritePlaying(writer, playing, false);
                    writer.WriteString("browser", browser.DisplayName);
                    writer.WriteString("playbackStatus", playing.PlaybackStatus);
                    writer.WriteString("authority", "user_browser_smtc_postread");
                    writer.WriteEndObject();
                }),
            };
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("title", step.Chosen.Length > 0 ? step.Chosen : title);
            writer.WriteString("sessionTitle", playing.Title);
            if (matches == true)
                WritePlaying(writer, playing, true);
            writer.WriteString("browser", browser.DisplayName);
            writer.WriteString("sourceAppUserModelId", playing.SourceAppUserModelId);
            writer.WriteString("playbackStatus", "playing");
            // Ronda final 14 (regla 3): the system's media session says playing for an advertisement too, and the
            // person's page is not read here: an advertisement is not ruled out.
            writer.WriteBoolean("adRuledOut", false);
            writer.WriteString("authority", "user_browser_smtc_postread");
            writer.WriteEndObject();
        }));
    }

    /// <summary>
    /// Whether the session read names the title asked for, or the card pressed, by the two names a page hands the
    /// system (the Media Session API's title and artist; a series may come as the artist of its episode). Null when
    /// its title is empty or only the service's own name (Netflix's is «Netflix») and its artist does not name it:
    /// such a read tells nothing either way.
    /// </summary>
    internal static bool? SessionNamesTitle(UserMediaSession session, Uri page, string requested, string chosen)
    {
        bool Names(string name) =>
            TitlesMatch(name, requested) || (chosen.Length > 0 && TitlesMatch(name, chosen));
        if (Names(session.Title) || Names(session.Artist))
            return true;
        string[] labels = BareHost(page.Host).Split('.');
        string site = labels.Length >= 2 ? labels[^2] : labels[0];
        string named = Fold(session.Title).Replace(" ", string.Empty, StringComparison.Ordinal);
        return named.Length == 0 || (named.Length >= 3 && site.Contains(named, StringComparison.Ordinal))
            ? null : false;
    }

    // What the session read says plays, and whether it names the title asked for.
    private static void WritePlaying(Utf8JsonWriter writer, UserMediaSession playing, bool matches)
    {
        writer.WriteString("playingTitle", playing.Title);
        if (playing.Artist.Length > 0)
            writer.WriteString("playingArtist", playing.Artist);
        writer.WriteBoolean("titleMatchesRequest", matches);
    }

    private sealed record StreamingSearch(Uri Address, bool TypeTitle, string SignInCode);

    /// <summary>
    /// No card was named as the title, so nothing was pressed and nothing plays: the search page is all that opened.
    /// Uso real 02-11: said as «may have happened», the step read «puede haber corrido» for a title not found.
    /// </summary>
    internal static ExternalCapabilityReceipt StreamingTitleCandidates(
        string operation, string service, string title, IReadOnlyList<StreamingCard> seen) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("service", service);
            writer.WriteString("requested", title);
            // Each card as the page showed it; an episode says so, with its whole name, never as the title asked for.
            writer.WriteStartArray("candidates");
            foreach (StreamingCard card in seen)
            {
                writer.WriteStartObject();
                writer.WriteString("title", card.Title);
                if (card.Kind is not null)
                    writer.WriteString("kind", card.Kind);
                if (card.Label is not null)
                    writer.WriteString("label", card.Label);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }), StreamingTitleNotFound);

    /// <summary>
    /// A card the product browser's search knows only by its whole name: an episode when what it says besides the
    /// title asked for carries the service's episode mark (<see cref="UserBrowserScripts.EpisodeMark"/>).
    /// </summary>
    internal static StreamingCard CardOf(string name, string requested)
    {
        string rest = Fold(name);
        string asked = Fold(requested);
        int at = asked.Length == 0 ? -1 : rest.IndexOf(asked, StringComparison.Ordinal);
        if (at >= 0)
            rest = rest.Remove(at, asked.Length);
        return EpisodeMarked().IsMatch(rest) ? new StreamingCard(name, "episode") : new StreamingCard(name);
    }

    [GeneratedRegex(UserBrowserScripts.EpisodeMark, RegexOptions.CultureInvariant)]
    private static partial Regex EpisodeMarked();

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

    private bool TryOpen(
        Uri target, ExternalEffectBoundary effectBoundary, CancellationToken cancellationToken,
        UserBrowserIdentity? named = null)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            if (named is null)
                _platform.Open(target);
            else
                _platform.OpenWith(named, target);
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception
            or InvalidOperationException or FileNotFoundException or ArgumentException)
        {
            // Nothing was launched: the caller keeps the product browser as fallback, never for a browser a call named.
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

    /// <summary>The first Chrome and Edge whose pages and tabs UI Automation reads with no flag:
    /// https://developer.chrome.com/blog/windows-uia-support-update.</summary>
    private const int FirstNativeUiaVersion = 138;

    /// <summary>
    /// Uso-111 (G8, live in Chrome 136 on this PC: its window shows UI Automation no page and no tab strip): the failure says
    /// what still reads it, the look by its name, whose text comes from the screen, and when the browser is that old, what
    /// would let BAXY read it. Before, the model was told only the code and said it could not.
    /// </summary>
    internal static ExternalCapabilityReceipt PageNotShown(string operation, UserBrowserIdentity browser) =>
        ExternalJson.FailureBeforeEffect(operation, PageUnreadable) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("browser", browser.DisplayName);
                string look = Baxy.Kernel.Operations.WireNames.Call("input.visible.controls", new()
                {
                    ["application"] = browser.ProcessName,
                    ["includeText"] = true,
                });
                string why = $"{browser.DisplayName} did not show BAXY its page or its tabs";
                if (OlderThanNativeUia(browser) is int version)
                {
                    writer.WriteNumber("browserVersion", version);
                    why += $": its version {version} is older than {FirstNativeUiaVersion}, the first that shows them, and updating it would let BAXY read them";
                }
                writer.WriteString("next", $"{look} reads what its window shows on the screen; {why}");
                writer.WriteEndObject();
            }),
        };

    // The main version of a Chrome or Edge from before native UI Automation; null for any other browser or a version not read.
    private static int? OlderThanNativeUia(UserBrowserIdentity browser)
    {
        if (browser.Family is not ("chrome" or "edge") || !File.Exists(browser.Executable))
            return null;
        int major = System.Diagnostics.FileVersionInfo.GetVersionInfo(browser.Executable).FileMajorPart;
        return major is > 0 and < FirstNativeUiaVersion ? major : null;
    }

    /// <summary>
    /// Uso-111 (N2, «abre el navegador y busca…»: another browser opened, then the page read went to the default one and
    /// said only user_browser_not_running): which browser that is, and what opens it or reaches another one.
    /// </summary>
    internal static ExternalCapabilityReceipt NotRunning(string operation, UserBrowserIdentity browser) =>
        ExternalJson.FailureBeforeEffect(operation, BrowserNotRunning) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("browser", browser.DisplayName);
                writer.WriteString("next", $"{browser.DisplayName} has no window open, so nothing was read or done in it. If "
                    + $"the person wants a page there, {Baxy.Kernel.Operations.WireNames.Of("browser.navigate")} with its address "
                    + $"opens it; the window of another browser is reached with "
                    + $"{Baxy.Kernel.Operations.WireNames.Of("input.visible.controls")} with its name");
                writer.WriteEndObject();
            }),
        };

    /// <summary>
    /// Uso-108: a long page was read, the text cut, and asked to go on the model read the same page again and said «no hay más
    /// texto en la página», which is false (held-out, 3 seeds: 28 of 36, and the new text in 0 of 36; with this next, 1 of 36
    /// and 35 of 36, though two thirds of a read after a scroll were said already, and it went down in 0 of 30 where the person asked for nothing of the kind). Where the person asks about
    /// what is on screen it costs something: 2 of 24 went down and 4 read again. A field saying there was more moved nothing
    /// (hasMore: 0 of 19, a batch cut short); «if the person asks for more» gained nothing over this.
    /// </summary>
    internal static readonly string PageGoesOnBelow = "the page goes on below this text: "
        + Baxy.Kernel.Operations.WireNames.Call("browser.control", new System.Text.Json.Nodes.JsonObject { ["action"] = "scroll_down" })
        + " moves on to it";

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
        (UserBrowserWindow? window, _, _) = await TabbedWindowAsync(browser, cancellationToken).ConfigureAwait(false);
        if (window is null)
            return NotRunning(operation, browser);
        UserBrowserPageText? page = await _platform.ReadPageTextAsync(
            window.Handle, maximumCharacters, cancellationToken).ConfigureAwait(false);
        // FT/proveedores goal (E3): a heavy page may build its accessibility tree after the script's looks: read once more.
        if (page is null)
        {
            await _platform.DelayAsync(PageRetry, cancellationToken).ConfigureAwait(false);
            page = await _platform.ReadPageTextAsync(window.Handle, maximumCharacters, cancellationToken)
                .ConfigureAwait(false);
        }
        page ??= await ReadUncoveredAsync(window.Handle, maximumCharacters, cancellationToken).ConfigureAwait(false);
        if (page is null)
            return PageNotShown(operation, browser);
        string? address = await _platform.ReadAddressAsync(window.Handle, cancellationToken).ConfigureAwait(false);
        string pageText = PageBlocks.WithoutObjectMarks(page.Text);
        IReadOnlyList<PageBlock> blocks = PageBlocks.Read(page.Nodes, pageText.Length, maximumCharacters, out bool blocksCut);
        int blocksSize = blocks.Sum(static block => block.Title.Length + block.Address.Length + block.Text.Length + PageBlocks.BlockOverhead);
        bool textCut = false;
        string text = blocks.Count > 0
            ? PageBlocks.TextOutside(pageText, blocks, maximumCharacters - blocksSize, out textCut)
            : pageText;
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("url", address ?? string.Empty);
            writer.WriteString("title", page.Title);
            // Encargo 82: before the text, which a long page cuts.
            if (PageRows.Read(page.Rows, DateTime.Now, CultureInfo.CurrentCulture) is { } rows)
            {
                writer.WriteStartObject("rows");
                writer.WriteNumber("count", rows.Count);
                writer.WriteString("order", "row 1 is the top one on screen");
                if (rows.LatestRow is int latest)
                {
                    writer.WriteStartObject("latestDated");
                    writer.WriteNumber("row", latest);
                    writer.WriteString("when", rows.LatestWhen);
                    writer.WriteString("text", rows.LatestText);
                    writer.WriteEndObject();
                }
                if (rows.WithoutDate > 0)
                    writer.WriteNumber("rowsWithoutDate", rows.WithoutDate);
                writer.WriteEndObject();
            }
            // Uso-111 (P3): the items of a list keep each fact beside its source; the text is what lies outside them.
            if (blocks.Count > 0)
            {
                writer.WriteStartArray("blocks");
                foreach (PageBlock block in blocks)
                {
                    writer.WriteStartObject();
                    writer.WriteString("title", block.Title);
                    if (block.Address.Length > 0)
                        writer.WriteString("url", block.Address);
                    writer.WriteString("text", block.Text);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
            }
            // Uso-108: a page read from what is on screen is not the whole of it: what lies above it is cut too. A typed fact: a
            // sentence here (three measured) did not lower what the model said falsely and sent it to read the same page again
            // (8 of 60 against 3 of 60; this field, 4).
            if (page.FromScreen)
                writer.WriteBoolean("textStartsOnScreen", true);
            // Before the text, which the limits of a result cut from its end.
            if (page.Truncated && page.CanScrollDown)
                writer.WriteString("next", PageGoesOnBelow);
            writer.WriteString("text", text);
            writer.WriteBoolean("truncated", page.Truncated || blocksCut || textCut || page.FromScreen);
            // FT/proveedores goal (review of receipts): no document was named as the window title (an untitled page, a
            // title changing, a tree not built yet) and the first one on screen was read, which may be a side panel.
            if (!page.PageMatched)
                writer.WriteBoolean("pageMatched", false);
            // Encargo 62 (R06, «ábreme la ficha» after a read): the text alone says nothing of what opens from the page.
            // By name, the way a click takes them: measured against a next pointing to a look (0/40 vs 27/40).
            if (page.Links is { Count: > 0 } links)
            {
                writer.WriteStartArray("links");
                foreach (string link in links)
                    writer.WriteStringValue(link);
                writer.WriteEndArray();
                if (page.LinksCut)
                    writer.WriteBoolean("linksTruncated", true);
            }
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
        (UserBrowserWindow? window, UserBrowserFrame? frame, bool read) =
            await TabbedWindowAsync(browser, cancellationToken).ConfigureAwait(false);
        if (window is null)
            return NotRunning(operation, browser);
        if (!read)
            frame = await ReadFrameAsync(window.Handle, cancellationToken).ConfigureAwait(false);
        IReadOnlyList<UserBrowserTab> tabs = frame?.Tabs ?? [];
        if (tabs.Count == 0)
            return PageNotShown(operation, browser);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("count", tabs.Count);
            writer.WriteBoolean("truncated", tabs.Count > limit);
            // Auditoría final (regla 3): a tab strip read with tabs that failed is the tabs read, not all of them.
            if (frame is { TabsComplete: false }) writer.WriteBoolean("tabsComplete", false);
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

    // Uso-111 (live: a browser window wholly covered by another showed UI Automation no page, in Chromium 140 and Edge 156,
    // and with --disable-features=CalculateNativeWinOcclusion it did: Chromium stops drawing what its native occlusion
    // calculation sees covered). What the person asked to read is uncovered for the moment of the read; the front goes back.
    private async ValueTask<UserBrowserPageText?> ReadUncoveredAsync(
        nint window, int maximumCharacters, CancellationToken cancellationToken)
    {
        nint front = _platform.FrontWindow();
        if (front == 0 || front == window
            || !await _platform.BringToFrontAsync(window, cancellationToken).ConfigureAwait(false))
            return null;
        try
        {
            return await _platform.ReadPageTextAsync(window, maximumCharacters, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _ = await _platform.BringToFrontAsync(front, CancellationToken.None).ConfigureAwait(false);
        }
    }

    private static readonly TimeSpan PageRetry = TimeSpan.FromMilliseconds(800);
    private const int TabbedWindowReads = 3;

    /// <summary>
    /// FT/proveedores goal (E3): the browser window the page and tab steps act on: the first one in z-order whose frame
    /// read has tabs, among the first <see cref="TabbedWindowReads"/>, so a window of the browser that is no frame (the
    /// always-on-top pop-out of a video, with no page document and no tab strip) is passed over. A browser with one
    /// window has it read by the step itself (<c>FrameRead</c> false); with no window that has tabs, the front one, as
    /// before. The window is chosen by what its frame shows, never by the person's words.
    /// </summary>
    private async ValueTask<(UserBrowserWindow? Window, UserBrowserFrame? Frame, bool FrameRead)> TabbedWindowAsync(
        UserBrowserIdentity browser, CancellationToken cancellationToken)
    {
        IReadOnlyList<UserBrowserWindow> windows = _platform.ListWindows(browser.ProcessName);
        if (windows.Count == 0)
            return (null, null, false);
        if (windows.Count == 1)
            return (windows[0], null, false);
        UserBrowserFrame? front = null;
        for (int index = 0; index < windows.Count && index < TabbedWindowReads; index++)
        {
            UserBrowserFrame? frame = await ReadFrameAsync(windows[index].Handle, cancellationToken).ConfigureAwait(false);
            if (frame is { Tabs.Count: > 0 })
                return (windows[index], frame, true);
            if (index == 0)
                front = frame;
            // Review of E3: only an always-on-top window with no tabs (the pop-out of a video) is passed over. A window
            // without tabs that is not on top (a video full screen, or a frame that could not be read) is what the
            // person sees: the step acts on it or fails, never on a window behind it they cannot see.
            if (!windows[index].Topmost)
                break;
        }
        return (windows[0], front, true);
    }

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
    internal static bool SearchTitleArrives(Uri target, string? title, string? browserSegment = null)
    {
        if (string.IsNullOrWhiteSpace(title) || SearchAddresses.SearchedText(target) is not { } searched)
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

    /// <summary>
    /// Banco de uso 2026-11-03 (U31): the title of the page a navigation arrived at, its window's title without the
    /// browser's own trailing segment (<see cref="BrowserTitleSegment"/>; with none learned, the last one), so the model
    /// reads which page came (a site's «not found» page has an address like any other). A tab still titled with its
    /// address is waited for a moment (<see cref="SamePagePolls"/>); null when no other title came.
    /// </summary>
    private async ValueTask<string?> PageTitleAsync(
        UserBrowserIdentity browser, nint window, string? browserSegment, CancellationToken cancellationToken)
    {
        if (window == 0)
            return null;
        for (int poll = 0; ; poll++)
        {
            string? title = _platform.ListWindows(browser.ProcessName)
                .FirstOrDefault(listed => listed.Handle == window)?.Title;
            if (string.IsNullOrWhiteSpace(title))
                return null;
            if (TitleAddress(title) is null)
                return WithoutBrowserSegment(title, browserSegment);
            if (poll + 1 >= SamePagePolls)
                return null;
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
        }
    }

    private static string WithoutBrowserSegment(string title, string? browserSegment)
    {
        List<string> segments = TitleSegments(title);
        if (segments.Count < 2 || (browserSegment is not null && Fold(segments[^1]) != Fold(browserSegment)))
            return title.Trim();
        string trimmed = title.TrimEnd();
        string page = trimmed[..trimmed.LastIndexOf(segments[^1], StringComparison.Ordinal)].TrimEnd();
        string? separator = TitleSeparators.FirstOrDefault(each => page.EndsWith(each.TrimEnd(), StringComparison.Ordinal));
        return separator is null ? page : page[..^separator.TrimEnd().Length].TrimEnd();
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

    /// <summary>
    /// Where a navigation arrived, or with no <paramref name="Address"/> what was checked: whether a window of the browser
    /// changed after the link (<paramref name="Changed"/>) and what the last address read showed (<paramref name="Seen"/>).
    /// </summary>
    private readonly record struct PageObservation(
        Uri? Address,
        nint Window,
        string Authority = AddressAuthority,
        string Seen = AddressNotRead,
        bool Changed = false);

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
    /// the browser opens a link in a new tab. <paramref name="FrontAddress"/> is empty when the whole frame was read and
    /// showed no address (a new tab, the start page, Opera GX's empty <c>AddressBarViewGx</c>): no page of any site was on
    /// show there. It is null when the address was not read, so the earlier page there is not known.
    /// </summary>
    private sealed record NavigationBaseline(Dictionary<nint, string> Titles, nint Front, string? FrontAddress)
    {
        /// <summary>
        /// The address could only have come from the link just opened: its window is new, or it is the front window
        /// and its address field was read before showing no address or another one. Auditoría final (regla 3): an
        /// earlier address not read is unknown, as another window's is, so an address there that is not the
        /// destination itself is never taken for the arrival.
        /// </summary>
        internal bool Fresh(nint window, Uri observed)
        {
            if (!Titles.ContainsKey(window))
                return true;
            if (window != Front || FrontAddress is null)
                return false;
            return !ShowedBefore(window, observed);
        }

        /// <summary>The front window's address field read before the link showed this very address.</summary>
        internal bool ShowedBefore(nint window, Uri observed) =>
            window == Front && TryAddress(FrontAddress, out Uri? earlier) && SameAddress(earlier, observed);
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
        long started = System.Diagnostics.Stopwatch.GetTimestamp();
        string? address = await _platform.ReadAddressAsync(front, cancellationToken).ConfigureAwait(false);
        // Noche r7 (R7-NB-5): one failed read left the page before the link unknown, and a redirect of the site could
        // not be told from a page the person had; a read that failed fast is tried once more.
        if (address is null && System.Diagnostics.Stopwatch.GetElapsedTime(started) < BaselineRetryWithin)
            address = await _platform.ReadAddressAsync(front, cancellationToken).ConfigureAwait(false);
        return new(titles, front, address?.Trim());
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
        string seenLast = AddressNotRead;
        // Noche r7 (R7-NB-5): a window whose address field still showed the page from before the link is read once more
        // from this poll on, although its title does not move.
        var rereadAt = new Dictionary<nint, int>();
        var reread = new HashSet<nint>();

        // The address read of a window: the arrival when it is the destination; a fresh address of the same site
        // is kept as a redirect. Anything else is noted by kind (seenLast), never by address.
        PageObservation? Arrived(string? text, nint window)
        {
            if (!TryAddress(text, out Uri? observed))
            {
                seenLast = text is null ? Unreadable : NoAddress;
                return null;
            }
            if (ReachedTarget(target, observed))
                return new(observed, window);
            if (before.ShowedBefore(window, observed))
            {
                seenLast = PageFromBefore;
                if (reread.Add(window))
                    rereadAt[window] = attempt + StaleRereadPolls;
            }
            else if (!ofSite(observed) || ContradictsTarget(target, observed))
                seenLast = OtherPage;
            else if (before.Fresh(window, observed))
            {
                if (redirect.Address is null)
                    redirectUntil = attempt + RedirectSettlePolls;
                redirect = new(observed, window);
            }
            else
                seenLast = SameSiteNotKnownNew;
            return null;
        }

        for (; attempt < NavigationPolls && attempt <= redirectUntil
            && (reads < AddressReads || pending is not null || rereadAt.Count > 0);
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
                if (pending is not null)
                    break;
                // A window is read again only once its title moved on: an address
                // field read while the new tab was still being built says nothing. Noche r7: or, once, when a field
                // that still showed the page from before the link has had a moment to catch up.
                bool due = rereadAt.TryGetValue(window.Handle, out int at) && attempt >= at;
                bool moved = !readTitles.TryGetValue(window.Handle, out string? read)
                    || !string.Equals(read, window.Title, StringComparison.Ordinal);
                if (!due && (!moved || reads >= AddressReads))
                    continue;
                readTitles[window.Handle] = window.Title;
                if (due)
                    rereadAt.Remove(window.Handle);
                else
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
                (PageObservation? front, string? frontSeen) =
                    await FrontShowsAsync(browser, target, ofSite, cancellationToken).ConfigureAwait(false);
                if (front is { } shownNow)
                    return shownNow;
                seenLast = frontSeen ?? seenLast;
            }
        }
        if (alreadyShown && redirect.Address is null)
        {
            (PageObservation? last, string? lastSeen) =
                await FrontShowsAsync(browser, target, ofSite, cancellationToken).ConfigureAwait(false);
            if (last is { } shownLast)
                return shownLast;
            seenLast = lastSeen ?? seenLast;
        }
        return redirect.Address is null ? new(null, nint.Zero, Seen: seenLast, Changed: clue) : redirect;
    }

    /// <summary>
    /// The front window, when its address field shows the destination asked for. Only called when it showed it before
    /// the link: its authority says so (<see cref="AlreadyShownAuthority"/>). Otherwise what the read showed, by kind
    /// (<see cref="PageObservation.Seen"/>), or null when no window was there to read.
    /// </summary>
    private async ValueTask<(PageObservation? Arrival, string? Seen)> FrontShowsAsync(
        UserBrowserIdentity browser, Uri target, Func<Uri, bool> ofSite, CancellationToken cancellationToken)
    {
        if (FrontWindow(browser) is not { } front)
            return (null, null);
        string? text = await _platform.ReadAddressAsync(front.Handle, cancellationToken).ConfigureAwait(false);
        if (!TryAddress(text, out Uri? observed))
            return (null, text is null ? Unreadable : NoAddress);
        if (ReachedTarget(target, observed))
            return (new PageObservation(observed, front.Handle, AlreadyShownAuthority), null);
        return (null, ofSite(observed) && !ContradictsTarget(target, observed) ? SameSiteNotKnownNew : OtherPage);
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
        bool coldLaunch = false,
        bool ownSessionsOnly = false,
        Uri? page = null,
        SignInSeen? signIn = null)
    {
        int notPlaying = 0;
        bool nudged = false;
        bool traced = false;
        int nextPagePlay = PagePlayPolls;
        bool pagePressed = false;
        // The silence that ends the wait is counted from the link, or from the press of the page's play control.
        int quietFrom = 0;
        for (int attempt = 0; attempt < polls; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            IReadOnlyList<UserMediaSession> sessions = await _platform.ReadMediaSessionsAsync(cancellationToken)
                .ConfigureAwait(false) ?? [];
            traced |= !BrowserSessionsUnchanged(browser, before, sessions);
            UserMediaSession? candidate = PlaybackCandidate(
                browser, expectedTitle, before, sessions, anyNewBrowserSession, coldLaunch, ownSessionsOnly);
            if (candidate is null)
            {
                if (!traced && page is not null && !pagePressed && attempt + 1 >= nextPagePlay)
                {
                    nextPagePlay *= 2;
                    if (FrontWindow(browser) is { } window)
                    {
                        UserBrowserAct pressed = await _platform.PressVideoPlayAsync(
                            window.Handle, page, cancellationToken).ConfigureAwait(false);
                        pagePressed = pressed.Step == "invoked";
                        if (pagePressed)
                            quietFrom = attempt + 1;
                        // Encargo 58: a page that asks to sign in plays nothing until the person does; with no play
                        // control pressed, the wait and the presses after it would only spend the person's time.
                        if (signIn is not null && SignInDialog(pressed.Dialogs) is { } wall)
                        {
                            signIn.Dialog = wall;
                            if (!pagePressed)
                                return null;
                        }
                    }
                }
                if (!traced && attempt + 1 - quietFrom >= silentPollsLimit)
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
    /// had no session with that title before the page was opened. A browser the call named is verified by its own
    /// sessions only (<paramref name="ownSessionsOnly"/>): the same title in another browser proves nothing.
    /// </summary>
    internal static UserMediaSession? PlaybackCandidate(
        UserBrowserIdentity browser,
        string expectedTitle,
        IReadOnlyList<UserMediaSession> before,
        IReadOnlyList<UserMediaSession> sessions,
        bool anyNewBrowserSession,
        bool coldLaunch = false,
        bool ownSessionsOnly = false)
    {
        // A browser this request launched had no page of the person's playing: any session of it that was not there
        // before is the page's, as for a service whose session title is not the title asked for.
        anyNewBrowserSession |= coldLaunch;
        if (expectedTitle.Length > 0)
        {
            UserMediaSession? titled = sessions
                .Where(session => TitlesMatch(session.Title, expectedTitle) && !AlreadyThere(session, before)
                    && (!ownSessionsOnly || browser.OwnsMediaSession(session.SourceAppUserModelId)))
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
        !AlreadyThere(candidate, before)
        && (TitlesMatch(candidate.Title, expectedTitle)
            || (coldLaunch && browser.OwnsMediaSession(candidate.SourceAppUserModelId)));

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
