using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

// Topmost: an always-on-top window (WS_EX_TOPMOST), such as the pop-out of a video.
internal sealed record UserBrowserWindow(nint Handle, string Title, bool Topmost = false);

internal sealed record UserMediaSession(
    string SourceAppUserModelId,
    string Title,
    string Artist,
    string PlaybackStatus);

/// <summary>
/// What the page step did inside the person's browser: the last step reached, the name it acted on and, when no item
/// was named as the title, the cards the page showed (<paramref name="Seen"/>).
/// </summary>
internal sealed record UserBrowserPageStep(
    bool PlayInvoked, string Step, string Chosen, IReadOnlyList<StreamingCard>? Seen = null);

/// <summary>
/// A card a streaming search showed: its title as the service writes it and, when the service marks it beside that
/// title, its <paramref name="Kind"/> («episode»: one part of a series, never the movie or series asked for) with the
/// card's whole name as the page reads it (<paramref name="Label"/>).
/// </summary>
internal sealed record StreamingCard(string Title, string? Kind = null, string? Label = null);

/// <summary>
/// A tab of the person's browser. <paramref name="X"/> and <paramref name="Y"/> are its centre as a fraction of the
/// window (independent of the display scale of whoever reads it); <paramref name="Shown"/> is false when it is off
/// screen (minimized window, scrolled tab strip) and has no place to be pointed at. <paramref name="Id"/> is the tab
/// element's UI Automation runtime id (empty when not read): the same tab between two reads, whatever its title does
/// (Edge names its active tab with its memory use, which changes; a page retitles itself).
/// </summary>
internal sealed record UserBrowserTab(
    string Title, bool Selected, bool Shown = false, double X = 0, double Y = 0, string Id = "");

/// <summary>
/// One read of the browser frame: its tabs, whether the back button is enabled (null when no back button was found),
/// the address field, and the page document of the active tab. <paramref name="PageId"/> is the document's UI
/// Automation runtime id, which changes when the tab reloads or leaves the page; <paramref name="Scroll"/> is its
/// vertical position in percent, or -1 when the document itself does not scroll.
/// FT/proveedores goal (E3): <paramref name="TabsComplete"/> is the tab strip read whole; <paramref name="Complete"/>
/// the whole frame (a dead node outside the strip, as Opera GX keeps after a Speed Dial, leaves only this one false);
/// <paramref name="PageMatched"/> says the page document was the one named as the window title begins.
/// </summary>
internal sealed record UserBrowserFrame(
    IReadOnlyList<UserBrowserTab> Tabs,
    bool? BackEnabled,
    string Address,
    string PageId,
    string PageTitle,
    double Scroll,
    bool TabsComplete = true,
    bool Complete = true,
    bool PageMatched = true);

/// <summary>
/// What a UI Automation step inside the frame or the page did (see UserBrowserScripts.Act); <paramref name="Dialogs"/>,
/// the dialogs on show in the page a play step read (null when it read none).
/// </summary>
internal sealed record UserBrowserAct(
    string Step, double Before, double After, IReadOnlyList<UserBrowserDialog>? Dialogs = null);

/// <summary>
/// Encargo 58: a dialog of the page (ARIA dialog or alertdialog, which Chromium gives UI Automation as a Window inside
/// the document), by its name, with the links it holds by name and address.
/// </summary>
internal sealed record UserBrowserDialog(string Name, IReadOnlyList<UserBrowserLink> Links);

internal sealed record UserBrowserLink(string Name, string Address);

// PageMatched: the document read is the one the window title names; false, it is the first one on screen (a side panel
// or the Speed Dial may be it). FromScreen: a long page was read from what is on screen, not from its start. CanScrollDown:
// the page itself scrolls and is not at its end.
internal sealed record UserBrowserPageText(
    string Title, string Text, bool Truncated, bool PageMatched = true,
    IReadOnlyList<string>? Links = null, bool LinksCut = false, IReadOnlyList<UserBrowserPageRow>? Rows = null,
    IReadOnlyList<PageNode>? Nodes = null, bool FromScreen = false, bool CanScrollDown = false);

/// <summary>
/// Everything the user-browser surface touches on the PC. The production
/// implementation opens links the way the shell does, reads top-level window
/// titles, the system media sessions (SMTC) and the address field through UI
/// Automation; tests replace it whole.
/// </summary>
internal interface IUserBrowserPlatform
{
    UserBrowserIdentity? ResolveDefault();

