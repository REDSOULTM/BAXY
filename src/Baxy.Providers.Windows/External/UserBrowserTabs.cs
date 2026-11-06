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
    // Uso real 03-11 (U53): a tab named to be closed (browser.control's «tab»): none of the strip's titles bears it,
    // several do, it is not on screen to be clicked, or the tab that went is not that one.
    internal const string TabNotFound = "user_browser_tab_not_found";
    internal const string TabAmbiguous = "user_browser_tab_ambiguous";
    internal const string TabNotShown = "user_browser_tab_not_shown";
    internal const string OtherTabClosed = "user_browser_other_tab_closed";
    internal const string TabNameNeedsClose = "browser_control_tab_needs_close_or_switch";
    // Uso real 03-11 (U64): a request to go to a named tab had no action that goes to a tab (the model took close).
    internal const string SwitchNeedsTab = "browser_control_switch_tab_needs_tab";

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
        string? tab,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (action is not ("back" or "close" or "close_all" or "fullscreen_video" or "exit_fullscreen" or "new_tab"
            or "reload" or "scroll_down" or "scroll_up" or "switch_tab"))
            return ExternalJson.Failure(operation, "browser_control_action_invalid");
        // Only a single close and a switch take a tab: any other step acts on the active tab, so a name would be ignored.
        if (tab is not null && action is not ("close" or "switch_tab"))
            return ExternalJson.FailureBeforeEffect(operation, TabNameNeedsClose);
        if (tab is null && action == "switch_tab")
            return ExternalJson.FailureBeforeEffect(operation, SwitchNeedsTab);
        (UserBrowserWindow? window, _, _) = await TabbedWindowAsync(browser, cancellationToken).ConfigureAwait(false);
        if (window is null)
            return NotRunning(operation, browser);
        var step = new TabStep(operation, browser, action, window.Handle, effectBoundary, tab);
        return action switch
        {
            "back" => await HistoryStepAsync(step, AppCommandBack, cancellationToken).ConfigureAwait(false),
            "reload" => await HistoryStepAsync(step, AppCommandRefresh, cancellationToken).ConfigureAwait(false),
            "new_tab" => await NewTabAsync(step, cancellationToken).ConfigureAwait(false),
            "close" => await CloseTabAsync(step, cancellationToken).ConfigureAwait(false),
            "close_all" => await CloseAllTabsAsync(step, cancellationToken).ConfigureAwait(false),
            "switch_tab" => await SwitchTabAsync(step, cancellationToken).ConfigureAwait(false),
            "fullscreen_video" => await FullscreenAsync(step, cancellationToken).ConfigureAwait(false),
            "exit_fullscreen" => await ExitFullscreenAsync(step, cancellationToken).ConfigureAwait(false),
            _ =>await ScrollAsync(step, cancellationToken).ConfigureAwait(false),
        };
    }

    private readonly record struct TabStep(
        string Operation,
        UserBrowserIdentity Browser,
        string Action,
        nint Window,
        ExternalEffectBoundary Boundary,
        string? Tab = null);

    /// <summary>
    /// Back and reload: WM_APPCOMMAND, which Chromium (Opera GX included, measured 2026-10-06) runs on the active tab.
    /// Going back is seen as another page document or address; reloading, as a new document of the same page.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> HistoryStepAsync(
        TabStep step, int command, CancellationToken cancellationToken)
    {
        // Auditoría final (regla 3): back and reload compare page and address only between frames read whole, so an
        // address or a page document a partial read missed is never taken for the change.
        // FT/proveedores goal (E3): a frame with its strip whole but a node unread elsewhere (Opera GX's dead
        // LiveBackgroundView child) is compared by its page document only when that document is the one named as the
        // window title begins (the active tab's page, not one a partial read put in its place); its address, never.
        UserBrowserFrame? before = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (before is null || before.PageId.Length == 0 || !PageKnown(before))
            return PageNotShown(step.Operation, step.Browser);
        bool back = command == AppCommandBack;
        if (back && before.BackEnabled == false)
            return FirstPage(step, before);
        if (!_platform.PostAppCommand(step.Window, command))
            return ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserFrame? after = await AwaitFrameAsync(
            step.Window,
            frame => frame.TabsComplete && (frame.PageId.Length > 0 && frame.PageId != before.PageId && PageKnown(frame)
                || back && before.Complete && frame.Complete && frame.Address.Length > 0 && frame.Address != before.Address),
            cancellationToken).ConfigureAwait(false);
        return after is null
            ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
            : Done(step, back ? "went_back" : "reloaded", after);
    }

    /// <summary>
    /// Uso real 05-11 (C2040): «go through my courses» went back until the tab had no earlier page, then back again, also
    /// after a click on a course that had opened nothing, and the reply was that it could not go on. The code alone said
    /// nothing of where the tab is: the page it stays on, which also tells whether a click before it opened anything, and
    /// how what that page shows is opened.
    /// </summary>
    private static ExternalCapabilityReceipt FirstPage(TabStep step, UserBrowserFrame frame) =>
        !Infrastructure.ModelAids.On(Infrastructure.ModelAids.HistoryStartNext)
            || frame.Tabs.FirstOrDefault(tab => tab.Selected) is not { } active
            ? ExternalJson.FailureBeforeEffect(step.Operation, HistoryStart)
            : ExternalJson.FailureBeforeEffect(step.Operation, HistoryStart) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("action", step.Action);
                    writer.WriteString("browser", step.Browser.DisplayName);
                    writer.WriteString("activeTab", active.Title);
                    var look = new System.Text.Json.Nodes.JsonObject { ["application"] = step.Browser.ProcessName };
                    writer.WriteString("next", "this tab has no earlier page: it is on its first page (activeTab), and "
                        + "going back again gives the same; to open something that page shows, call "
                        + $"{Baxy.Kernel.Operations.WireNames.Call("input.visible.controls", look)}, then "
                        + $"{Baxy.Kernel.Operations.WireNames.Of("input.visible.click")} on it");
                    writer.WriteEndObject();
                }),
            };

    /// <summary>
    /// A new tab: Chromium's IDC_NEW_TAB by message; a browser that does not run it (Opera GX, or a message read back
    /// with as many tabs as before) gets its tab strip's new-tab button pressed through UI Automation. Seen as one tab
    /// more.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> NewTabAsync(TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (before is null)
            return PageNotShown(step.Operation, step.Browser);
        int count = before.Tabs.Count;
        bool OneMore(UserBrowserFrame frame) => frame.TabsComplete && frame.Tabs.Count > count;
        if (PostTabCommand(step, BrowserCommandNewTab, AppCommandNew))
        {
            step.Boundary.Cross(CancellationToken.None);
            // A tab the message opened late is said; the button is pressed only when no message could be posted.
            UserBrowserFrame? now = await AwaitFrameAsync(step.Window, OneMore, cancellationToken).ConfigureAwait(false)
                ?? await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
            if (now is not null && OneMore(now))
                return Done(step, "tab_opened", now);
            // Ronda final 42 (regla: doble pulsación): the posted message may still run; the button is not pressed too.
            return ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed);
        }
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserAct pressed = await _platform.ActAsync(step.Window, "new_tab", cancellationToken)
            .ConfigureAwait(false);
        UserBrowserFrame? after = pressed.Step == "invoked"
            ? await AwaitFrameAsync(step.Window, OneMore, cancellationToken).ConfigureAwait(false)
            : null;
        return after is null
            ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
            : Done(step, "tab_opened", after);
    }

    /// <summary>
    /// The active tab, or the one named (<see cref="TabStep.Tab"/>): the active one by Chromium's IDC_CLOSE_TAB by
    /// message, else a middle click posted on that tab (what closes a tab in every Chromium browser, Opera GX measured;
    /// Chromium's Tab::OnMouseReleased closes the tab a middle button is released over); another tab, by that middle
    /// click on it, without selecting it. The last tab is kept: closing it closes the person's window. Seen as one tab
    /// less with that very tab gone from the strip read after (<see cref="TabGone"/>), which also gives the tabs left.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> CloseTabAsync(TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
        UserBrowserTab? active = before?.Tabs.FirstOrDefault(tab => tab.Selected);
        if (before is null || active is null)
            return PageNotShown(step.Operation, step.Browser);
        UserBrowserTab target = active;
        if (step.Tab is { } named)
        {
            // Uso real 03-11 (U53): the tab is the one whose title bears the name said, compared by form only (whole
            // words, case and accents aside); none or several close nothing and give the titles read.
            UserBrowserTab[] bearing = [.. before.Tabs.Where(tab => TitleBears(tab.Title, named))];
            if (bearing.Length != 1)
                return NamedTabRefused(step, bearing.Length == 0 ? TabNotFound : TabAmbiguous, before, bearing);
            target = bearing[0];
            if (!target.Selected && !target.Shown)
                return NamedTabRefused(step, TabNotShown, before, bearing);
        }

        if (before.Tabs.Count <= 1)
            return ExternalJson.FailureBeforeEffect(step.Operation, LastTabKept);
        UserBrowserFrame? after = target.Selected
            ? (await CloseActiveTabAsync(step, before, active, cancellationToken).ConfigureAwait(false)).After
            : await CloseShownTabAsync(step, before, target, cancellationToken).ConfigureAwait(false);
        if (after is null)
            return step.Boundary.WasCrossed
                ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
                : ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        // One tab less is not yet the tab asked for: that tab must be the one gone. Another gone is said as it is.
        string[] gone = Gone(before, after);
        if (TabGone(before, after, target))
            return Done(step, "tab_closed", after, closed: target.Title, remaining: true);
        return ExternalJson.FailureAfterEffect(step.Operation, OtherTabClosed, effectObserved: true) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("action", step.Action);
                writer.WriteString("browser", step.Browser.DisplayName);
                if (step.Tab is not null) writer.WriteString("requestedTab", step.Tab);
                writer.WriteString("targetTab", target.Title);
                if (gone.Length == 1) writer.WriteString("closedTab", gone[0]);
                WriteTitles(writer, "remainingTabs", after.Tabs);
                if (after.Tabs.FirstOrDefault(tab => tab.Selected) is { } now)
                    writer.WriteString("activeTab", now.Title);
                writer.WriteString("authority", FrameAuthority);
                writer.WriteEndObject();
            }),
        };
    }

    /// <summary>A tab on screen other than the active one, closed by a middle click on it: one tab less, or null.</summary>
    private async ValueTask<UserBrowserFrame?> CloseShownTabAsync(
        TabStep step, UserBrowserFrame before, UserBrowserTab target, CancellationToken cancellationToken)
    {
        int count = before.Tabs.Count;
        if (!_platform.PostMiddleClick(step.Window, target.X, target.Y))
            return null;
        step.Boundary.Cross(CancellationToken.None);
        // Ronda final 43 (regla: doble pulsación): a click not seen may still close the tab late: never clicked again.
        return await AwaitFrameAsync(
            step.Window, frame => frame.TabsComplete && frame.Tabs.Count == count - 1, cancellationToken)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// Whether the title bears the name as whole words, case, accents and punctuation aside («runpod» in «Runpod
    /// Billing»; «run» is not in it). Uso real 03-11 (U64): the ear splits and joins words («Run pod» for «Runpod», «git
    /// hub» for «GitHub»), so the spaces between the words said do not count: the letters said, run together, must be
    /// the letters of whole words of the title run together, from the start of one word to the end of another («run
    /// pod» and «runpod billing» are in «Runpod Billing»; «run», «pod» and «pod billing» are not).
    /// </summary>
    internal static bool TitleBears(string title, string name)
    {
        string said = Fold(name).Replace(" ", string.Empty, StringComparison.Ordinal);
        if (said.Length == 0)
            return false;
        string[] words = Fold(title).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        for (int first = 0; first < words.Length; first++)
        {
            int at = 0;
            for (int word = first; word < words.Length; word++)
            {
                if (at + words[word].Length > said.Length
                    || string.CompareOrdinal(said, at, words[word], 0, words[word].Length) != 0)
                    break;
                at += words[word].Length;
                if (at == said.Length)
                    return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Uso real 03-11 (U64): the tab named made the active one. It is found as a named close finds it (one tab whose
    /// title bears the name; none or several send nothing and give the titles read) and selected through its TabItem's
    /// UI Automation SelectionItemPattern.Select, which deselects the tab selected and selects that one (Microsoft
    /// Learn), without keys or a click (it may bring the browser window to the front: measured so on a WebView2 tab,
    /// CONTRATO_VISTA_ACCION.md). Seen as that very tab, by its runtime id, selected in the strip
    /// read after; the receipt gives the active tab and every other tab as read then. A tab already active is said so,
    /// with nothing sent.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> SwitchTabAsync(TabStep step, CancellationToken cancellationToken)
    {
        UserBrowserFrame? before = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (before is null || !before.Tabs.Any(tab => tab.Selected))
            return PageNotShown(step.Operation, step.Browser);
        UserBrowserTab[] bearing = [.. before.Tabs.Where(tab => TitleBears(tab.Title, step.Tab!))];
        if (bearing.Length != 1)
            return NamedTabRefused(step, bearing.Length == 0 ? TabNotFound : TabAmbiguous, before, bearing);
        UserBrowserTab target = bearing[0];
        if (target.Selected)
            return Switched(step, "already_active", before);
        // The tab is selected by the runtime id read now: a tab without one is not looked for again by title.
        if (target.Id.Length == 0)
            return ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserAct selected = await _platform.SelectTabAsync(step.Window, target.Id, cancellationToken)
            .ConfigureAwait(false);
        // The tab was not found again, or does not take a selection: nothing was selected.
        if (selected.Step is "tab_not_found" or "select_unavailable")
            return ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
        UserBrowserFrame? after = selected.Step == "selected"
            ? await AwaitFrameAsync(
                step.Window,
                frame => frame.TabsComplete && frame.Tabs.FirstOrDefault(tab => tab.Selected) is { } now
                    && (now.Id.Length > 0
                        ? string.Equals(now.Id, target.Id, StringComparison.Ordinal)
                        : string.Equals(now.Title, target.Title, StringComparison.Ordinal)),
                cancellationToken).ConfigureAwait(false)
            : null;
        return after is null
            ? ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed)
            : Switched(step, "tab_selected", after);
    }

    private static ExternalCapabilityReceipt Switched(TabStep step, string observedState, UserBrowserFrame frame) =>
        ExternalJson.Success(step.Operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("action", step.Action);
            writer.WriteString("observedState", observedState);
            writer.WriteString("browser", step.Browser.DisplayName);
            writer.WriteString("requestedTab", step.Tab);
            writer.WriteNumber("tabCount", frame.Tabs.Count);
            writer.WriteString("activeTab", frame.Tabs.First(tab => tab.Selected).Title);
            WriteTitles(writer, "otherTabs", frame.Tabs.Where(tab => !tab.Selected));
            writer.WriteString("authority", FrameAuthority);
            writer.WriteEndObject();
        }));

    /// <summary>
    /// Whether the two reads tell tabs apart by their UI Automation runtime id (every tab of both carries one), which
    /// stays the same while a title changes (Edge's memory use in its active tab's name, a page retitling itself);
    /// otherwise by title.
    /// </summary>
    private static bool ByIdentity(UserBrowserFrame before, UserBrowserFrame after) =>
        before.Tabs.All(tab => tab.Id.Length > 0) && after.Tabs.All(tab => tab.Id.Length > 0);

    private static bool TabGone(UserBrowserFrame before, UserBrowserFrame after, UserBrowserTab target) =>
        ByIdentity(before, after)
            ? after.Tabs.All(tab => !string.Equals(tab.Id, target.Id, StringComparison.Ordinal))
            : TitleCount(before, target.Title) - TitleCount(after, target.Title) == 1;

    private static int TitleCount(UserBrowserFrame frame, string title) =>
        frame.Tabs.Count(tab => string.Equals(tab.Title, title, StringComparison.Ordinal));

    /// <summary>The titles (as read before) of the tabs of the strip before that are not in the strip after.</summary>
    private static string[] Gone(UserBrowserFrame before, UserBrowserFrame after)
    {
        bool byId = ByIdentity(before, after);
        var left = after.Tabs.Select(tab => byId ? tab.Id : tab.Title).ToList();
        var gone = new List<string>();
        foreach (UserBrowserTab tab in before.Tabs)
        {
            if (!left.Remove(byId ? tab.Id : tab.Title))
                gone.Add(tab.Title);
        }
        return [.. gone];
    }

    private static ExternalCapabilityReceipt NamedTabRefused(
        TabStep step, string errorCode, UserBrowserFrame before, UserBrowserTab[] bearing) =>
        ExternalJson.FailureBeforeEffect(step.Operation, errorCode) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("action", step.Action);
                writer.WriteString("browser", step.Browser.DisplayName);
                writer.WriteString("requestedTab", step.Tab);
                if (bearing.Length > 1)
                    WriteTitles(writer, "candidates", bearing);
                WriteTitles(writer, "tabs", before.Tabs);
                writer.WriteString("authority", FrameAuthority);
                writer.WriteEndObject();
            }),
        };

    private static void WriteTitles(System.Text.Json.Utf8JsonWriter writer, string property, IEnumerable<UserBrowserTab> tabs)
    {
        writer.WriteStartArray(property);
        foreach (UserBrowserTab tab in tabs)
            writer.WriteStringValue(tab.Title);
        writer.WriteEndArray();
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
        UserBrowserFrame? frame = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
        if (frame is null || !frame.Tabs.Any(tab => tab.Selected))
            return PageNotShown(step.Operation, step.Browser);
        if (frame.Tabs.Count <= 1)
            return ExternalJson.FailureBeforeEffect(step.Operation, LastTabKept) with
            {
                Result = TabsClosed(step, 0, frame),
            };
        long started = System.Diagnostics.Stopwatch.GetTimestamp();
        int closed = 0;
        var resisting = new HashSet<string>(StringComparer.Ordinal);
        while (frame.Tabs.Count > 1)
        {
            UserBrowserTab? active = frame.Tabs.FirstOrDefault(tab => tab.Selected);
            if (active is null)
                return StoppedClosing(step, PageUnreadable, closed);
            if (closed >= CloseAllTabs || System.Diagnostics.Stopwatch.GetElapsedTime(started) > CloseAllTime)
                return StoppedClosing(step, CloseAllIncomplete, closed);
            (UserBrowserFrame? after, bool pressed) = resisting.Contains(active.Title)
                ? (null, false)
                : await CloseActiveTabAsync(step, frame, active, cancellationToken).ConfigureAwait(false);
            // Rondas finales 42-44 (regla: doble pulsación): a close command or click sent and not seen run may still
            // run: the closing stops unconfirmed, never goes on to click other tabs (a late close would take one too
            // many). Another tab is clicked only when nothing at all was sent for the active one.
            if (after is null && pressed)
                return StoppedClosing(step, TabStepUnconfirmed, closed);
            if (after is null)
            {
                // Measured on Opera GX: its «GX Corner» tab did not close as the active tab. Another tab on screen
                // is closed instead, by the middle click that closes any tab of a Chromium strip without selecting it.
                resisting.Add(active.Title);
                after = await CloseAnotherTabAsync(step, frame, resisting, cancellationToken).ConfigureAwait(false);
            }

            if (after is null)
                return step.Boundary.WasCrossed
                    ? StoppedClosing(step, TabStepUnconfirmed, closed)
                    : ExternalJson.FailureBeforeEffect(step.Operation, TabStepUnavailable);
            closed++;
            frame = after;
        }
        return ExternalJson.Success(step.Operation, TabsClosed(step, closed, frame));
    }

    /// <summary>A shown tab other than the ones that resisted, closed by a middle click: one tab less, or null.</summary>
    private async ValueTask<UserBrowserFrame?> CloseAnotherTabAsync(
        TabStep step, UserBrowserFrame before, HashSet<string> resisting, CancellationToken cancellationToken)
    {
        int count = before.Tabs.Count;
        foreach (UserBrowserTab other in before.Tabs.Where(tab => !tab.Selected && tab.Shown && !resisting.Contains(tab.Title)).Reverse())
        {
            if (!_platform.PostMiddleClick(step.Window, other.X, other.Y))
                continue;
            step.Boundary.Cross(CancellationToken.None);
            UserBrowserFrame? after = await AwaitFrameAsync(
                step.Window, frame => frame.TabsComplete && frame.Tabs.Count == count - 1, cancellationToken)
                .ConfigureAwait(false);
            // Ronda final 43 (regla: doble pulsación): a click not seen may still close that tab late: no other tab is
            // clicked after it (the closing stops unconfirmed).
            return after;
        }

        return null;
    }

    /// <summary>
    /// Closes the active tab of <paramref name="before"/>: the frame read with one tab less, or null when none was
    /// seen (the step's boundary says whether anything was posted), and whether a close command or click was sent.
    /// </summary>
    private async ValueTask<(UserBrowserFrame? After, bool Pressed)> CloseActiveTabAsync(
        TabStep step, UserBrowserFrame before, UserBrowserTab active, CancellationToken cancellationToken)
    {
        int count = before.Tabs.Count;
        bool OneLess(UserBrowserFrame frame) => frame.TabsComplete && frame.Tabs.Count == count - 1;
        UserBrowserFrame? after = null;
        if (PostTabCommand(step, BrowserCommandCloseTab, AppCommandClose))
        {
            step.Boundary.Cross(CancellationToken.None);
            // Ronda final 42 (regla: doble pulsación): a command posted and not seen run may still run (a busy browser
            // answers the reads first): it is said unconfirmed, never followed by a click that would close the next tab.
            return (await AwaitFrameAsync(step.Window, OneLess, cancellationToken).ConfigureAwait(false), true);
        }
        {
            // The message was not run: the click goes only to the same tab, still active and still on screen.
            UserBrowserFrame? now = await ReadTabsAsync(step.Window, cancellationToken).ConfigureAwait(false);
            UserBrowserTab? same = now?.Tabs.FirstOrDefault(tab => tab.Selected);
            if (now is null || now.Tabs.Count != count || same is null || !same.Shown
                || !string.Equals(same.Title, active.Title, StringComparison.Ordinal))
                return (null, false);
            if (_platform.PostMiddleClick(step.Window, same.X, same.Y))
            {
                step.Boundary.Cross(CancellationToken.None);
                return (await AwaitFrameAsync(step.Window, OneLess, cancellationToken).ConfigureAwait(false), true);
            }
        }
        return (after, false);
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
            "page_not_found" => PageNotShown(step.Operation, step.Browser),
            // Not seen moving, or UI Automation (or the script's deadline) failing, possibly after the scroll was sent.
            _ => ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed),
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
        if (pressed.Step == "page_not_found")
            return PageNotShown(step.Operation, step.Browser);
        // UI Automation (or the script's deadline) failing, possibly after the button was pressed.
        if (pressed.Step != "invoked")
            return ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed);
        for (int attempt = 0; attempt < FullscreenPolls && !coveredBefore; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            if (_platform.CoversMonitor(step.Window))
                return Done(step, "fullscreen", null);
        }
        return ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed);
    }

    /// <summary>
    /// Uso real 2026-10-21: «sal de pantalla completa» had no action (the model chose close, which reads the tab strip a
    /// full-screen window does not show). The page's own exit button pressed through UI Automation, as the full-screen one
    /// is; the window no longer covering its monitor is the proof. A window that does not cover it is left as it is.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> ExitFullscreenAsync(
        TabStep step, CancellationToken cancellationToken)
    {
        if (!_platform.CoversMonitor(step.Window))
            return Done(step, "windowed", null);
        step.Boundary.Cross(CancellationToken.None);
        UserBrowserAct pressed = await _platform.ActAsync(step.Window, step.Action, cancellationToken)
            .ConfigureAwait(false);
        if (pressed.Step == "fullscreen_control_not_found")
            return ExternalJson.FailureBeforeEffect(step.Operation, FullscreenControlMissing);
        if (pressed.Step == "page_not_found")
            return PageNotShown(step.Operation, step.Browser);
        if (pressed.Step != "invoked")
            return ExternalJson.FailureAfterEffect(step.Operation, TabStepUnconfirmed);
        for (int attempt = 0; attempt < FullscreenPolls; attempt++)
        {
            await _platform.DelayAsync(Poll, cancellationToken).ConfigureAwait(false);
            if (!_platform.CoversMonitor(step.Window))
                return Done(step, "windowed", null);
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

    // Auditoría final (regla 3): a tab step counts tabs only on a strip read whole (UserBrowserFrame.TabsComplete): a tab
    // that could not be read is never «the last tab», «nothing to close», «one tab less» or «one tab more».
    private async ValueTask<UserBrowserFrame?> ReadTabsAsync(nint window, CancellationToken cancellationToken)
    {
        UserBrowserFrame? frame = await ReadFrameAsync(window, cancellationToken).ConfigureAwait(false);
        if (frame is null or { TabsComplete: true })
            return frame;
        await _platform.DelayAsync(FramePoll, cancellationToken).ConfigureAwait(false);
        frame = await _platform.ReadFrameAsync(window, cancellationToken).ConfigureAwait(false);
        return frame is { TabsComplete: true } ? frame : null;
    }

    private static bool PageKnown(UserBrowserFrame frame) => frame.Complete || frame.PageMatched;

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
            if (frame.TabsComplete) writer.WriteNumber("tabCount", frame.Tabs.Count);
            else writer.WriteBoolean("tabsComplete", false);
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
        double? position = null,
        bool remaining = false) =>
        ExternalJson.Success(step.Operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("action", step.Action);
            writer.WriteString("observedState", observedState);
            writer.WriteString("browser", step.Browser.DisplayName);
            if (step.Tab is not null) writer.WriteString("requestedTab", step.Tab);
            if (frame is not null)
            {
                // Auditoría final (regla 3): the count only from a strip read whole (back and reload read it as it was).
                if (frame.TabsComplete) writer.WriteNumber("tabCount", frame.Tabs.Count);
                else writer.WriteBoolean("tabsComplete", false);
                // FT/proveedores goal (E3): the strip was read whole, the rest of the frame was not: said.
                if (!frame.Complete) writer.WriteBoolean("frameComplete", false);
                if (frame.Tabs.FirstOrDefault(tab => tab.Selected) is { } active)
                    writer.WriteString("activeTab", active.Title);
            }
            if (closed is not null)
                writer.WriteString("closedTab", closed);
            // Uso real 03-11 (U53): every tab left, as the strip read after shows them, beside the one that went.
            if (remaining && frame is { TabsComplete: true })
                WriteTitles(writer, "remainingTabs", frame.Tabs);
            if (position is { } percent)
                writer.WriteNumber("scrollPercent", Math.Round(percent, 1));
            writer.WriteString("authority", FrameAuthority);
            writer.WriteEndObject();
        }));
}
