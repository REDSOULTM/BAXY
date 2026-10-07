namespace Baxy.Providers.Windows.External;

/// <summary>
/// Owner 2026-10-06 («lo de mover pestañas… que el Baxi no se limite»): browser.control acts on the person's own
/// browser, the front window of their default browser, never on a browser BAXY keeps aside. Each step is taken the
/// way the browser itself takes it without the keyboard, the menu or the foreground —a window message Chromium runs as
/// its own command, or a UI Automation pattern— and is verified by reading the frame again: the tab count and the
/// selected tab, the page document's identity, the scroll position or the window covering the monitor. What cannot be
/// read afterwards is said as unconfirmed (documentacion/NAVEGADOR_USUARIO.md, «Pestañas»).
/// </summary>
internal sealed partial class UserBrowserSurface
{
    internal const string TabStepUnconfirmed = "user_browser_tab_step_unconfirmed";
    internal const string TabStepUnavailable = "user_browser_tab_step_unavailable";
    internal const string LastTabKept = "user_browser_last_tab_kept";
    internal const string CloseAllIncomplete = "user_browser_close_all_incomplete";
    internal const string FullscreenControlMissing = "user_browser_fullscreen_control_missing";
    internal const string HistoryStart = "user_browser_history_start";
    internal const string ScrollBoundary = "user_browser_scroll_boundary";
    internal const string FrameAuthority = "user_browser_uia_frame_postread";

    // WM_APPCOMMAND commands (winuser.h) and Chromium browser command ids (chrome/app/chrome_command_ids.h).
    internal const int AppCommandBack = 1;
    internal const int AppCommandRefresh = 3;
    internal const int AppCommandNew = 29;
    internal const int AppCommandClose = 31;
    internal const int BrowserCommandNewTab = 34014;
    internal const int BrowserCommandCloseTab = 34015;

    private static readonly TimeSpan FramePoll = TimeSpan.FromMilliseconds(300);
    private const int FrameReads = 4;
    private const int FullscreenPolls = 12;
    private const int CloseAllTabs = 50;
    private static readonly TimeSpan CloseAllTime = TimeSpan.FromSeconds(40);

    internal async ValueTask<ExternalCapabilityReceipt> ControlAsync(
        string operation,
        UserBrowserIdentity browser,
        string action,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (action is not ("back" or "close" or "close_all" or "fullscreen_video" or "new_tab" or "reload"
            or "scroll_down" or "scroll_up"))
            return ExternalJson.Failure(operation, "browser_control_action_invalid");
        UserBrowserWindow? window = FrontWindow(browser);
        if (window is null)
            return ExternalJson.FailureBeforeEffect(operation, BrowserNotRunning);
        var step = new TabStep(operation, browser, action, window.Handle, effectBoundary);
        return action switch
        {
            "back" => await HistoryStepAsync(step, AppCommandBack, cancellationToken).ConfigureAwait(false),
            "reload" => await HistoryStepAsync(step, AppCommandRefresh, cancellationToken).ConfigureAwait(false),
            "new_tab" => await NewTabAsync(step, cancellationToken).ConfigureAwait(false),
            "close" => await CloseTabAsync(step, cancellationToken).ConfigureAwait(false),
            "close_all" => await CloseAllTabsAsync(step, cancellationToken).ConfigureAwait(false),
            "fullscreen_video" => await FullscreenAsync(step, cancellationToken).ConfigureAwait(false),
            _ => await ScrollAsync(step, cancellationToken).ConfigureAwait(false),
        };
    }

    private readonly record struct TabStep(
        string Operation,
        UserBrowserIdentity Browser,
        string Action,
        nint Window,
        ExternalEffectBoundary Boundary);

