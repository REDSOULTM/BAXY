using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

internal interface IVisibleControlLocator
{
    string Stage { get; }

    ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        CancellationToken cancellationToken);
}

// The application app.open brought up moments ago, if any: a click right after an opening acts on it.
internal interface IOpenedApplicationFocus
{
    VisibleControlSurface.OpenedApplication? TakeOpened();

    VisibleControlSurface.OpenedApplication? PeekOpened();

    // The opened application's main window, brought to the front (none yet: Window 0), and whether it looks drawn
    // (judged only when asked; otherwise drawn).
    ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken);

    // That window is still the one in front: the UI Automation stage reads the window in front.
    bool Holds(nint window);
}

internal sealed class OpenedApplicationFocus : IOpenedApplicationFocus
{
    // A click asked in the same breath as the opening, or answered after its confirmation, comes well inside this.
    private static readonly TimeSpan Freshness = TimeSpan.FromSeconds(90);

    public VisibleControlSurface.OpenedApplication? TakeOpened() =>
        VisibleControlSurface.TakeOpened(Freshness);

    public VisibleControlSurface.OpenedApplication? PeekOpened() =>
        VisibleControlSurface.PeekOpened(Freshness);

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken) =>
        VisibleControlSurface.FrontOpenedAsync(opened, judgeDrawn, cancellationToken);

    public bool Holds(nint window) => VisibleControlSurface.ForegroundIs(window);
}

internal sealed class NoOpenedApplicationFocus : IOpenedApplicationFocus
{
    public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

    public VisibleControlSurface.OpenedApplication? PeekOpened() => null;

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken) => ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));

    public bool Holds(nint window) => true;
}

// The person's browser when a mission names «the browser» without naming one (a tab spoken of in passing): the front
// window of their default browser, the window browser.control and browser.tabs.list act on; 0 when it is not running.
internal interface IUserBrowserWindowLocator
{
    nint FrontWindow();

    // «navegador», «el navegador», «mi navegador», «browser», «my browser», «web browser»: the category, not a product.
    internal static bool NamesTheCategory(string? application)
    {
        string[] words = VisibleControlSurface.FoldTitle(application).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        int start = words.Length > 1 && words[0] is "el" or "mi" or "tu" or "su" or "the" or "my" or "your" ? 1 : 0;
        return string.Join(' ', words[start..]) is "navegador" or "navegador web" or "browser" or "web browser";
    }
}

internal sealed class NoUserBrowserWindow : IUserBrowserWindowLocator
{
    public nint FrontWindow() => 0;
}

// How long a click looks for its label. M132 (owner script t42 «En … ve a crash bandicoot», 28 s for «no hay ningún
// elemento visible con ese nombre»): a label is waited on only while the surface may still be drawing — an
// application opened moments ago — and then for a bounded stretch once its window is up; on a window that was
// already there, a second look settles it and the honest «not there» comes at once.
// The post-read of a pressed control: its UIA state is asked every PostreadPeriod for ControlPostread; its window is
// captured from SurfaceFirstSample on, up to SurfacePostread when nothing has settled earlier.
internal sealed record VisibleClickTiming(
    TimeSpan LaunchSurface,
    TimeSpan ReusedSurface,
    TimeSpan OpenedLabel,
    TimeSpan SettledLabel,
    TimeSpan Interval,
    TimeSpan PostreadPeriod,
    TimeSpan ControlPostread,
    TimeSpan SurfaceFirstSample,
    TimeSpan SurfacePostread)
{
    internal static VisibleClickTiming Default { get; } = new(
        LaunchSurface: TimeSpan.FromSeconds(30),
        ReusedSurface: TimeSpan.FromSeconds(5),
        OpenedLabel: TimeSpan.FromSeconds(10),
        SettledLabel: TimeSpan.FromSeconds(3),
        Interval: TimeSpan.FromMilliseconds(1500),
        PostreadPeriod: TimeSpan.FromMilliseconds(50),
        ControlPostread: TimeSpan.FromMilliseconds(500),
        SurfaceFirstSample: TimeSpan.FromMilliseconds(150),
        SurfacePostread: TimeSpan.FromMilliseconds(1500));

    // r8: between two looks for a label on a window that was already there, the window is sampled every StillSample;
    // one that did not change at all for StillFor is not drawing anything new, so the label that no stage found will
    // not appear and «not found» is answered then instead of after the whole SettledLabel stretch (measured on ~50
    // live missions: 13 such clicks at 4.2–4.4 s each).
    internal TimeSpan StillSample { get; init; } = TimeSpan.FromMilliseconds(200);
    internal TimeSpan StillFor { get; init; } = TimeSpan.FromMilliseconds(750);
}