    /// <summary>
    /// The installed browser of that family Windows has registered, or null when none is. Throws when the registry cannot
    /// be read.
    /// </summary>
    UserBrowserIdentity? ResolveRegistered(string family);

    /// <summary>Opens the address with the person's default browser. Throws when nothing was launched.</summary>
    void Open(Uri address);

    /// <summary>Opens the address with that browser's own executable, not the default one. Throws when nothing was launched.</summary>
    void OpenWith(UserBrowserIdentity browser, Uri address);

    IReadOnlyList<UserBrowserWindow> ListWindows(string processName);

    /// <summary>Puts the window in front, where the keys typed next go, and records it as the surface BAXY just put on
    /// show (a keyboard act with no window goes to it); whether it holds the front.</summary>
    ValueTask<bool> BringToFrontAsync(nint window, CancellationToken cancellationToken);

    /// <summary>The media sessions, or null when they could not all be read.</summary>
    ValueTask<IReadOnlyList<UserMediaSession>?> ReadMediaSessionsAsync(CancellationToken cancellationToken);

    ValueTask<bool> PlayMediaSessionAsync(UserMediaSession session, CancellationToken cancellationToken);

    /// <summary>The text of the window's address field, or null when UI Automation cannot read it.</summary>
    ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken);

    /// <summary>Picks the named title on a streaming page shown in the window and presses its play control.</summary>
    ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
        nint window, string title, bool typeSearch, CancellationToken cancellationToken);

    /// <summary>The window's frame (tabs, back button, address, page document), or null when its tab strip cannot be read.</summary>
    ValueTask<UserBrowserFrame?> ReadFrameAsync(nint window, CancellationToken cancellationToken);

    /// <summary>
    /// Posts a WM_APPCOMMAND to the window (back, forward, reload): Chromium runs it on the active tab whatever window
    /// has the foreground, with no key and no menu. False when the message could not be posted.
    /// </summary>
    bool PostAppCommand(nint window, int command);

    /// <summary>
    /// Posts a WM_COMMAND with a Chromium browser command id (IDC_NEW_TAB, IDC_CLOSE_TAB…): Chrome, Edge and Brave run
    /// it as their menu would, without the foreground. False when the message could not be posted.
    /// </summary>
    bool PostBrowserCommand(nint window, int command);

    /// <summary>
    /// Posts a middle click at a point of the window given as a fraction of it (a tab's centre): Chromium closes the
    /// tab under it, without the foreground. False when the message could not be posted.
    /// </summary>
    bool PostMiddleClick(nint window, double x, double y);

    /// <summary>Runs a UI Automation step in the window: new_tab, scroll_down, scroll_up or fullscreen_video.</summary>
    ValueTask<UserBrowserAct> ActAsync(nint window, string action, CancellationToken cancellationToken);

    /// <summary>
    /// Selects the tab of the window whose UI Automation runtime id is <paramref name="tabId"/> (SelectionItemPattern
    /// Select on its TabItem): «selected», «tab_not_found» or «select_unavailable» (nothing selected), or a UI
    /// Automation failure. Whether it became the active tab is read again by the caller.
    /// </summary>
    ValueTask<UserBrowserAct> SelectTabAsync(nint window, string tabId, CancellationToken cancellationToken);

    /// <summary>
    /// Presses the play control of the page at <paramref name="page"/> in the window (UI Automation Invoke, which the
    /// browser takes as the person's click): «invoked», «page_not_found» (no tab of the window is at that address) or
    /// «play_control_not_found».
    /// </summary>
    ValueTask<UserBrowserAct> PressVideoPlayAsync(nint window, Uri page, CancellationToken cancellationToken);

    /// <summary>Whether the window covers its whole monitor (a video in full screen), taskbar included.</summary>
    bool CoversMonitor(nint window);

    /// <summary>The window in front now; 0 when it is not known.</summary>
    nint FrontWindow() => 0;

    /// <summary>The title and visible text of the page the window shows, or null when it cannot be read.</summary>
    ValueTask<UserBrowserPageText?> ReadPageTextAsync(
        nint window, int maximumCharacters, CancellationToken cancellationToken);

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal sealed partial class WindowsUserBrowserPlatform : IUserBrowserPlatform
{
    // One persistent PowerShell for every browser script of the process (each platform instance shares it): computer
    // use measured 3.1 s per tab closed while each frame read started its own PowerShell. It is not the computer-use
    // worker, so a page that is waited on (PagePlay, up to 45 s) never holds a view or a click; it keeps the scaling
    // of the per-call PowerShell it replaces. It ends with this process (end of its input).
    private static readonly Lazy<UiaWorkerHost> SharedScripts = new(
        () => new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"), "-DpiUnaware"));

    private readonly IUiaWorker _scripts;

    internal WindowsUserBrowserPlatform()
        : this(SharedScripts.Value)
    {
    }

    internal WindowsUserBrowserPlatform(IUiaWorker scripts) =>
        _scripts = scripts ?? throw new ArgumentNullException(nameof(scripts));

    public UserBrowserIdentity? ResolveDefault() => UserBrowserIdentityResolver.ResolveFromRegistry();

    public UserBrowserIdentity? ResolveRegistered(string family) => UserBrowserIdentityResolver.ResolveRegistered(family);

    public void Open(Uri address)
    {
        RequireWebAddress(address);
        if (ResolveDefault() is { } browser)
        {
            // A Chrome that needs the flag is started as OpenWith starts it: the shell's path could not carry it.
            if (ChromeUiaFlag.For(browser.Executable) is not null)
            {
                OpenWith(browser, address);
                return;
            }

            AllowForeground(browser);
        }

        // The shell resolves the link exactly as a click would: the person's
        // browser, their profile and session, a new tab in the window they use.
        using Process? launched = Process.Start(new ProcessStartInfo(address.AbsoluteUri)
        {
            UseShellExecute = true,
        });
    }

    public void OpenWith(UserBrowserIdentity browser, Uri address)
    {
        ArgumentNullException.ThrowIfNull(browser);
        RequireWebAddress(address);
        AllowForeground(browser);
        // Feria 2026-10-27 (caso 19): the address as the only argument of the browser's own executable, as its
        // registered open command passes a link: the person's profile, a new tab in the window of it already running.
        // Started outside BAXY's job and inheriting none of the core's handles (its stdio pipes), as the files and the
        // CDP browser are (InvokerLaunch, review of M5): a browser started here lives for hours.
        if (Applications.InvokerLaunch.StartOutsideBaxy(new Applications.InvokerLaunch.LaunchPlan(
                browser.Executable,
                (ChromeUiaFlag.For(browser.Executable) is { } flag ? flag + " " : string.Empty)
                    + "\"" + address.AbsoluteUri + "\"",
                Path.GetDirectoryName(browser.Executable) ?? Environment.SystemDirectory)) <= 0)
            throw new InvalidOperationException("The named browser could not be started.");
    }

    private static void RequireWebAddress(Uri address)
    {
        ArgumentNullException.ThrowIfNull(address);
        if (address.Scheme is not ("http" or "https"))
            throw new ArgumentException("Only web addresses are opened.", nameof(address));
    }

    // PLAN_GENERAL B3: the right to take the front is handed to the browser already running, by its exact process
    // (Raymond Chen, «Sure, you can steal the foreground…» 2009-02-20; Chromium does the same for its running copy),
    // so the browser may raise the page it opens itself. Refused when this process holds no right to give: the
    // bringing up after the navigation (BringToFrontAsync) still does it then.
    private static void AllowForeground(UserBrowserIdentity browser)
    {
        foreach (Process running in Process.GetProcessesByName(browser.ProcessName))
        {
            using (running)
                _ = AllowSetForegroundWindow(unchecked((uint)running.Id));
        }
    }

    // Under the gate of the opening guards, and said before it happens, as a lease takes the front (ForegroundLease).
    public nint FrontWindow() => VisibleControlSurface.FrontWindow();

    public async ValueTask<bool> BringToFrontAsync(nint window, CancellationToken cancellationToken)
    {
        // PLAN_GENERAL B2 (uso real 2026-10-20: the text typed after a page was opened went to Spotify): the page just
        // opened is what BAXY put on show, as an opened application is, so a key or a text with no window of its own
        // goes to it through the lease, or nowhere (OpenedApplicationKeyboard), and a click acts on it (M132).
        VisibleControlSurface.NoteOpened(VisibleControlSurface.WindowProcess(window).ProcessId, launched: false, window);
        await Applications.ForegroundHandBack.FrontGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            LeaseFrontSignal.Mark(window);
            return VisibleControlSurface.BringToFront(window);
        }
        finally
        {
            _ = Applications.ForegroundHandBack.FrontGate.Release();
        }
    }

    public IReadOnlyList<UserBrowserWindow> ListWindows(string processName)
    {
        var owners = new HashSet<uint>();
        Process[] processes = Process.GetProcessesByName(processName);
        try
        {
            foreach (Process process in processes)
                owners.Add(checked((uint)process.Id));
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
        var windows = new List<UserBrowserWindow>();
        if (owners.Count == 0)
            return windows;
        EnumWindowsProc callback = (window, unused) =>
        {
            // FT/proveedores goal (E3): only the browser's own frames. A window another one owns, a tool window (a
            // pop-out or bubble) or one the shell cloaks (another virtual desktop) is not the window the person sees.
            if (!IsWindowVisible(window) || GetWindow(window, OwnerWindow) != nint.Zero
                || (GetWindowLongPtr(window, ExtendedStyleIndex).ToInt64() & ToolWindowStyle) != 0
                || (DwmGetWindowAttribute(window, CloakedAttribute, out int cloaked, sizeof(int)) == 0 && cloaked != 0))
                return true;
            _ = GetWindowThreadProcessId(window, out uint owner);
            if (!owners.Contains(owner))
                return true;
            string title = ReadWindowTitle(window);
            if (title.Length > 0)
                windows.Add(new UserBrowserWindow(window, title,
                    (GetWindowLongPtr(window, ExtendedStyleIndex).ToInt64() & TopmostStyle) != 0));
            return true;
        };
        // A failed enumeration is no observation: the caller sees no window
        // change and the navigation stays unconfirmed, never an exception.
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return windows;
    }

    public async ValueTask<IReadOnlyList<UserMediaSession>?> ReadMediaSessionsAsync(
        CancellationToken cancellationToken) =>
        await MediaSessionCalls.ReadCompleteAsync(cancellationToken).ConfigureAwait(false);

    public async ValueTask<bool> PlayMediaSessionAsync(
        UserMediaSession target, CancellationToken cancellationToken)
    {
        try
        {
            return await MediaSessionCalls.ControlAsync(
                target.SourceAppUserModelId, target.Title, pause: false, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return false;
        }
    }

    public async ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Address,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            TimeSpan.FromSeconds(8),
            cancellationToken).ConfigureAwait(false);
        return result is { } value
            && value.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
            && value.TryGetProperty("value", out JsonElement address)
            && address.ValueKind == JsonValueKind.String
                ? address.GetString()
                : null;
    }

    public async ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
        nint window, string title, bool typeSearch, CancellationToken cancellationToken)
    {
        string[] arguments =
        [
            window.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(title)),
            "30",
            typeSearch ? "1" : "0",
            UserBrowserScripts.EpisodeMark,
        ];
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.PagePlay, arguments, TimeSpan.FromSeconds(45), cancellationToken)
            .ConfigureAwait(false);
        return result is { } value ? ParsePageStep(value) : new UserBrowserPageStep(false, "script_failed", string.Empty);
    }

    internal static UserBrowserPageStep ParsePageStep(JsonElement value)
    {
        bool played = value.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True;
        // ConvertTo-Json writes a one-element array as the element itself.
        IEnumerable<JsonElement> cards = !value.TryGetProperty("seen", out JsonElement seenValue) ? []
            : seenValue.ValueKind == JsonValueKind.Array ? seenValue.EnumerateArray()
            : [seenValue];
        StreamingCard[] seen = [.. cards
            .Where(card => card.ValueKind == JsonValueKind.Object && TextOf(card, "title").Length > 0)
            .Select(card => new StreamingCard(
                TextOf(card, "title"), NullIfEmpty(TextOf(card, "kind")), NullIfEmpty(TextOf(card, "label"))))];
        return new UserBrowserPageStep(played, TextOf(value, "step"), TextOf(value, "chosen"), seen);
    }

    private static string TextOf(JsonElement value, string name) =>
        value.TryGetProperty(name, out JsonElement text) && text.ValueKind == JsonValueKind.String
            ? text.GetString() ?? string.Empty
            : string.Empty;

    private static string? NullIfEmpty(string text) => text.Length == 0 ? null : text;

    public async ValueTask<UserBrowserFrame?> ReadFrameAsync(nint window, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Frame,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            TimeSpan.FromSeconds(10),
            cancellationToken).ConfigureAwait(false);
        return result is { } value ? ParseFrame(value) : null;
    }

    internal static UserBrowserFrame? ParseFrame(JsonElement value)
    {
        if (!value.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
            || !value.TryGetProperty("tabs", out JsonElement tabs))
            return null;
        // ConvertTo-Json writes a one-element array as the element itself.
        IEnumerable<JsonElement> items = tabs.ValueKind switch
        {
            JsonValueKind.Array => tabs.EnumerateArray(),
            JsonValueKind.Object => [tabs],
            _ => [],
        };
        var read = new List<UserBrowserTab>();
        foreach (JsonElement tab in items)
        {
            read.Add(new UserBrowserTab(
                Text(tab, "title"),
                tab.TryGetProperty("selected", out JsonElement flag) && flag.ValueKind == JsonValueKind.True,
                tab.TryGetProperty("shown", out JsonElement shown) && shown.ValueKind == JsonValueKind.True,
                Number(tab, "x"),
                Number(tab, "y"),
                Text(tab, "id")));
        }
        if (read.Count == 0)
            return null;
        string back = Text(value, "back");
        JsonElement page = value.TryGetProperty("page", out JsonElement found) && found.ValueKind == JsonValueKind.Object
            ? found
            : default;
        bool hasPage = page.ValueKind == JsonValueKind.Object;
        return new UserBrowserFrame(
            read,
            back switch { "enabled" => true, "disabled" => false, _ => null },
            Text(value, "address"),
            hasPage ? Text(page, "id") : string.Empty,
            hasPage ? Text(page, "title") : string.Empty,
            hasPage ? Number(page, "scroll", -1) : -1,
            !(value.TryGetProperty("tabsComplete", out JsonElement tabsComplete) && tabsComplete.ValueKind == JsonValueKind.False),
            !(value.TryGetProperty("complete", out JsonElement complete) && complete.ValueKind == JsonValueKind.False),
            hasPage && page.TryGetProperty("matched", out JsonElement matched) && matched.ValueKind == JsonValueKind.True);
    }

    public bool PostAppCommand(nint window, int command) =>
        window != nint.Zero
        && PostMessage(window, WmAppCommand, window, (nint)(command << 16));

    public bool PostBrowserCommand(nint window, int command) =>
        window != nint.Zero
        && PostMessage(window, WmCommand, (nint)command, nint.Zero);

    public bool PostMiddleClick(nint window, double x, double y)
    {
        if (window == nint.Zero || x is <= 0 or >= 1 || y is <= 0 or >= 1 || !GetWindowRect(window, out Rect frame))
            return false;
        var point = new Point
        {
            X = frame.Left + (int)Math.Round((frame.Right - frame.Left) * x),
            Y = frame.Top + (int)Math.Round((frame.Bottom - frame.Top) * y),
        };
        if (!ScreenToClient(window, ref point))
            return false;
        nint position = (nint)(((point.Y & 0xFFFF) << 16) | (point.X & 0xFFFF));
        // The pointer passes over the tab first, as a hand would, then the middle button goes down and up on it.
        return PostMessage(window, WmMouseMove, nint.Zero, position)
            && PostMessage(window, WmMiddleButtonDown, MiddleButton, position)
            && PostMessage(window, WmMiddleButtonUp, nint.Zero, position);
    }

    public async ValueTask<UserBrowserAct> ActAsync(nint window, string action, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Act,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture), action],
            TimeSpan.FromSeconds(20),
            cancellationToken).ConfigureAwait(false);
        return result is { } value
            ? new UserBrowserAct(Text(value, "step"), Number(value, "before", -1), Number(value, "after", -1))
            : new UserBrowserAct("script_failed", -1, -1);
    }

    public async ValueTask<UserBrowserAct> SelectTabAsync(nint window, string tabId, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Act,
            [window.ToString(System.Globalization.CultureInfo.InvariantCulture), "select_tab", tabId],
            TimeSpan.FromSeconds(20),
            cancellationToken).ConfigureAwait(false);
        return result is { } value
            ? new UserBrowserAct(Text(value, "step"), -1, -1)
            : new UserBrowserAct("script_failed", -1, -1);
    }

    public async ValueTask<UserBrowserAct> PressVideoPlayAsync(nint window, Uri page, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.Act,
            [
                window.ToString(System.Globalization.CultureInfo.InvariantCulture),
                "play_video",
                Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(page.AbsoluteUri)),
            ],
            TimeSpan.FromSeconds(20),
            cancellationToken).ConfigureAwait(false);
        return result is { } value
            ? new UserBrowserAct(Text(value, "step"), -1, -1, ParseDialogs(value))
            : new UserBrowserAct("script_failed", -1, -1);
    }

    // Encargo 58: the page's dialogs the play step read, with their links (null: the step read none).
    internal static IReadOnlyList<UserBrowserDialog>? ParseDialogs(JsonElement value)
    {
        if (!value.TryGetProperty("dialogs", out JsonElement dialogs) || dialogs.ValueKind != JsonValueKind.Array)
            return null;
        return [.. dialogs.EnumerateArray()
            .Where(static dialog => dialog.ValueKind == JsonValueKind.Object)
            .Select(static dialog => new UserBrowserDialog(
                Text(dialog, "name"),
                dialog.TryGetProperty("links", out JsonElement links) && links.ValueKind == JsonValueKind.Array
                    ? [.. links.EnumerateArray()
                        .Where(static link => link.ValueKind == JsonValueKind.Object)
                        .Select(static link => new UserBrowserLink(Text(link, "name"), Text(link, "address")))]
                    : []))];
    }

    public bool CoversMonitor(nint window)
    {
        if (window == nint.Zero || !GetWindowRect(window, out Rect frame))
            return false;
        nint monitor = MonitorFromWindow(window, MonitorDefaultToNearest);
        var info = new MonitorInfo { Size = Marshal.SizeOf<MonitorInfo>() };
        return monitor != nint.Zero && GetMonitorInfo(monitor, ref info)
            && frame.Left <= info.Monitor.Left && frame.Top <= info.Monitor.Top
            && frame.Right >= info.Monitor.Right && frame.Bottom >= info.Monitor.Bottom;
    }

    private static string Text(JsonElement value, string property) =>
        value.TryGetProperty(property, out JsonElement field) && field.ValueKind == JsonValueKind.String
            ? field.GetString() ?? string.Empty
            : string.Empty;

    private static double Number(JsonElement value, string property, double fallback = 0) =>
        value.TryGetProperty(property, out JsonElement field) && field.ValueKind == JsonValueKind.Number
            ? field.GetDouble()
            : fallback;

    public async ValueTask<UserBrowserPageText?> ReadPageTextAsync(
        nint window, int maximumCharacters, CancellationToken cancellationToken)
    {
        JsonElement? result = await RunScriptAsync(
            UserBrowserScripts.PageText,
            [
                window.ToString(System.Globalization.CultureInfo.InvariantCulture),
                maximumCharacters.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ],
            TimeSpan.FromSeconds(20),
            cancellationToken).ConfigureAwait(false);
        if (result is not { } value
            || !value.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return null;
        string Read(string property) => value.TryGetProperty(property, out JsonElement field)
            && field.ValueKind == JsonValueKind.String ? field.GetString() ?? string.Empty : string.Empty;
        bool truncated = value.TryGetProperty("truncated", out JsonElement cut) && cut.ValueKind == JsonValueKind.True;
        bool matched = !value.TryGetProperty("matched", out JsonElement match) || match.ValueKind != JsonValueKind.False;
        string[] links = value.TryGetProperty("links", out JsonElement named) && named.ValueKind == JsonValueKind.Array
            ? [.. named.EnumerateArray().Where(static link => link.ValueKind == JsonValueKind.String)
                .Select(static link => link.GetString() ?? string.Empty)]
            : [];
        bool linksCut = value.TryGetProperty("linksCut", out JsonElement cutLinks) && cutLinks.ValueKind == JsonValueKind.True;
        UserBrowserPageRow[] rows = value.TryGetProperty("rows", out JsonElement listed) && listed.ValueKind == JsonValueKind.Array
            ? [.. listed.EnumerateArray().Where(static row => row.ValueKind == JsonValueKind.Object).Select(static row =>
                new UserBrowserPageRow(
                    Number(row, "top", 0),
                    Number(row, "bottom", 0),
                    row.TryGetProperty("cells", out JsonElement cells) && cells.ValueKind == JsonValueKind.Array
                        ? [.. cells.EnumerateArray().Where(static cell => cell.ValueKind == JsonValueKind.String)
                            .Select(static cell => cell.GetString() ?? string.Empty)]
                        : []))]
            : [];
        PageNode[] nodes = value.TryGetProperty("nodes", out JsonElement pieces) && pieces.ValueKind == JsonValueKind.Array
            ? [.. pieces.EnumerateArray().Where(static piece => piece.ValueKind == JsonValueKind.Object).Select(static piece =>
                new PageNode(
                    piece.TryGetProperty("link", out JsonElement isLink) && isLink.ValueKind == JsonValueKind.True,
                    Text(piece, "name"),
                    Text(piece, "address"),
                    (int)Number(piece, "depth"),
                    (int)Number(piece, "under", -1),
                    (int)Number(piece, "rise"),
                    piece.TryGetProperty("gap", out JsonElement gap) && gap.ValueKind == JsonValueKind.True,
                    Number(piece, "top"),
                    Number(piece, "bottom")))]
            : [];
        bool fromScreen = value.TryGetProperty("fromScreen", out JsonElement shown) && shown.ValueKind == JsonValueKind.True;
        return new UserBrowserPageText(
            Read("title"), Read("text"), truncated, matched, links, linksCut, rows, nodes, fromScreen,
            value.TryGetProperty("canScrollDown", out JsonElement down) && down.ValueKind == JsonValueKind.True);
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private async ValueTask<JsonElement?> RunScriptAsync(
        string script,
        IReadOnlyList<string> scriptArguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        var arguments = new System.Text.Json.Nodes.JsonArray();
        foreach (string argument in scriptArguments)
            arguments.Add((System.Text.Json.Nodes.JsonNode?)argument);
        string command = new System.Text.Json.Nodes.JsonObject
        {
            ["cmd"] = "script",
            ["script"] = script,
            ["args"] = arguments,
        }.ToJsonString();
        try
        {
            // A script that does not answer in time takes its worker with it; the next one starts a fresh worker.
            using JsonDocument? answer = await _scripts.SendAsync(command, timeout, cancellationToken)
                .ConfigureAwait(false);
            if (answer is null
                || !answer.RootElement.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
                || !answer.RootElement.TryGetProperty("line", out JsonElement written)
                || written.ValueKind != JsonValueKind.String
                || written.GetString() is not { } line || !line.StartsWith('{'))
            {
                return null;
            }

            using JsonDocument document = JsonDocument.Parse(line);
            return document.RootElement.Clone();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static unsafe string ReadWindowTitle(nint handle)
    {
        const int capacity = 1024;
        char* buffer = stackalloc char[capacity];
        int length = GetWindowText(handle, buffer, capacity);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AllowSetForegroundWindow(uint processId);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint window, char* text, int capacity);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint window, uint command);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    private static partial nint GetWindowLongPtr(nint window, int index);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(nint window, uint attribute, out int value, int size);

    private const uint OwnerWindow = 4;
    private const int ExtendedStyleIndex = -20;
    private const long ToolWindowStyle = 0x80;
    private const long TopmostStyle = 0x8;
    private const uint CloakedAttribute = 14;

    private const uint WmAppCommand = 0x0319;
    private const uint WmCommand = 0x0111;
    private const uint WmMouseMove = 0x0200;
    private const uint WmMiddleButtonDown = 0x0207;
    private const uint WmMiddleButtonUp = 0x0208;
    private const nint MiddleButton = 0x0010;
    private const uint MonitorDefaultToNearest = 2;

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorInfo
    {
        public int Size;
        public Rect Monitor;
        public Rect Work;
        public uint Flags;
    }

    [LibraryImport("user32.dll", EntryPoint = "PostMessageW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PostMessage(nint window, uint message, nint wParam, nint lParam);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint window, out Rect rect);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ScreenToClient(nint window, ref Point point);

    [LibraryImport("user32.dll")]
    private static partial nint MonitorFromWindow(nint window, uint flags);

    [LibraryImport("user32.dll", EntryPoint = "GetMonitorInfoW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetMonitorInfo(nint monitor, ref MonitorInfo info);
}