    /// <summary>
    /// Back and reload: WM_APPCOMMAND, which Chromium (Opera GX included, measured 2026-10-06) runs on the active tab.
    /// Going back is seen as another page document or address; reloading, as a new document of the same page.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> HistoryStepAsync(
        TabStep step, int command, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadFrameAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (before is null || before.PageId.Length == 0)
            return ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable);
        bool back = command == AppCommandBack;
        if (back && before.BackEnabled == false)
            return ExternalJson.FailureBeforeEffect(step.Operation, HistoryStart);
        if (!_platform.PostAppCommand(step.Window, command))
            return ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserFrame? after = await AwaitFrameAsync(
            step.Window,
            frame => frame.PageId.Length > 0 && frame.PageId != before.PageId
                || back && frame.Address.Length > 0 && frame.Address != before.Address,
            cancellationToken).ConfigureAwait(false);
        return after is null
            ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
            : Done(step, back ? "went_back" : "reloaded", after);
    }

    /// <summary>
    /// A new tab: Chromium's IDC_NEW_TAB by message; a browser that does not run it (Opera GX) gets its tab strip's
    /// new-tab button pressed through UI Automation. Seen as one tab more.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> NewTabAsync(TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadFrameAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (before is null)
            return ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable);
        int count = before.Tabs.Count;
        bool OneMore(UserBrowserFrame frame) => frame.Tabs.Count > count;
        UserBrowserFrame? after = null;
        if (PostTabCommand(step, BrowserCommandNewTab, AppCommandNew))
        {
            step.Boundary.Cross(CancellationToken.None);
            after = await AwaitFrameAsync(step.Window, OneMore, cancellationToken).ConfigureAwait(false);
        }
        if (after is null)
        {
            step.Boundary.Cross(CancellationToken.None);
            UserBrowserAct pressed = await _platform.ActAsync(step.Window, "new_tab", cancellationToken)
                .ConfigureAwait(false);
            if (pressed.Step == "invoked")
                after = await AwaitFrameAsync(step.Window, OneMore, cancellationToken).ConfigureAwait(false);
        }
        return after is null
            ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
            : Done(step, "tab_opened", after);
    }

    /// <summary>
    /// The active tab: Chromium's IDC_CLOSE_TAB by message, else a middle click posted on that tab (what closes a tab
    /// in every Chromium browser, Opera GX measured). The last tab is kept: closing it closes the person's window.
    /// Seen as one tab less.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> CloseTabAsync(TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadFrameAsync(step.Window, cancellationToken).ConfigureAwait(false);
        UserBrowserTab? active = before?.Tabs.FirstOrDefault(tab => tab.Selected);
        if (before is null || active is null)
            return ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable);
        if (before.Tabs.Count <= 1)
            return ExternalJson.FailureBeforeEffect(step.Operation, LastTabKept);
        UserBrowserFrame? after = await CloseActiveTabAsync(step, before, active, cancellationToken)
            .ConfigureAwait(false);
        if (after is null)
            return step.Boundary.WasCrossed
                ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
                : ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        return Done(step, "tab_closed", after, closed: active.Title);
    }

    /// <summary>
    /// Every tab but one (asked for with the person's confirmation: RiskPolicy, it loses their session): the active
    /// tab closed the way a single close is taken, again and again, each close seen as one tab less before the next.
    /// The last tab is kept, as for a single close. A close that is not seen, or a strip that runs past the bound,
    /// stops the step there and says how many were closed.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> CloseAllTabsAsync(
        TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? frame = await ReadFrameAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (frame is null || !frame.Tabs.Any(tab => tab.Selected))
            return ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable);
        if (frame.Tabs.Count <= 1)
            return ExternalJson.FailureBeforeEffect(step.Operation, LastTabKept) with
            {
                Result = TabsClosed(step, 0, frame),
            };
        long started = System.Diagnostics.Stopwatch.GetTimestamp();
        int closed = 0;
        while (frame.Tabs.Count > 1)
        {
            UserBrowserTab? active = frame.Tabs.FirstOrDefault(tab => tab.Selected);
            if (active is null)
                return StoppedClosing(step, PageUnreadable, closed);
            if (closed >= CloseAllTabs || System.Diagnostics.Stopwatch.GetElapsedTime(started) > CloseAllTime)
                return StoppedClosing(step, CloseAllIncomplete, closed);
            UserBrowserFrame? after = await CloseActiveTabAsync(step, frame, active, cancellationToken)
                .ConfigureAwait(false);
            if (after is null)
                return step.Boundary.WasCrossed
                    ? StoppedClosing(step, TabStepUnconfirmed, closed)
                    : ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
            closed++;
            frame = after;
        }
        return ExternalJson.Success(step.Operation, TabsClosed(step, closed, frame));
    }

    /// <summary>
    /// Closes the active tab of <paramref name="before"/>: the frame read with one tab less, or null when none was
    /// seen (the step's boundary says whether anything was posted).
    /// </summary>
    private async ValueTask<UserBrowserFrame?> CloseActiveTabAsync(
        TabStep step, UserBrowserFrame before, UserBrowserTab active, CancellationToken cancellationToken)
    {
        int count = before.Tabs.Count;
        bool OneLess(UserBrowserFrame frame) => frame.Tabs.Count == count - 1;
        UserBrowserFrame? after = null;
        if (PostTabCommand(step, BrowserCommandCloseTab, AppCommandClose))
        {
            step.Boundary.Cross(CancellationToken.None);
            after = await AwaitFrameAsync(step.Window, OneLess, cancellationToken).ConfigureAwait(false);
        }
        if (after is null)
        {
            // The message was not run: the click goes only to the same tab, still active and still on screen.
            UserBrowserFrame? now = await ReadFrameAsync(step.Window, cancellationToken).ConfigureAwait(false);
            UserBrowserTab? same = now?.Tabs.FirstOrDefault(tab => tab.Selected);
            if (now is null || now.Tabs.Count != count || same is null || !same.Shown
                || !string.Equals(same.Title, active.Title, StringComparison.Ordinal))
                return null;
            if (_platform.PostMiddleClick(step.Window, same.X, same.Y))
            {
                step.Boundary.Cross(CancellationToken.None);
                after = await AwaitFrameAsync(step.Window, OneLess, cancellationToken).ConfigureAwait(false);
            }
        }
        return after;
    }

    /// <summary>Closing stopped part way: the tabs seen closed are said; how many are left is not guessed.</summary>
    private static ExternalCapabilityReceipt StoppedClosing(TabStep step, string errorCode, int closed) =>
        ExternalJson.FailureAfterEffect(step.Operation, errorCode, effectObserved: closed > 0) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("action", step.Action);
                writer.WriteNumber("closedTabs", closed);
                writer.WriteString("browser", step.Browser.DisplayName);
                writer.WriteString("authority", FrameAuthority);
                writer.WriteEndObject();
            }),
        };

    /// <summary>A screen down or up with the page's ScrollPattern; the position read back is the proof.</summary>
    private async ValueTask<ExternalCapabilityReceipt> ScrollAsync(TabStep step, CancellationToken cancellationToken)
    {
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserAct scrolled = await _platform.ActAsync(step.Window, step.Action, cancellationToken)
            .ConfigureAwait(false);
        return scrolled.Step switch
        {
            "scrolled" => Done(step, "scrolled", null, position: scrolled.After),
            // Already at that end, or a page that does not scroll: nothing moved, and it is said so.
            "boundary" or "not_scrollable" => ExternalJson.FailureBeforeEffect(step.Operation, ScrollBoundary),
            "unmoved" => ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed),
            _ => ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable),
        };
    }

    /// <summary>
    /// The page's own full-screen button pressed through UI Automation (Blink takes it as the person's click); the
    /// browser window covering its monitor is the proof.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> FullscreenAsync(
        TabStep step, CancellationToken cancellationToken)
    {
        bool coveredBefore = _platform.CoversMonitor(step.Window);
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserAct pressed = await _platform.ActAsync(step.Window, step.Action, cancellationToken)
            .ConfigureAwait(false);
        if (pressed.Step == "fullscreen_control_not_found")
            return ExternalJson.FailureBeforeEffect(step.Operation, FullscreenControlMissing);
        if (pressed.Step != "invoked")
            return ExternalJson.FailureBeforeEffect(step.Operation, PageUnreadable);
        for (int attempt = 0; attempt < FullscreenPolls && !coveredBefore; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            if (_platform.CoversMonitor(step.Window))
                return Done(step, "fullscreen", null);
        }
        return ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed);
    }

    /// <summary>
    /// The tab command by window message, where the browser runs one: Chromium's IDC_* by WM_COMMAND (Chrome, Edge,
    /// Brave, measured 2026-10-06), Firefox's WM_APPCOMMAND. Opera and Opera GX run neither IDC_* (WM_COMMAND or
    /// WM_SYSCOMMAND) nor APPCOMMAND_NEW/CLOSE (measured on Opera GX 2026-10-06): no message is posted and the caller
    /// goes straight to UI Automation or the tab itself, without waiting for a change that will not come.
    /// </summary>
    private bool PostTabCommand(TabStep step, int browserCommand, int appCommand) => step.Browser.Family switch
    {
        "opera" or "opera_gx" => false,
        "firefox" => _platform.PostAppCommand(step.Window, appCommand),
        _ => _platform.PostBrowserCommand(step.Window, browserCommand),
    };

    /// <summary>The frame, read a second time when the first read fails (a fresh UI Automation client).</summary>
    private async ValueTask<UserBrowserFrame?> ReadFrameAsync(nint window, CancellationToken cancellationToken)
    {
        UserBrowserFrame? frame = await _platform.ReadFrameAsync(window, cancellationToken).ConfigureAwait(false);
        if (frame is not null)
            return frame;
        await _platform.DelayAsync(FramePoll, cancellationToken).ConfigureAwait(false);
        return await _platform.ReadFrameAsync(window, cancellationToken).ConfigureAwait(false);
    }

    private async ValueTask<UserBrowserFrame?> AwaitFrameAsync(
        nint window, Func<UserBrowserFrame, bool> changed, CancellationToken cancellationToken)
    {
        for (int attempt = 0; attempt < FrameReads; attempt++)
        {
            await _platform.DelayAsync(FramePoll, cancellationToken).ConfigureAwait(false);
            UserBrowserFrame? frame = await _platform.ReadFrameAsync(window, cancellationToken).ConfigureAwait(false);
            if (frame is not null && changed(frame))
                return frame;
        }
        return null;
    }

    private static System.Text.Json.JsonElement TabsClosed(TabStep step, int closed, UserBrowserFrame frame) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("action", step.Action);
            writer.WriteString("observedState", closed > 0 ? "tabs_closed" : "nothing_to_close");
            writer.WriteString("browser", step.Browser.DisplayName);
            writer.WriteNumber("closedTabs", closed);
            writer.WriteNumber("tabCount", frame.Tabs.Count);
            if (frame.Tabs.FirstOrDefault(tab => tab.Selected) is { } active)
                writer.WriteString("activeTab", active.Title);
            writer.WriteString("authority", FrameAuthority);
            writer.WriteEndObject();
        });

    private static ExternalCapabilityReceipt Done(
        TabStep step,
        string observedState,
        UserBrowserFrame? frame,
        string? closed = null,
        double? position = null) =>
        ExternalJson.Success(step.Operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("action", step.Action);
            writer.WriteString("observedState", observedState);
            writer.WriteString("browser", step.Browser.DisplayName);
            if (frame is not null)
            {
                writer.WriteNumber("tabCount", frame.Tabs.Count);
                if (frame.Tabs.FirstOrDefault(tab => tab.Selected) is { } active)
                    writer.WriteString("activeTab", active.Title);
            }
            if (closed is not null)
                writer.WriteString("closedTab", closed);
            if (position is { } percent)
                writer.WriteNumber("scrollPercent", Math.Round(percent, 1));
            writer.WriteString("authority", FrameAuthority);
            writer.WriteEndObject();
        }));
}