/// <summary>
/// Perception and the click of the computer-use engine
/// (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §1, §2).
/// <c>input.visible.controls</c> is the compact view of the foreground window:
/// up to sixty actionable controls with index, kind, label, state, rectangle,
/// zone and dominant colour, the written text by zone (OCR), the window's
/// title and process. <c>input.visible.click</c> invokes one control by label
/// or by the identity the view handed out, through the persistent UIA worker,
/// then OCR, then vision, and demands a post-read.
/// </summary>
internal sealed class WindowsVisibleControlAdapter : IExternalOperationAdapter, IDisposable
{
    private static readonly HashSet<string> CascadeAfter = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
        "visible_button_uia_failed",
        "visible_click_no_receipt",
        "active_window_not_found",
    };

    // H0096 «aprieta en Among Us»: el worker sólo emite este código después de
    // recorrer el árbol y los botones nativos y no encontrar nada con ese
    // nombre, es decir, antes de tocar nada. Marcarlo como «pudo haber efecto»
    // sólo porque la frontera se cruza al arrancar convertía una ausencia
    // medida en una duda, y el turno la contaba como un resultado sin
    // confirmar en vez de decir que ahí no había nada así.
    private static readonly HashSet<string> BeforeAnyPress = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
        "visible_control_identity_stale",
        "visible_control_label_mismatch",
        "visible_click_argument_invalid",
    };

    private static readonly TimeSpan LabelWaitBudget = TimeSpan.FromSeconds(24);
    private static readonly TimeSpan LabelWaitInterval = TimeSpan.FromMilliseconds(1500);
    private static readonly TimeSpan WorkerViewBudget = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan WorkerClickBudget = TimeSpan.FromSeconds(15);

    private readonly IUiaWorker _worker;
    private readonly IVisibleControlLocator? _ocr;
    private readonly IVisibleControlLocator? _vision;
    private readonly IOpenedApplicationFocus _focus;
    private readonly VisibleClickTiming _timing;
    private readonly IUserBrowserWindowLocator _browserWindow;
    private readonly Func<CancellationToken, ValueTask<string?>>? _surfaceHash;
    private readonly object _viewLock = new();
    private LastView? _lastView;

    internal WindowsVisibleControlAdapter()
        : this(
            new UiaWorkerHost(),
            new WindowsVisibleOcrLocator(),
            new WindowsVisibleVisionLocator(),
            new OpenedApplicationFocus(),
            VisibleClickTiming.Default,
            new UserBrowserSurface(new WindowsUserBrowserPlatform()),
            ForegroundSurfaceHashAsync)
    {
    }

    internal WindowsVisibleControlAdapter(
        IUiaWorker worker,
        IVisibleControlLocator? ocr,
        IVisibleControlLocator? vision,
        IOpenedApplicationFocus? focus = null,
        VisibleClickTiming? timing = null,
        IUserBrowserWindowLocator? browserWindow = null,
        Func<CancellationToken, ValueTask<string?>>? surfaceHash = null)
    {
        _worker = worker ?? throw new ArgumentNullException(nameof(worker));
        _surfaceHash = surfaceHash;
        _ocr = ocr;
        _vision = vision;
        _focus = focus ?? new NoOpenedApplicationFocus();
        _timing = timing ?? VisibleClickTiming.Default;
        _browserWindow = browserWindow ?? new NoUserBrowserWindow();
    }

    public bool CanHandle(string operation) =>
        operation is "input.visible.click" or "input.visible.controls";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "input.visible.controls")
            return await ListAsync(operation, arguments, cancellationToken).ConfigureAwait(false);

        string label;
        int? index = null;
        string? controlId = null;
        try
        {
            label = ExternalJson.RequiredString(arguments, "label").Trim();
            if (arguments.TryGetProperty("index", out JsonElement indexValue)
                && indexValue.ValueKind == JsonValueKind.Number
                && indexValue.TryGetInt32(out int requestedIndex))
            {
                index = requestedIndex;
            }

            if (arguments.TryGetProperty("controlId", out JsonElement identity)
                && identity.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(identity.GetString()))
            {
                controlId = identity.GetString()!.Trim();
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "visible_click_argument_invalid");
        }

        // The engine clicks by the identity the last view handed out. The
        // index is resolved against that view, and the label must name the
        // same control: an index that drifted is refused, never clicked.
        if (index is int position && controlId is null)
        {
            LastView? view;
            lock (_viewLock)
            {
                view = _lastView;
            }

            ViewControl? chosen = view?.Controls.FirstOrDefault(control => control.Index == position);
            if (chosen is null)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            if (!LabelNames(label, chosen.Name))
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_label_mismatch");
            controlId = chosen.Id.Length > 0 ? chosen.Id : null;
            if (controlId is null && !LabelNames(label, chosen.Name))
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        }

        if (controlId is not null)
        {
            ExternalCapabilityReceipt identified = await InvokeUiaAsync(
                operation, label, controlId, 0, cancellationToken).ConfigureAwait(false);
            if (identified.ErrorCode != "visible_control_identity_stale")
            {
                // A control of the view pressed by its identity: the application opened is drawn and answering, so a
                // later click by label does not wait for it to finish opening. v2-u3 «abrí Fotos y andá a Carpetas»:
                // the search field was pressed by identity 2 s after the opening, and the next click by label still
                // waited 26 s for the dark gallery to stop looking blank.
                if (identified.EffectObserved)
                    _ = _focus.TakeOpened();
                return identified;
            }
            // The control moved or was redrawn since the view: the ordinary
            // cascade by label, which is what the reviewer saw, takes over.
        }

        // UI1731 → UI1735: an application that was just opened draws its
        // interface over several seconds (the Epic Games Launcher shows its
        // navigation about ten seconds after its window exists). A label that
        // no stage finds yet is looked for again, bounded, before the click is
        // declared not found — the way a person waits for a screen to load.
        // M132: that wait belongs to the application just opened, on its own
        // window. Its window is waited for (a client that updates itself shows
        // only a small updater at first) and, when it was launched now, its
        // page is waited on until it is drawn — nothing is looked at or pressed
        // meanwhile; then the label for a bounded stretch on each new main
        // window. Any other click looks two or three times and answers.
        VisibleControlSurface.OpenedApplication? opened = _focus.TakeOpened();
        nint surfaceWindow = 0;
        DateTime? lookingSince = null;
        ExternalCapabilityReceipt? uia = null;
        TimeSpan labelBudget = opened is null ? _timing.SettledLabel : _timing.OpenedLabel;
        DateTime settled = opened is { } noted
            ? noted.NotedUtc + (noted.Launched ? _timing.LaunchSurface : _timing.ReusedSurface)
            : DateTime.MinValue;
        // Whatever happens to the opened application's windows, the click ends by here.
        DateTime cap = (settled > DateTime.UtcNow ? settled : DateTime.UtcNow) + labelBudget;
        while (true)
        {
            bool look = true;
            if (opened is { } application)
            {
                VisibleControlSurface.OpenedSurface surface = await _focus.FrontAsync(
                    application, judgeDrawn: application.Launched, cancellationToken).ConfigureAwait(false);
                if (surface.Window != 0 && surface.Window != surfaceWindow)
                {
                    // A login window replaced by the main one is a new surface: its label gets its own wait.
                    surfaceWindow = surface.Window;
                    lookingSince = null;
                }
                bool settling = DateTime.UtcNow < settled;
                look = surface.Window != 0 && (surface.Drawn || !settling);
                if (!look && !settling && lookingSince is null)
                    break;
                if (DateTime.UtcNow >= cap)
                    break;
            }

            if (look)
            {
                lookingSince ??= DateTime.UtcNow;
                // Bound to the opened application's window: if the front moved
                // elsewhere (the person took it), nothing is read or pressed there.
                using IDisposable bound = VisibleControlSurface.RequireWindow(
                    opened is null ? 0 : surfaceWindow);
                uia = opened is null || _focus.Holds(surfaceWindow)
                    ? await InvokeUiaAsync(
                        operation, label, null, opened is null ? 0 : surfaceWindow, cancellationToken)
                        .ConfigureAwait(false)
                    : ExternalJson.FailureBeforeEffect(operation, "visible_button_not_found");
                if (ShouldKeep(uia))
                    return uia;

                if (_ocr is not null)
                {
                    ExternalCapabilityReceipt? ocr = await _ocr.TryClickAsync(
                        operation, label, cancellationToken).ConfigureAwait(false);
                    if (ocr is not null && ShouldKeep(ocr))
                        return ocr;
                    if (ocr is not null && !ShouldCascade(ocr))
                        return ocr;
                }

                if (_vision is not null)
                {
                    ExternalCapabilityReceipt? vision = await _vision.TryClickAsync(
                        operation, label, cancellationToken).ConfigureAwait(false);
                    if (vision is not null)
                        return vision;
                }
            }

            // UI1765: a cascade answer («not found yet», no accessible tree)
            // is worth waiting on; any other error (no surface, no window,
            // cancelled) ends the wait.
            if ((look && uia?.ErrorCode is { } code && !CascadeAfter.Contains(code))
                || (lookingSince is { } since && DateTime.UtcNow >= since + labelBudget))
                break;
            if (opened is null && _surfaceHash is not null)
            {
                // A window that was already there and stays still is not drawing the label: answer now. One that
                // changes is looked at again at once.
                if (await StaysStillAsync(_surfaceHash, cancellationToken).ConfigureAwait(false))
                    break;
                continue;
            }
            await Task.Delay(_timing.Interval, cancellationToken).ConfigureAwait(false);
        }

        // Nothing looked at means nothing pressed: no window of the opened application ever showed.
        if (uia is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_button_not_found");
        return uia.ErrorCode is null
            ? ExternalJson.Failure(operation, "visible_button_not_found")
            : uia;
    }

    // Watches the window in front for up to Interval: true when it stayed exactly the same for StillFor, false as soon
    // as it changes, when it cannot be captured (then the whole interval is waited, as before) or at the interval.
    private async ValueTask<bool> StaysStillAsync(
        Func<CancellationToken, ValueTask<string?>> surfaceHash,
        CancellationToken cancellationToken)
    {
        var watch = Stopwatch.StartNew();
        string? first = await surfaceHash(cancellationToken).ConfigureAwait(false);
        if (first is null)
        {
            TimeSpan rest = _timing.Interval - watch.Elapsed;
            if (rest > TimeSpan.Zero)
                await Task.Delay(rest, cancellationToken).ConfigureAwait(false);
            return false;
        }

        var still = Stopwatch.StartNew();
        while (watch.Elapsed < _timing.Interval)
        {
            await Task.Delay(_timing.StillSample, cancellationToken).ConfigureAwait(false);
            string? now = await surfaceHash(cancellationToken).ConfigureAwait(false);
            if (now is null || !string.Equals(now, first, StringComparison.Ordinal))
                return false;
            if (still.Elapsed >= _timing.StillFor)
                return true;
        }

        return false;
    }

    private static async ValueTask<string?> ForegroundSurfaceHashAsync(CancellationToken cancellationToken) =>
        (await VisibleControlSurface.CaptureForegroundAsync(cancellationToken).ConfigureAwait(false))?.Sha256;

    // ---------------------------------------------------------------- view

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = 60;
        bool includeText = false;
        string? waitForLabel = null;
        int processId = 0;
        string? application = null;
        if (arguments.ValueKind == JsonValueKind.Object)
        {
            if (arguments.TryGetProperty("application", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(named.GetString()))
            {
                application = named.GetString()!.Trim();
            }

            if (arguments.TryGetProperty("processId", out JsonElement owner)
                && owner.ValueKind == JsonValueKind.Number
                && owner.TryGetInt32(out int requestedProcess) && requestedProcess > 0)
            {
                processId = requestedProcess;
            }

            if (arguments.TryGetProperty("limit", out JsonElement requested)
                && requested.ValueKind == JsonValueKind.Number
                && requested.TryGetInt32(out int value))
            {
                limit = Math.Clamp(value, 1, 60);
            }

            includeText = arguments.TryGetProperty("includeText", out JsonElement wantsText)
                && wantsText.ValueKind == JsonValueKind.True;
            if (arguments.TryGetProperty("waitForLabel", out JsonElement waited)
                && waited.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(waited.GetString()))
            {
                waitForLabel = waited.GetString()!.Trim();
            }
        }

        // M132: a look right after an opening reads the application opened, not what was in front before it. A look
        // bound to the mission's process reads and fronts that process's window whatever is in front, so the opened
        // application is not fronted first (about 275 ms on every view of a mission, measured).
        if (processId == 0 && _focus.PeekOpened() is { } opened)
            _ = await _focus.FrontAsync(opened, judgeDrawn: false, cancellationToken).ConfigureAwait(false);
        DateTime deadline = DateTime.UtcNow + LabelWaitBudget;
        while (true)
        {
            ViewResult view = await BuildViewAsync(limit, includeText, processId, application, cancellationToken)
                .ConfigureAwait(false);
            if (view.Receipt.ErrorCode is not null)
                return view.Receipt;
            if (waitForLabel is null || view.Names.Any(name => LabelNames(waitForLabel, name))
                || DateTime.UtcNow >= deadline)
            {
                return view.Receipt;
            }

            await Task.Delay(LabelWaitInterval, cancellationToken).ConfigureAwait(false);
        }
    }

    private async ValueTask<ViewResult> BuildViewAsync(
        int limit,
        bool includeText,
        int processId,
        string? application,
        CancellationToken cancellationToken)
    {
        const string operation = "input.visible.controls";
        var stopwatch = Stopwatch.StartNew();
        nint hwnd = 0;
        nint cover = 0;
        bool requested = false;
        try
        {
            // «The browser» without a name is the person's own: the front
            // window of their default browser, whichever of its windows the
            // process holds and whatever is in front.
            bool theBrowser = IUserBrowserWindowLocator.NamesTheCategory(application);
            if (theBrowser)
            {
                hwnd = _browserWindow.FrontWindow();
                if (hwnd != 0 && !VisibleControlSurface.ForegroundIs(hwnd))
                {
                    VisibleControlSurface.BringToFront(hwnd);
                    await Task.Delay(250, cancellationToken).ConfigureAwait(false);
                }
            }

            // The application the mission works on (the one it just opened, or
            // the one named when its process is unknown) is the surface even
            // when another window holds the foreground.
            if (hwnd == 0 && processId > 0)
            {
                hwnd = await VisibleControlSurface.ResolveProcessWindowAsync(processId, cancellationToken)
                    .ConfigureAwait(false);
            }

            // The category is no title: a window whose title says «navegador»
            // is not the person's browser.
            if (hwnd == 0 && application is not null && !theBrowser)
            {
                hwnd = await VisibleControlSurface.ResolveTitledWindowAsync(application, cancellationToken)
                    .ConfigureAwait(false);
            }

            // Whether the window is the mission's application (its process, its
            // title, the person's browser) and not just what holds the front.
            requested = hwnd != 0;
            if (hwnd == 0)
            {
                hwnd = await VisibleControlSurface.ResolveForegroundAsync(cancellationToken)
                    .ConfigureAwait(false);
            }

            // Another process drawn over the window (a fullscreen player, an
            // overlay): one more attempt to bring the window up, then the view
            // says who covers it rather than reading the cover as the surface.
            if (hwnd != 0)
            {
                cover = VisibleControlSurface.CoveringWindow(hwnd);
                if (cover != 0)
                {
                    VisibleControlSurface.BringToFront(hwnd);
                    await Task.Delay(300, cancellationToken).ConfigureAwait(false);
                    cover = VisibleControlSurface.CoveringWindow(hwnd);
                }
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            hwnd = 0;
        }

        if (hwnd == 0)
            return new ViewResult(ExternalJson.Failure(operation, "active_window_not_found"), []);

        string command = new JsonObject
        {
            ["cmd"] = "view",
            ["hwnd"] = hwnd,
            ["limit"] = limit,
        }.ToJsonString();
        // One capture serves the colours, the written text and the surface
        // hash; a window without an accessible tree (CEF, SDL, canvas) is
        // read from what is drawn, the case measured in a game launcher (UI1731).
        // The capture, and the text when it is asked for, are read while the
        // worker walks the accessible tree: they do not wait on each other.
        Task<VisibleControlSurface.CapturedWindow?> captureTask = Task.Run(
            () => CaptureQuietlyAsync(hwnd, cancellationToken), CancellationToken.None);
        Task<WrittenText>? textTask = includeText ? ReadTextAsync(captureTask, limit, cancellationToken) : null;
        JsonDocument? answer = await _worker.SendAsync(command, WorkerViewBudget, cancellationToken)
            .ConfigureAwait(false);
        long uiaMs = stopwatch.ElapsedMilliseconds;
        if (answer is null)
        {
            return new ViewResult(ExternalJson.Failure(operation, "visible_controls_unavailable"), []);
        }

        using (answer)
        {
            JsonElement root = answer.RootElement;
            if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            {
                string code = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() is { Length: > 0 } text
                        ? text
                        : "visible_controls_unavailable";
                return new ViewResult(ExternalJson.Failure(operation, code), []);
            }

            List<ViewControl> controls = ParseControls(root);
            int counted = root.TryGetProperty("controlCount", out JsonElement total)
                && total.ValueKind == JsonValueKind.Number && total.TryGetInt32(out int totalValue)
                    ? totalValue
                    : controls.Count;
            string title = root.TryGetProperty("window", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                    ? named.GetString() ?? string.Empty
                    : string.Empty;
            if (title.Length == 0)
                title = VisibleControlSurface.WindowTitle(hwnd);
            (int ownerProcessId, string processName) = VisibleControlSurface.WindowProcess(hwnd);
            VisibleControlSurface.TryBounds(hwnd, out int left, out int top, out int right, out int bottom);
            var windowRect = new Rect(left, top, right - left, bottom - top);

            VisibleControlSurface.CapturedWindow? captured = await captureTask.ConfigureAwait(false);
            long colorMs = 0;
            long ocrMs = 0;
            Dictionary<string, List<string>> textZones = new(StringComparer.Ordinal);
            string? textAuthority = null;
            var names = new List<string>();
            if (captured is { } capture)
            {
                var colourWatch = Stopwatch.StartNew();
                VisibleControlColors.Assign(capture, controls);
                colorMs = colourWatch.ElapsedMilliseconds;
                // Not asked for, the text is still read when the tree shows nothing to act on.
                if (textTask is null && controls.Count <= 1)
                    textTask = ReadTextAsync(captureTask, limit, cancellationToken);
                if (textTask is not null)
                {
                    (IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines, ocrMs) =
                        await textTask.ConfigureAwait(false);
                    if (lines is not null)
                    {
                        textAuthority = "windows_media_ocr_lines";
                        foreach (WindowsVisibleOcrLocator.LayoutLine line in lines)
                        {
                            string zone = Zone(
                                line.X + line.Width / 2, line.Y + line.Height / 2,
                                new Rect(0, 0, capture.Width, capture.Height));
                            if (!textZones.TryGetValue(zone, out List<string>? bucket))
                            {
                                bucket = [];
                                textZones[zone] = bucket;
                            }

                            bucket.Add(line.Text);
                            names.Add(line.Text);
                        }
                    }
                    else
                    {
                        textAuthority = "unavailable";
                    }
                }
            }

            foreach (ViewControl control in controls)
            {
                control.Zone = control.RectValue is { } rect
                    ? Zone(rect.X + rect.W / 2, rect.Y + rect.H / 2, windowRect)
                    : string.Empty;
                names.Add(control.Name);
            }

            lock (_viewLock)
            {
                _lastView = new LastView(hwnd, controls);
            }

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 2);
                writer.WriteBoolean("ok", true);
                writer.WriteString("error", string.Empty);
                writer.WriteStartObject("window");
                writer.WriteString("title", title);
                writer.WriteString("process", processName);
                writer.WriteNumber("processId", ownerProcessId);
                writer.WriteNumber("hwnd", hwnd);
                writer.WriteBoolean("requested", requested);
                if (VisibleControlSurface.RunsAboveUs(ownerProcessId))
                    writer.WriteBoolean("elevated", true);
                WriteRect(writer, "rect", windowRect);
                if (cover != 0)
                {
                    (_, string coverProcess) = VisibleControlSurface.WindowProcess(cover);
                    writer.WriteStartObject("coveredBy");
                    writer.WriteString("title", VisibleControlSurface.WindowTitle(cover));
                    writer.WriteString("process", coverProcess);
                    writer.WriteEndObject();
                }
                if (root.TryGetProperty("focused", out JsonElement focused)
                    && focused.ValueKind == JsonValueKind.Object)
                {
                    writer.WritePropertyName("focused");
                    focused.WriteTo(writer);
                }
                else
                {
                    writer.WriteNull("focused");
                }

                writer.WriteEndObject();
                writer.WriteStartArray("controls");
                foreach (ViewControl control in controls)
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("i", control.Index);
                    writer.WriteString("kind", control.Kind);
                    writer.WriteString("name", control.Name);
                    writer.WriteString("id", control.Id);
                    writer.WriteString("state", control.State);
                    if (control.Value is null)
                        writer.WriteNull("value");
                    else
                        writer.WriteString("value", control.Value);
                    // What a list, grid or tree item is as its application reports it (a folder, a shortcut).
                    if (control.ItemType.Length > 0)
                        writer.WriteString("itemType", control.ItemType);
                    if (control.RectValue is { } rect)
                        WriteRect(writer, "rect", rect);
                    else
                        writer.WriteNull("rect");
                    writer.WriteString("zone", control.Zone);
                    writer.WriteString("color", control.Color);
                    if (control.Repeated > 0)
                        writer.WriteNumber("repeated", control.Repeated);
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
                writer.WriteNumber("controlCount", counted);
                if (textAuthority is not null)
                {
                    writer.WriteStartObject("text");
                    foreach (string zone in ZoneOrder)
                    {
                        if (!textZones.TryGetValue(zone, out List<string>? bucket) || bucket.Count == 0)
                            continue;
                        writer.WriteStartArray(zone);
                        foreach (string line in bucket)
                            writer.WriteStringValue(line);
                        writer.WriteEndArray();
                    }

                    writer.WriteEndObject();
                    writer.WriteString("textAuthority", textAuthority);
                }

                writer.WriteString("surface", captured?.Sha256 ?? string.Empty);
                writer.WriteStartObject("elapsedMs");
                writer.WriteNumber("uia", uiaMs);
                writer.WriteNumber("ocr", ocrMs);
                writer.WriteNumber("color", colorMs);
                writer.WriteNumber("total", stopwatch.ElapsedMilliseconds);
                writer.WriteEndObject();
                writer.WriteString("authority", controls.Count <= 1 && textAuthority == "windows_media_ocr_lines"
                    ? "windows_media_ocr_lines"
                    : "windows_uia_snapshot_ocr_zones");
                writer.WriteEndObject();
            });
            return new ViewResult(ExternalJson.Success(operation, result, false), names);
        }
    }

    private readonly record struct WrittenText(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? Lines,
        long Milliseconds);

    private static async Task<VisibleControlSurface.CapturedWindow?> CaptureQuietlyAsync(
        nint hwnd,
        CancellationToken cancellationToken)
    {
        try
        {
            return await VisibleControlSurface.CaptureAsync(hwnd, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    private static async Task<WrittenText> ReadTextAsync(
        Task<VisibleControlSurface.CapturedWindow?> captureTask,
        int limit,
        CancellationToken cancellationToken)
    {
        if (await captureTask.ConfigureAwait(false) is not { } capture)
            return default;
        var watch = Stopwatch.StartNew();
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            capture.Bmp, Math.Max(limit, 40), cancellationToken).ConfigureAwait(false);
        return new WrittenText(lines, watch.ElapsedMilliseconds);
    }

    private static List<ViewControl> ParseControls(JsonElement root)
    {
        var controls = new List<ViewControl>();
        if (!root.TryGetProperty("controls", out JsonElement listed)
            || listed.ValueKind != JsonValueKind.Array)
        {
            return controls;
        }

        foreach (JsonElement item in listed.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
                continue;
            string name = ReadString(item, "name");
            if (name.Length == 0)
                continue;
            Rect? rect = null;
            if (item.TryGetProperty("rect", out JsonElement box) && box.ValueKind == JsonValueKind.Object)
            {
                rect = new Rect(ReadInt(box, "x"), ReadInt(box, "y"), ReadInt(box, "w"), ReadInt(box, "h"));
            }

            controls.Add(new ViewControl
            {
                Index = controls.Count,
                Kind = ReadString(item, "kind"),
                Name = name,
                Id = ReadString(item, "id"),
                State = ReadString(item, "state"),
                Value = item.TryGetProperty("value", out JsonElement value)
                    && value.ValueKind == JsonValueKind.String
                        ? value.GetString()
                        : null,
                ItemType = ReadString(item, "itemType"),
                RectValue = rect,
                Repeated = ReadInt(item, "repeated"),
            });
        }

        return controls;
    }

    private static string ReadString(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static int ReadInt(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int number)
            ? number
            : 0;

    private static void WriteRect(Utf8JsonWriter writer, string name, Rect rect)
    {
        writer.WriteStartObject(name);
        writer.WriteNumber("x", rect.X);
        writer.WriteNumber("y", rect.Y);
        writer.WriteNumber("w", rect.W);
        writer.WriteNumber("h", rect.H);
        writer.WriteEndObject();
    }

    private static readonly string[] ZoneOrder = ["TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"];

    // Rejilla 3×3 sobre la ventana (contrato §1.4): la zona del centro.
    internal static string Zone(double centerX, double centerY, Rect window)
    {
        if (window.W <= 0 || window.H <= 0)
            return string.Empty;
        double fx = (centerX - window.X) / window.W;
        double fy = (centerY - window.Y) / window.H;
        string row = fy < 1.0 / 3 ? "T" : fy < 2.0 / 3 ? string.Empty : "B";
        string column = fx < 1.0 / 3 ? "L" : fx < 2.0 / 3 ? string.Empty : "R";
        string zone = row + column;
        return zone.Length == 0 ? "C" : zone;
    }

    // ---------------------------------------------------------------- click

    private async ValueTask<ExternalCapabilityReceipt> InvokeUiaAsync(
        string operation,
        string label,
        string? controlId,
        nint window,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        nint hwnd = 0;
        try
        {
            // A click by the identity of the last view lands on that view's
            // window while it still exists, whatever holds the foreground now.
            LastView? recent;
            lock (_viewLock)
            {
                recent = _lastView;
            }

            // M132: a click bound to the application just opened acts on that
            // window, never on whatever happens to be in front.
            if (window != 0)
            {
                hwnd = window;
            }
            else if (controlId is not null && recent is not null && VisibleControlSurface.IsAlive(recent.Hwnd))
            {
                VisibleControlSurface.BringToFront(recent.Hwnd);
                hwnd = recent.Hwnd;
            }

            if (hwnd == 0)
            {
                hwnd = await VisibleControlSurface.ResolveForegroundAsync(cancellationToken)
                    .ConfigureAwait(false);
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            hwnd = 0;
        }

        if (hwnd == 0)
            return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");

        // The descriptor admits «surface changed» as post-read. A Calculator
        // digit stays enabled and unselected after Invoke, so the surface is
        // the only evidence (UI1273); it is compared before/after the click.
        VisibleControlSurface.CapturedWindow? before = null;
        try
        {
            before = await VisibleControlSurface.CaptureAsync(hwnd, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            before = null;
        }

        var aliases = new JsonArray();
        foreach (string alias in Aliases(label))
            aliases.Add((JsonNode?)JsonValue.Create(alias));
        string command = new JsonObject
        {
            ["cmd"] = "click",
            ["hwnd"] = hwnd,
            ["aliases"] = aliases,
            ["controlId"] = controlId ?? string.Empty,
        }.ToJsonString();
        try
        {
            effectBoundary.Cross(cancellationToken);
            JsonDocument? answer = await _worker.SendAsync(command, WorkerClickBudget, cancellationToken)
                .ConfigureAwait(false);
            if (answer is null)
                return effectBoundary.Failure(operation, "visible_click_no_receipt");
            using (answer)
            {
                if (answer.RootElement.TryGetProperty("pending", out JsonElement pending)
                    && pending.ValueKind == JsonValueKind.True)
                {
                    return await PostreadAsync(operation, answer.RootElement, before, effectBoundary, cancellationToken)
                        .ConfigureAwait(false);
                }

                return ReceiptFromWorker(operation, answer.RootElement, effectBoundary);
            }
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
    }

    /// <summary>
    /// The post-read of a click the worker has just invoked. The control's own state is asked every 50 ms for up to
    /// half a second; meanwhile the window is captured from about 150 ms on, and two captures that agree with each
    /// other and differ from the one before the click settle it at once (a Calculator digit stays enabled and
    /// unselected after Invoke, so the surface is its only evidence, UI1273). A window still redrawing is watched up
    /// to the surface budget; one that differed then counts as changed, one that never did leaves the click
    /// unconfirmed.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> PostreadAsync(
        string operation,
        JsonElement clicked,
        VisibleControlSurface.CapturedWindow? before,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        var watch = Stopwatch.StartNew();
        bool askControl = true;
        bool differed = false;
        string? lastSurface = null;
        TimeSpan budget = before is null ? _timing.ControlPostread : _timing.SurfacePostread;
        while (true)
        {
            if (askControl && watch.Elapsed < _timing.ControlPostread)
            {
                using JsonDocument? read = await _worker.SendAsync(
                        "{\"cmd\":\"postread\"}", WorkerClickBudget, cancellationToken)
                    .ConfigureAwait(false);
                // The control was invoked already: a silence here is not a «not found» to look for again.
                if (read is null)
                    return effectBoundary.Failure(operation, "visible_click_postread_no_receipt");
                JsonElement root = read.RootElement;
                if (root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True)
                    return ReceiptFromWorker(operation, root, effectBoundary);
                // Anything but «not yet» ends the questions to the control; the surface may still answer.
                askControl = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() == "visible_button_postread_unchanged";
            }

            if (before is { } captured && watch.Elapsed >= _timing.SurfaceFirstSample)
            {
                string? surface = await SurfaceAsync(captured.Hwnd, cancellationToken).ConfigureAwait(false);
                if (surface is not null && !string.Equals(surface, captured.Sha256, StringComparison.Ordinal))
                {
                    if (string.Equals(surface, lastSurface, StringComparison.Ordinal))
                        return SurfaceChanged(operation, clicked);
                    differed = true;
                }

                lastSurface = surface;
            }

            if (watch.Elapsed >= budget)
                break;
            await Task.Delay(_timing.PostreadPeriod, cancellationToken).ConfigureAwait(false);
        }

        return differed
            ? SurfaceChanged(operation, clicked)
            : effectBoundary.Failure(operation, "visible_button_postread_unchanged", effectObserved: true);
    }

    private static async ValueTask<string?> SurfaceAsync(nint window, CancellationToken cancellationToken)
    {
        try
        {
            VisibleControlSurface.CapturedWindow? capture =
                await VisibleControlSurface.CaptureAsync(window, cancellationToken).ConfigureAwait(false);
            return capture is { } taken && taken.Hwnd == window ? taken.Sha256 : null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    private static ExternalCapabilityReceipt SurfaceChanged(string operation, JsonElement clicked)
    {
        JsonObject node = JsonNode.Parse(clicked.GetRawText())!.AsObject();
        node.Remove("pending");
        node["ok"] = true;
        node["error"] = "";
        node["surfaceChanged"] = true;
        node["cascadeStage"] = "uia_surface";
        using JsonDocument verified = JsonDocument.Parse(node.ToJsonString());
        return ExternalJson.Success(operation, verified.RootElement.Clone(), true);
    }

    internal static bool PostreadHolds(JsonElement root)
    {
        bool dismissed = root.TryGetProperty("absentOrDisabled", out JsonElement dismissedValue)
            && dismissedValue.ValueKind == JsonValueKind.True;
        bool selected = root.TryGetProperty("selected", out JsonElement selectedValue)
            && selectedValue.ValueKind == JsonValueKind.True;
        bool toggled = root.TryGetProperty("toggled", out JsonElement toggledValue)
            && toggledValue.ValueKind == JsonValueKind.True;
        bool surface = root.TryGetProperty("surfaceChanged", out JsonElement surfaceValue)
            && surfaceValue.ValueKind == JsonValueKind.True;
        return dismissed || selected || toggled || surface;
    }

    private static ExternalCapabilityReceipt ReceiptFromWorker(
        string operation,
        JsonElement root,
        ExternalEffectBoundary effectBoundary)
    {
        bool effect = root.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.True;
        bool ok = root.TryGetProperty("ok", out JsonElement accepted)
            && accepted.ValueKind == JsonValueKind.True;
        if (!ok)
        {
            string error = root.TryGetProperty("error", out JsonElement errorValue)
                && errorValue.ValueKind == JsonValueKind.String
                    ? errorValue.GetString() ?? "visible_click_failed"
                    : "visible_click_failed";
            if (error.Length == 0)
                error = "visible_click_failed";
            return !effect && BeforeAnyPress.Contains(error)
                ? ExternalJson.FailureBeforeEffect(operation, error)
                : effectBoundary.Failure(operation, error, effect);
        }

        if (!effect || !PostreadHolds(root))
            return effectBoundary.Failure(operation, "visible_click_postread_invalid", effect);
        return ExternalJson.Success(operation, root.Clone(), true);
    }

    // Alias bilingües del catálogo y nombres de dígitos: una persona dice
    // «aceptar» y «5»; UI Automation anuncia «Accept» o «Cinco» (UI1273).
    internal static IReadOnlyList<string> Aliases(string label)
    {
        string folded = WindowsVisibleOcrLocator.Fold(label);
        switch (folded)
        {
            case "accept" or "aceptar":
                return ["Accept", "Aceptar", label];
            case "ok" or "okay":
                return ["OK", "Okay", "Aceptar", label];
            case "validate" or "valider":
                return ["Validate", "Valider", label];
            case "biblioteca" or "library":
                return ["Biblioteca", "Library", label];
            case "configuracion" or "settings":
                return ["Configuración", "Configuracion", "Settings", label];
        }

        string[][] digits =
        [
            ["0", "Cero", "Zero"], ["1", "Uno", "One"], ["2", "Dos", "Two"], ["3", "Tres", "Three"],
            ["4", "Cuatro", "Four"], ["5", "Cinco", "Five"], ["6", "Seis", "Six"], ["7", "Siete", "Seven"],
            ["8", "Ocho", "Eight"], ["9", "Nueve", "Nine"],
        ];
        foreach (string[] digit in digits)
        {
            if (digit.Any(form => string.Equals(WindowsVisibleOcrLocator.Fold(form), folded, StringComparison.Ordinal)))
                return digit;
        }

        return [label];
    }

    // Etiqueta pedida frente a nombre visto: iguales plegados, o el nombre
    // contiene la etiqueta como palabra, con una errata por cada cinco letras.
    internal static bool LabelNames(string label, string name)
    {
        string needle = WindowsVisibleOcrLocator.Fold(label);
        string haystack = WindowsVisibleOcrLocator.Fold(name);
        if (needle.Length == 0 || haystack.Length == 0)
            return false;
        if (string.Equals(needle, haystack, StringComparison.Ordinal))
            return true;
        if (haystack.Contains(needle, StringComparison.Ordinal))
            return true;
        int allowed = needle.Length / 5;
        return allowed > 0 && EditDistance(needle, haystack, allowed) <= allowed;
    }

    private static int EditDistance(string left, string right, int cap)
    {
        if (Math.Abs(left.Length - right.Length) > cap)
            return cap + 1;
        int[] previous = new int[right.Length + 1];
        int[] current = new int[right.Length + 1];
        for (int column = 0; column <= right.Length; column++)
            previous[column] = column;
        for (int row = 1; row <= left.Length; row++)
        {
            current[0] = row;
            int best = current[0];
            for (int column = 1; column <= right.Length; column++)
            {
                int cost = left[row - 1] == right[column - 1] ? 0 : 1;
                current[column] = Math.Min(
                    Math.Min(previous[column] + 1, current[column - 1] + 1),
                    previous[column - 1] + cost);
                best = Math.Min(best, current[column]);
            }

            if (best > cap)
                return cap + 1;
            (previous, current) = (current, previous);
        }

        return previous[right.Length];
    }

    private static bool ShouldKeep(ExternalCapabilityReceipt receipt) =>
        receipt.Verified && receipt.ErrorCode is null;

    private static bool ShouldCascade(ExternalCapabilityReceipt receipt) =>
        receipt.ErrorCode is not null && CascadeAfter.Contains(receipt.ErrorCode);

    internal ValueTask PrewarmAsync() => _worker.PrewarmAsync(CancellationToken.None);

    /// <summary>The control the last view handed out at this index, and that view's window: what input.scroll's
    /// «index» names. False when no view handed it out.</summary>
    internal bool TryViewedControl(int index, out nint window, out string controlId, out Rect? rect)
    {
        LastView? view;
        lock (_viewLock)
        {
            view = _lastView;
        }

        ViewControl? chosen = view?.Controls.FirstOrDefault(control => control.Index == index);
        window = chosen is null ? 0 : view!.Hwnd;
        controlId = chosen?.Id ?? string.Empty;
        rect = chosen?.RectValue;
        return chosen is not null;
    }

    /// <summary>Scrolls a viewed control through its UI Automation ScrollPattern; null when the worker did not answer.</summary>
    internal ValueTask<JsonDocument?> ScrollControlAsync(
        nint window,
        string controlId,
        string direction,
        int amount,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "scroll",
                ["hwnd"] = window,
                ["controlId"] = controlId,
                ["direction"] = direction,
                ["amount"] = amount,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    public void Dispose()
    {
        (_worker as IDisposable)?.Dispose();
    }

    internal readonly record struct Rect(int X, int Y, int W, int H);

    internal sealed class ViewControl
    {
        internal int Index { get; set; }
        internal string Kind { get; set; } = string.Empty;
        internal string Name { get; set; } = string.Empty;
        internal string Id { get; set; } = string.Empty;
        internal string State { get; set; } = string.Empty;
        internal string? Value { get; set; }
        internal string ItemType { get; set; } = string.Empty;
        internal Rect? RectValue { get; set; }
        internal int Repeated { get; set; }
        internal string Zone { get; set; } = string.Empty;
        internal string Color { get; set; } = string.Empty;
    }

    private sealed record LastView(nint Hwnd, IReadOnlyList<ViewControl> Controls);

    private readonly record struct ViewResult(ExternalCapabilityReceipt Receipt, IReadOnlyList<string> Names);
}

/// <summary>
/// Dominant colour of each control's rectangle over the window capture
/// (CONTRATO_VISTA_ACCION.md §1.5): an HSV histogram over the pixels, so
/// «el botón rojo» resolves without a model.
/// </summary>
internal static class VisibleControlColors
{
    internal static readonly string[] Names =
        ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink", "white", "black", "gray"];

    internal static void Assign(
        VisibleControlSurface.CapturedWindow capture,
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        byte[] bmp = capture.Bmp;
        if (!TryParse(bmp, out int offset, out int width, out int height) || width <= 0 || height <= 0)
            return;
        foreach (WindowsVisibleControlAdapter.ViewControl control in controls)
        {
            if (control.RectValue is not { } rect)
                continue;
            int left = rect.X - capture.Left;
            int top = rect.Y - capture.Top;
            control.Color = Dominant(bmp, offset, width, height, left, top, rect.W, rect.H);
        }
    }

    internal static bool TryParse(byte[] bmp, out int offset, out int width, out int height)
    {
        offset = width = height = 0;
        if (bmp.Length < 54 || bmp[0] != (byte)'B' || bmp[1] != (byte)'M')
            return false;
        offset = BitConverter.ToInt32(bmp, 10);
        width = BitConverter.ToInt32(bmp, 18);
        height = BitConverter.ToInt32(bmp, 22);
        short bits = BitConverter.ToInt16(bmp, 28);
        if (bits != 32 || offset <= 0 || offset >= bmp.Length)
            return false;
        long needed = (long)offset + (long)Math.Abs(width) * Math.Abs(height) * 4;
        return needed <= bmp.Length;
    }

    internal static string Dominant(
        byte[] bmp, int offset, int width, int height,
        int left, int top, int boxWidth, int boxHeight)
    {
        if (boxWidth <= 0 || boxHeight <= 0)
            return string.Empty;
        // Recorte del 10 % por lado: el borde de un control es su contorno,
        // no su color.
        int insetX = boxWidth / 10;
        int insetY = boxHeight / 10;
        int x0 = Math.Max(0, left + insetX);
        int y0 = Math.Max(0, top + insetY);
        int x1 = Math.Min(width, left + boxWidth - insetX);
        int y1 = Math.Min(height, top + boxHeight - insetY);
        if (x1 <= x0 || y1 <= y0)
            return string.Empty;
        int stepX = Math.Max(1, (x1 - x0) / 64);
        int stepY = Math.Max(1, (y1 - y0) / 64);
        bool bottomUp = height > 0;
        int rows = Math.Abs(height);
        int stride = width * 4;
        int[] histogram = new int[Names.Length];
        for (int y = y0; y < y1; y += stepY)
        {
            int row = bottomUp ? rows - 1 - y : y;
            if (row < 0 || row >= rows)
                continue;
            for (int x = x0; x < x1; x += stepX)
            {
                int index = offset + row * stride + x * 4;
                if (index + 2 >= bmp.Length)
                    continue;
                histogram[Classify(bmp[index + 2], bmp[index + 1], bmp[index])]++;
            }
        }

        int best = 0;
        for (int index = 1; index < histogram.Length; index++)
        {
            if (histogram[index] > histogram[best])
                best = index;
        }

        return histogram[best] == 0 ? string.Empty : Names[best];
    }

    internal static int Classify(byte red, byte green, byte blue)
    {
        double r = red / 255.0;
        double g = green / 255.0;
        double b = blue / 255.0;
        double max = Math.Max(r, Math.Max(g, b));
        double min = Math.Min(r, Math.Min(g, b));
        double delta = max - min;
        double saturation = max <= 0 ? 0 : delta / max;
        double value = max;
        if (saturation < 0.18)
        {
            if (value >= 0.85)
                return 8; // white
            if (value <= 0.2)
                return 9; // black
            return 10; // gray
        }

        double hue;
        if (delta <= 0)
            hue = 0;
        else if (max == r)
            hue = 60 * (((g - b) / delta) % 6);
        else if (max == g)
            hue = 60 * ((b - r) / delta + 2);
        else
            hue = 60 * ((r - g) / delta + 4);
        if (hue < 0)
            hue += 360;
        if (hue < 15 || hue >= 330)
            return hue >= 330 && saturation < 0.55 ? 7 : 0; // pink or red
        if (hue < 40)
            return 1; // orange
        if (hue < 70)
            return 2; // yellow
        if (hue < 170)
            return 3; // green
        if (hue < 200)
            return 4; // cyan
        if (hue < 270)
            return 5; // blue
        return hue < 300 ? 6 : 7; // purple / pink
    }
}
