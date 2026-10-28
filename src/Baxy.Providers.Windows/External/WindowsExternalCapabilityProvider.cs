using System.Runtime.CompilerServices;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The Windows adapters of the external tools (apps, media, web, files, devices, accounts): each call goes to the
/// adapters that claim its operation, in order, until one verifies it or crosses its effect; a failure before any
/// effect lets the next one try, and the last failure that read something is the answer.
/// </summary>
public sealed class WindowsExternalCapabilityProvider : IExternalCapabilityProvider, IDisposable
{
    private readonly IExternalOperationAdapter[] _adapters;
    private readonly IForegroundLease? _missionFront;
    private readonly Func<string, JsonElement, bool>? _actRefused;
    // FT/proveedores goal (live W1, 2026-10-19): the program of the window an act was refused for; the refusal named
    // none, and the model told «la ventana de Word está protegida» when a terminal was in front. Null in the test seams.
    private Func<string, JsonElement, string?>? _refusedProcess;
    private Func<string, JsonElement, string?>? _elevatedAct;
    // Holdout v6 V6E016: the desktop's windows an act may reach, as a refusal lists them. Null in the test seams.
    private Func<IReadOnlyList<OpenWindow>>? _openWindows;
    private readonly IOpenedApplicationKeyboard? _openedKeyboard;
    private readonly Func<OpenedKeyboardWindow?>? _surfaceBelowProduct;
    // Feria (writing with no window): the program of the window in front, named apart from the refused one. Null in the
    // test seams.
    private Func<string?>? _frontProcess;
    private int _disposed;

    /// <summary>
    /// How media.status names the YouTube tab of BAXY's browser, and so the one sourceApp with which media.control
    /// reaches that tab (<see cref="WebBrowserAdapter"/> drives it through CDP, by a script in the page); with any other
    /// session named, the tab's adapter refuses it before any effect.
    /// </summary>
    public const string YouTubeTabMediaSource = "BAXY YouTube (Edge)";

    public WindowsExternalCapabilityProvider()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXY",
            "1"))
    {
    }

    public WindowsExternalCapabilityProvider(string dataRoot)
        : this(CreateDefaultAdapters(dataRoot), ForegroundLease.Shared, ActOnProtectedWindow,
            OpenedApplicationKeyboard.Product, SurfaceBelowProduct)
    {
        _refusedProcess = RefusedProcess;
        _frontProcess = static () => ProgramOf(VisibleControlSurface.FrontWindow());
        _openWindows = OpenWindows;
        _elevatedAct = static (operation, arguments) => ElevatedActCode(operation, ActTarget(operation, arguments),
            static window => unchecked((int)VisibleControlSurface.ProcessOf(window)), VisibleControlSurface.RunsAboveUs,
            VisibleControlSurface.Elevated);
    }

    private static IExternalOperationAdapter[] CreateDefaultAdapters(string dataRoot)
    {
        string root = Path.GetFullPath(dataRoot);
        var browserSessionContext = new CdpBrowserSessionContext();
        // input.scroll by «index» scrolls a control of the last computer-use view; input.text.type by «index» writes
        // into a field of it.
        // TZ-DC2 (z3 t1-c09 «mandale a Ron92 por discord…»): one UI Automation worker for the Core, started by its
        // prewarm. The messaging clients' probe had its own, started by each Core's first search, which read nothing
        // until it was up: that search clicked its first row after fixed waits and the recipient's chat never opened.
        var uia = new UiaWorkerHost();
        var visibleControls = new WindowsVisibleControlAdapter(uia);
        // Ronda 20 P2 (t-drag-2): the pause detector starts with the provider, off the caller's thread and without
        // waiting for it (its own wait for Raw Input happens there), so the first look of a mission already knows the
        // window the person works in. Started lazily at that look, it knew nothing that came before.
        _ = Task.Run(() => WindowsUserInputPause.Shared);
        // Renew al máximo (rendimiento): filesystem.folder.open's and the Calculator's scripts run in this worker, already
        // started by the prewarm, instead of a PowerShell started cold for each call.
        var desktopInteraction = new WindowsDesktopInteractionAdapter(visibleControls) { Scripts = uia };
        // A search burst (goal v3 point 0, fix 3) types its destination as input.text.type does, bound to the window.
        visibleControls.TypeInWindow = (window, text, token) => desktopInteraction.InvokeAsync(
            "input.text.type",
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("text", text);
                writer.WriteNumber("window", (long)window);
                writer.WriteEndObject();
            }),
            token);
        return [
            new DesktopMessagingAdapter(new UiaClientInteractionProbe(uia)),
            new WindowsMicrophoneAdapter(),
            new WindowsAudioAdjustmentAdapter(),
            new WindowsAppVolumeAdapter(),
            new WindowsAppVolumeSetAdapter(),
            // MUSIC1593: the local YouTube player answers media.status and
            // media.control while it plays (SMTC never sees mpv); without an
            // active player it stands aside and the SMTC adapter answers.
            // Renew al máximo (B-APP-1): so it does, unnamed, when left paused
            // while a system session plays.
            new YouTubeMpvAdapter(),
            new WindowsMediaSessionAdapter(),
            // 2026-09-22 (owner's turn 148): the YouTube tab this session plays answers
            // media.control/media.status after SMTC, so «para la canción» stops what was
            // just played. The Spotify client is controlled through its SMTC session.
            new WebBrowserAdapter(root, browserSessionContext),
            new SpotifyDesktopAdapter(),
            new SteamLocalAdapter(visibleControls),
            new WindowsGameInstallationAdapter(),
            new WindowsDeviceControlAdapter(
                root,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY"))
            {
                Scripts = uia,
            },
            new WindowsDisplayModeAdapter(),
            new WingetPackageAdapter(),
            new ShellCommandAdapter(),
            new WindowsFileToolsAdapter(),
            new PresentationDocumentAdapter(),
            new ExplorerFolderAdapter(),
            desktopInteraction,
            visibleControls,
            new WindowsScrollAdapter(visibleControls) { ActRefused = VisibleControlSurface.ActRefused },
            new WindowsPointerDragAdapter(visibleControls),
            new WindowsKnownFileAdapter(),
            new WindowsSandboxNamedFileAdapter(root),
            new WindowsKnownBackupAdapter(root),
            new WindowsScheduledNotificationAdapter(root),
            new WindowsApplicationCrashDiagnosticAdapter(),
            new WindowsPowerTransitionAdapter(),
            new WindowsProcessTerminationAdapter(),
            new WindowsRecycleBinAdapter(),
            new CaptureVisionAdapter(Path.Combine(root, "captures")),
            new NamedBrowserAdapter(root, browserSessionContext),
            new OpenMeteoWeatherAdapter(),
            new MicrosoftAccountAdapter(),
            new OfficeFormatAdapter(),
        ];
    }

    /// <param name="missionFront">The lease that brings a mission's window to the front before its act
    /// (<see cref="IForegroundLease.TakeForMissionAsync"/>); null (the test seams that name none) brings nothing.</param>
    /// <param name="actRefused">Whether an act would reach a window it never may (<see cref="ActOnProtectedWindow"/>);
    /// null (the test seams, whose adapters reach no window) refuses nothing.</param>
    /// <param name="openedKeyboard">The window of the application app.open just opened that a keyboard act with no
    /// window goes to (<see cref="OpenedApplicationKeyboard"/>); null (the test seams) sends it to the front, as before.</param>
    /// <param name="surfaceBelowProduct">The person's window a text with no window goes to when BAXY's own is in
    /// front (<see cref="SurfaceBelowProduct"/>); null (the test seams) sends it to the front, as before.</param>
    internal WindowsExternalCapabilityProvider(
        IExternalOperationAdapter[] adapters,
        IForegroundLease? missionFront = null,
        Func<string, JsonElement, bool>? actRefused = null,
        IOpenedApplicationKeyboard? openedKeyboard = null,
        Func<OpenedKeyboardWindow?>? surfaceBelowProduct = null)
    {
        _adapters = adapters ?? throw new ArgumentNullException(nameof(adapters));
        _missionFront = missionFront;
        _actRefused = actRefused;
        _openedKeyboard = openedKeyboard;
        _surfaceBelowProduct = surfaceBelowProduct;
    }

    /// <summary>
    /// FT/proveedores goal (E6): the keyboard acts that, with no window named, go to the window in front (a key, a text,
    /// a select-all, a copy, a paste).
    /// </summary>
    internal static bool IsKeyboardAct(string operation, JsonElement arguments) => operation switch
    {
        // Review of E6: a select-all, a copy or a paste takes no window, and its helper acts on whatever is in front
        // when it runs: sent «to» the opened application it could land on another window with that one's name in the
        // receipt, so those three keep acting on the front, as before.
        "input.text.type" => true,
        // A key of the system's rather than of a window's (switching windows, the Start menu, the Task Manager) is
        // what it is from whatever window is in front: bringing the opened application up first would change it.
        "input.key.press" => !(arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("key", out JsonElement key) && key.ValueKind == JsonValueKind.String
            && key.GetString() is "alt_tab" or "win" or "ctrl_shift_escape"),
        _ => false,
    };

    /// <summary>
    /// FT/proveedores goal (E6): the act names no window (none, or null). A window named but invalid is left to the
    /// adapter, which refuses it; it is never replaced.
    /// </summary>
    internal static bool NamesNoWindow(JsonElement arguments) =>
        arguments.ValueKind != JsonValueKind.Object
        || !arguments.TryGetProperty("window", out JsonElement window)
        || window.ValueKind == JsonValueKind.Null;

    /// <summary>
    /// FT/proveedores goal (E6): the arguments with <c>window</c> set to <paramref name="window"/> (every other
    /// property kept as it came).
    /// </summary>
    internal static JsonElement WithWindow(JsonElement arguments, nint window) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        if (arguments.ValueKind == JsonValueKind.Object)
        {
            foreach (JsonProperty property in arguments.EnumerateObject())
            {
                if (property.NameEquals("window"))
                    continue;
                property.WriteTo(writer);
            }
        }

        writer.WriteNumber("window", (long)window);
        // Review of E6: a text sent to the opened application is read back as one with no window (F004), never told
        // verified on the keys Windows accepted alone.
        writer.WriteBoolean(OpenedApplicationArgument, true);
        writer.WriteEndObject();
    });

    /// <summary>The argument the provider adds to an act it sent to the opened application (never the model's).</summary>
    internal const string OpenedApplicationArgument = "openedApplication";

    /// <summary>
    /// FT/proveedores goal (E6): the receipt of a keyboard act sent to the opened application's window says so: the
    /// window it was sent to (<c>openedWindow</c>, its title) and why (<c>windowFrom</c>: <c>opened_application</c>),
    /// whatever came of it (a refusal before any key included).
    /// </summary>
    private static ExternalCapabilityReceipt FromOpened(ExternalCapabilityReceipt receipt, OpenedKeyboardWindow opened) =>
        receipt with
        {
            Result = ExternalJson.Extended(receipt.Result, writer =>
            {
                writer.WriteString("windowFrom", "opened_application");
                writer.WriteNumber("openedWindow", (long)opened.Window);
                writer.WriteString("openedWindowTitle", opened.Title);
            }),
        };

    /// <summary>
    /// Feria (writing with no window): the receipt of a text sent to the person's window below BAXY's own says
    /// so: the window it was sent to (<c>surfaceWindow</c>, its title) and why (<c>windowFrom</c>: <c>persons_surface</c>),
    /// whatever came of it (a refusal before any key included).
    /// </summary>
    private static ExternalCapabilityReceipt FromSurface(ExternalCapabilityReceipt receipt, OpenedKeyboardWindow surface) =>
        receipt with
        {
            Result = ExternalJson.Extended(receipt.Result, writer =>
            {
                writer.WriteString("windowFrom", "persons_surface");
                writer.WriteNumber("surfaceWindow", (long)surface.Window);
                writer.WriteString("surfaceWindowTitle", surface.Title);
            }),
        };

    // The product's window below BAXY's own (VisibleControlSurface.SurfaceBelowProduct), with its title.
    private static OpenedKeyboardWindow? SurfaceBelowProduct() =>
        VisibleControlSurface.SurfaceBelowProduct(VisibleControlSurface.FrontWindow()) is var window and not 0
            ? new OpenedKeyboardWindow(window, VisibleControlSurface.WindowTitle(window))
            : null;

    /// <summary>
    /// The mission's window an act names (its «window» argument: the catalog gives it only to the acts of a computer-use
    /// mission, the hwnd of the view the act was decided on), or 0.
    /// </summary>
    internal static nint MissionWindow(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("window", out JsonElement window)
        && window.ValueKind == JsonValueKind.Number
        && window.TryGetInt64(out long hwnd) && hwnd > 0
            ? checked((nint)hwnd)
            : 0;

    /// <summary>
    /// CU4 (auditoría final 2): a click, a key, a text, a wheel turn or a clipboard keystroke would reach a developer's
    /// or BAXY's own window that no look named (<see cref="VisibleControlSurface.ActRefused"/>).
    /// </summary>
    private static string? RefusedProcess(string operation, JsonElement arguments) =>
        ProgramOf(ActTarget(operation, arguments));

    // The program (process name) of a window; null when it is none or its process is gone.
    private static string? ProgramOf(nint window)
    {
        uint processId = window == 0 ? 0 : VisibleControlSurface.ProcessOf(window);
        if (processId == 0)
            return null;
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return process.ProcessName;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return null;
        }
    }

    // A test seam's way to name the refused window's program (the product's reads the window's process).
    internal Func<string, JsonElement, string?>? RefusedProcessOf
    {
        set => _refusedProcess = value;
    }

    // A test seam's way to name the program in front (the product's reads the front window's process).
    internal Func<string?>? FrontProcessOf
    {
        set => _frontProcess = value;
    }

    // A test seam's way to list the desktop's windows an act may reach (the product's reads them, OpenWindows).
    internal Func<IReadOnlyList<OpenWindow>>? OpenWindowsOf
    {
        set => _openWindows = value;
    }

    /// <summary>
    /// Holdout v6 V6E016 («en el bloc de notas que está abierto escribe: …», both seeds): the text went with no window to
    /// the developer's editor in front, was refused, and the reply ended there although the refusal named the look that
    /// gives the Notepad's number. The desktop's root windows an act may reach, top of the Z order first, each as a look
    /// names it («title» (process, window N)), N being what the act takes as window.
    /// </summary>
    private static IReadOnlyList<OpenWindow> OpenWindows() =>
        [.. VisibleControlSurface.RootWindowsNow(0).Windows
            .Where(window => !VisibleControlSurface.ActRefused(window.Window))
            .Select(window => new OpenWindow(VisibleControlSurface.WindowTitle(window.Window),
                VisibleControlSurface.ViewProcess(window.Window).ProcessName, (long)window.Window))];

    /// <summary>A desktop window an act may reach: its title, its program and its number (what the act takes as window).</summary>
    internal readonly record struct OpenWindow(string Title, string Process, long Number)
    {
        /// <summary>As a look names it: «title» (process, window N).</summary>
        public string Shown => $"«{Title}» ({Process}, window {Number})";
    }

    // A test seam's way to say a keyboard act's window runs above BAXY (the product's reads its process token).
    internal Func<string, JsonElement, string?>? ElevatedActOf
    {
        set => _elevatedAct = value;
    }

    /// <summary>
    /// Renew al máximo (w8): Windows drops the keys, the wheel and the messages BAXY sends to a window of a process that
    /// runs as administrator (UIPI) while SendInput still counts every event as taken, so a key or a text into it came
    /// back verified with nothing done. Only the click refused it (WindowsVisibleControlAdapter, «window_elevated»); every
    /// keyboard, wheel and clipboard act is refused the same way, before anything is sent: «window_elevated», or
    /// «window_elevation_unread» when the process's token could not be read. The click keeps its own refusal.
    /// </summary>
    internal static string? ElevatedActCode(
        string operation, nint target, Func<nint, int> processOf, Func<int, bool> runsAboveUs, Func<int, bool?> elevated)
    {
        if (target == 0 || operation is not ("input.key.press" or "input.text.type" or "input.scroll"
            or "input.pointer.drag" or "input.select.all" or "clipboard.copy" or "clipboard.paste" or "input.keyboard.layout"))
            return null;
        int processId = processOf(target);
        if (processId <= 0 || !runsAboveUs(processId))
            return null;
        return elevated(processId) is null
            ? WindowsVisibleControlAdapter.WindowElevationUnread
            : WindowsVisibleControlAdapter.WindowElevated;
    }

    private static bool ActOnProtectedWindow(string operation, JsonElement arguments) =>
        ActTarget(operation, arguments) is var target and not 0 && VisibleControlSurface.ActRefused(target);

    /// <summary>
    /// The window an input act reaches: the window it names, else the one in front (the pointer's click and wheel, the
    /// window under the pointer); 0 for an operation that is no input act.
    /// </summary>
    private static nint ActTarget(string operation, JsonElement arguments) => operation switch
    {
        "input.visible.click" or "input.key.press" or "input.text.type" or "input.scroll" or "input.select.all"
            or "clipboard.copy" or "clipboard.paste" or "input.keyboard.layout" or "input.pointer.drag" =>
            MissionWindow(arguments) is var window and not 0 ? window : VisibleControlSurface.FrontWindow(),
        "input.pointer.control" when arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("action", out JsonElement action)
            && action.GetString() is "click" or "scroll_down" => VisibleControlSurface.PointerWindow(),
        _ => 0,
    };

    // The acts of ActTarget that take a window (the catalog's «window»).
    private static bool TakesAWindow(string operation) =>
        operation is "input.visible.click" or "input.key.press" or "input.text.type" or "input.scroll";

    // Holdout v5 (V5E066): an input_text_type with no window refused at a protected window in front was told app_open
    // (another Notepad) or window_focus (an id no call had given), never the look by name that gives the open window's
    // number. The acts of ActTarget that take a window (the catalog's «window») name that look first; the others (a
    // paste, Ctrl+A, a copy) take none, and keep the opening or the front.
    // Holdout v6 V6E016: with the windows an act may reach listed beside it, the step is done again with the number of
    // the one meant, and only a window not listed is looked at by its name first.
    // Práctica V5E066 (junto s0 and s1): with the windows listed and the step to do again only described, the reply
    // ended at the refusal both times, once asking the person for the window's number. The call is written out: the
    // same arguments and the window set to the number of the one meant.
    // Revisión w11-rev4: the first listed is the top one, not the one meant when another application is above it (the
    // text went to a chat); a number is written only when one window is listed, and never a title, which any page or
    // document sets: titles stay in windows.
    private static string ProtectedNext(
        string operation, string program, bool named, bool listed, long? only, JsonElement arguments)
    {
        string refused = $"nothing was sent: the window it would go to belongs to {program}, where BAXY does not act";
        if (!TakesAWindow(operation))
            return refused + "; BAXY itself can open the application it meant (app_open) or bring its window to the front "
                + "(window_focus) and then do this step again there";
        string step = operation.Replace('.', '_');
        return refused + (named ? "" : $"; {step} with no window named acts on the window in front")
            + (listed
                ? $"; the windows open that BAXY may act in are in windows (top first), each with its number: to do this "
                    + $"step in one of them, call {step} again with {CallArguments(arguments)} and window set to the number "
                    + $"of the one meant{(only is { } number ? $" (window {number}, the only one listed)" : "")}; the numbers "
                    + "are in windows: the person is "
                    + "not asked for one; a window not listed"
                : "; the window of another application that is open")
            + " is reached by looking at it by its name "
            + "(input_visible_controls with application), whose result gives that window's number, and doing this step "
            + $"again as {step} with window set to that number; an application that is not open is opened first (app_open)";
    }

    // The longest the arguments of a refused call are written again in its next; longer, «the same arguments».
    private const int CallArgumentsMaxChars = 240;

    private static readonly JsonWriterOptions AsWritten = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    // A refused call's own arguments as a next writes them («text "comprar velas"»), without its window (the next sets
    // it), the index of a control or field (a look at another window gave it) nor the provider's own mark of the
    // opened application.
    private static string CallArguments(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
            return "the same arguments";
        var written = new List<string>();
        foreach (JsonProperty argument in arguments.EnumerateObject())
        {
            if (argument.NameEquals("window") || argument.NameEquals("index") || argument.NameEquals(OpenedApplicationArgument)
                || argument.Value.ValueKind == JsonValueKind.Null)
                continue;
            using var buffer = new MemoryStream();
            using (var writer = new Utf8JsonWriter(buffer, AsWritten))
            {
                if (argument.Value.ValueKind == JsonValueKind.String)
                    writer.WriteStringValue(argument.Value.GetString());
                else
                    argument.Value.WriteTo(writer);
            }

            written.Add($"{argument.Name} {System.Text.Encoding.UTF8.GetString(buffer.ToArray())}");
        }

        string call = string.Join(" and ", written);
        return call.Length is 0 or > CallArgumentsMaxChars ? "the same arguments" : call;
    }

    public InstalledGameCatalogSnapshot GetInstalledGameCatalogSnapshot()
    {
        ObjectDisposedException.ThrowIf(Volatile.Read(ref _disposed) != 0, this);
        try
        {
            SteamLocalAdapter? steam = _adapters.OfType<SteamLocalAdapter>().SingleOrDefault();
            return steam?.GetCatalogSnapshot()
                ?? new InstalledGameCatalogSnapshot(
                    Verified: false,
                    Complete: false,
                    Array.Empty<InstalledGameCatalogEntry>());
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or InvalidOperationException)
        {
            return new InstalledGameCatalogSnapshot(
                Verified: false,
                Complete: false,
                Array.Empty<InstalledGameCatalogEntry>());
        }
    }

    /// <summary>
    /// Starts in the background what the first computer-use view would otherwise wait for: the UI Automation worker
    /// (a PowerShell with its UI Automation assemblies, about a second) and its first look
    /// (<see cref="WindowsVisibleControlAdapter.PrewarmAsync"/>). Never blocks the caller; a start that fails
    /// leaves the first view to start it, as before.
    /// </summary>
    public void Prewarm()
    {
        ObjectDisposedException.ThrowIf(Volatile.Read(ref _disposed) != 0, this);
        foreach (WindowsVisibleControlAdapter adapter in _adapters.OfType<WindowsVisibleControlAdapter>())
            _ = Task.Run(() => adapter.PrewarmAsync().AsTask(), CancellationToken.None);
    }

    /// <summary>
    /// Releases every adapter exactly once. A failing adapter must not strand the
    /// remaining ones: each of them can own a child process, a native handle or a
    /// socket, so the loop keeps going and reports the failures together.
    /// </summary>
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
        {
            return;
        }

        List<Exception>? failures = null;
        foreach (IDisposable adapter in _adapters.OfType<IDisposable>())
        {
            try
            {
                adapter.Dispose();
            }
            catch (Exception exception)
            {
                (failures ??= []).Add(exception);
            }
        }

        if (failures is not null)
        {
            throw new AggregateException(
                "One or more external adapters could not be released.",
                failures);
        }
    }

    /// <summary>
    /// M105 (DEV-D v4a D-s047 «cuál es el nombre de la música que se está reproduciendo»): the system media session
    /// read nothing playing (<c>media_session_not_found</c>), then the YouTube tab adapter found no tab of its own and
    /// its <c>youtube_tab_not_found</c> replaced the system read, so the reply spoke only of a YouTube video. Ronda final
    /// 23 (regla 3): a system read that failed (<c>smtc_session_access_failed</c>) is kept too, never replaced by «no tab».
    /// </summary>
    private static bool OnlyNarrowsAnEarlierRead(ExternalCapabilityReceipt? earlier, ExternalCapabilityReceipt later) =>
        earlier?.ErrorCode is "media_session_not_found" or "smtc_session_access_failed"
        && later.ErrorCode == "youtube_tab_not_found";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // FT/proveedores goal (E6): a keyboard act with no window, while the application app.open just opened is not in
        // front, goes to that application's window as if it named it: the protected-window refusal judges that window,
        // the mission lease below brings it up after the person's pause or refuses (input_user_not_paused,
        // input_window_not_in_front) with nothing sent, and the adapter's named-window path sends it there or nowhere.
        // A window the act names always wins; with no fresh opening, or one of its windows in front, nothing changes.
        if (_openedKeyboard is not null && IsKeyboardAct(operation, arguments) && NamesNoWindow(arguments)
            && await _openedKeyboard.WindowAsync(cancellationToken).ConfigureAwait(false) is { } opened)
        {
            return FromOpened(
                await InvokeBoundAsync(operation, WithWindow(arguments, opened.Window), cancellationToken)
                    .ConfigureAwait(false),
                opened);
        }

        // Feria (writing with no window): with BAXY's own window in front (the request was just written there) a text went
        // there and was refused, while a look and a click land on the person's window below it. It goes to that window as
        // if it named it, by the same lease and refusal as the opened application's. A key keeps the front: whether its
        // Enter or space needs the person's yes (a declared text field, a dialog's answer) is read before, on the front.
        if (_surfaceBelowProduct is not null && operation == "input.text.type" && NamesNoWindow(arguments)
            && _surfaceBelowProduct() is { } surface)
        {
            return FromSurface(
                await InvokeBoundAsync(operation, WithWindow(arguments, surface.Window), cancellationToken)
                    .ConfigureAwait(false),
                surface);
        }

        return await InvokeBoundAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
    }

    // Al máximo, flujos: the read of the one adapter that claims the operation (with several, the dispatch decides
    // among them, so nothing is read before).
    public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(Volatile.Read(ref _disposed) != 0, this);
        IExternalOperationAdapter[] claiming = _adapters.Where(candidate => candidate.CanHandle(operation)).ToArray();
        return claiming.Length == 1
            ? claiming[0].PreflightAsync(operation, arguments, cancellationToken)
            : ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
    }

    // Renew al máximo (guarda diálogo destructivo): as the read, the one adapter that claims the operation says.
    public bool PreflightMayRaise(string operation, JsonElement arguments)
    {
        ObjectDisposedException.ThrowIf(Volatile.Read(ref _disposed) != 0, this);
        IExternalOperationAdapter[] claiming = _adapters.Where(candidate => candidate.CanHandle(operation)).ToArray();
        return claiming.Length == 1 && claiming[0].PreflightMayRaise(operation, arguments);
    }

    private async ValueTask<ExternalCapabilityReceipt> InvokeBoundAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (_actRefused?.Invoke(operation, arguments) == true)
        {
            string? program = _refusedProcess?.Invoke(operation, arguments);
            return program is null
                ? ExternalJson.FailureBeforeEffect(operation, "protected_window")
                : new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("refusedProcess", program);
                    if (_frontProcess?.Invoke() is { } front)
                        writer.WriteString("frontProcess", front);
                    // BAXY Renew cu (C18): a paste with no app opened went to the window in front (a developer's) and
                    // the reply blamed the app it meant; the fact of where it went, and how another window is reached.
                    if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.ProtectedFrontNext))
                    {
                        IReadOnlyList<OpenWindow> open = TakesAWindow(operation) && _openWindows is { } windows
                            ? windows()
                            : [];
                        if (open.Count > 0)
                        {
                            writer.WriteStartArray("windows");
                            foreach (OpenWindow window in open.Take(WindowsVisibleControlAdapter.NamedWindowCandidateLimit))
                                writer.WriteStringValue(window.Shown);
                            writer.WriteEndArray();
                        }

                        writer.WriteString("next", ProtectedNext(
                            operation, program, MissionWindow(arguments) != 0, open.Count > 0,
                            open.Count == 1 ? open[0].Number : null, arguments));
                    }

                    writer.WriteEndObject();
                }), "protected_window");
        }

        if (_elevatedAct?.Invoke(operation, arguments) is { } elevatedCode)
        {
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.ElevatedNext))
                {
                    writer.WriteString("next", elevatedCode == WindowsVisibleControlAdapter.WindowElevated
                        ? "nothing was sent: the window it would go to runs as administrator, and Windows blocks the "
                            + "keys BAXY sends there; the person can do it in that window, or open that application "
                            + "again without administrator rights"
                        : "nothing was sent: whether the window it would go to runs as administrator could not be read, "
                            + "and Windows may block the keys BAXY sends there; the person can do it in that window");
                }

                writer.WriteEndObject();
            }), elevatedCode);
        }
        // The owner's decision of 2026-10-10 («no molestar», simple form): an act of a mission is done with the mission's
        // window in front, brought after the person's pause; the lease gives the front back at the person's first input
        // and after a text. Nothing is sent when the person does not pause or Windows does not give the front: never
        // behind their window.
        nint missionWindow = MissionWindow(arguments);
        if (_missionFront is not null && missionWindow != 0)
        {
            if (await _missionFront.TakeForMissionAsync(missionWindow, cancellationToken).ConfigureAwait(false) is { } refusal)
                return ExternalJson.FailureBeforeEffect(operation, refusal);
            try
            {
                return await InvokeOnceAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
            }
            finally
            {
                _missionFront.MissionActEnded(operation);
            }
        }

        return await InvokeOnceAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// One operation, watched: a failure in which a media session went unanswered says so (MS: the reads of Windows'
    /// media sessions are bounded, an unanswered one is left out and the operation goes on).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> InvokeOnceAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        StrongBox<bool> unanswered = MediaSessionCalls.Watch();
        return Interrupted(MediaSessionCalls.Diagnosed(
            await InvokeWatchedAsync(operation, arguments, cancellationToken).ConfigureAwait(false), unanswered));
    }

    /// <summary>
    /// Renew al máximo (w5): an act stopped by the person's input reached the model as the bare code and the reply
    /// told «la ventana se cerró»; the facts of the stop beside the code, which stays: why BAXY stopped, whether
    /// anything was sent as the receipt says, and that whether the act landed was not looked at.
    /// </summary>
    internal static ExternalCapabilityReceipt Interrupted(ExternalCapabilityReceipt receipt) =>
        receipt.ErrorCode != LeasedInput.Interrupted || !Infrastructure.ModelAids.On(Infrastructure.ModelAids.InterruptedNext)
            ? receipt
            : receipt with
            {
                Result = ExternalJson.Extended(receipt.Result, writer =>
                {
                    writer.WriteString("reason", "BAXY stopped because input that was not its own (the person's mouse "
                        + "or keys) came during the act");
                    writer.WriteString("next", receipt.EffectObserved || receipt.EffectMayHaveOccurred
                        ? "part of the act may have been sent before the stop; whether it landed was not looked at: "
                            + "looking at the window again (input_visible_controls) tells"
                        : "nothing of the act was sent; the window was not looked at after the stop: looking at it "
                            + "again (input_visible_controls) tells how it is");
                }),
            };

    private async ValueTask<ExternalCapabilityReceipt> InvokeWatchedAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        IReadOnlyList<(string Source, string Title, bool Playing)>? sessionsBefore = null;
        var paused = new List<PausedPlayback>();
        if (IsPlayback(operation))
        {
            // Renew al máximo (auditoría de flujos): BAXY's own YouTube player is always BAXY's; playing, it is paused
            // for any other playback as the sessions below are (its own next playback replaces it anyway), and played
            // again by the same rule.
            foreach (YouTubeMpvAdapter local in _adapters.OfType<YouTubeMpvAdapter>())
            {
                if (await local.PauseForAnotherPlaybackAsync(cancellationToken).ConfigureAwait(false) is { } own)
                {
                    paused.Add(new(() => local.ResumeAfterAnotherPlaybackAsync(CancellationToken.None), own.Source,
                        own.Title));
                }
            }
        }

        if (IsPlayback(operation)
            && _adapters.OfType<WindowsMediaSessionAdapter>().FirstOrDefault() is { } sessions)
        {
            foreach (WindowsMediaSessionAdapter media in _adapters.OfType<WindowsMediaSessionAdapter>())
            {
                if (await media.PauseAssistantPlaybackBeforeAsync(operation).ConfigureAwait(false) is { } session)
                {
                    paused.Add(new(() => media.ResumeAssistantPlaybackAsync(session), session.Source, session.Title));
                }
            }

            // Ronda final 11 (regla 3): a «before» read in part would take a session of the person's for BAXY's.
            sessionsBefore = await sessions.CompleteSessionsAsync().ConfigureAwait(false);
        }

        if (paused.Count == 0)
        {
            return await DispatchAsync(operation, arguments, sessionsBefore, cancellationToken).ConfigureAwait(false);
        }

        ExternalCapabilityReceipt dispatched;
        try
        {
            dispatched = await DispatchAsync(operation, arguments, sessionsBefore, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception)
        {
            // The new playback never answered: what BAXY paused for it plays again, best effort.
            foreach (PausedPlayback pause in paused)
            {
                _ = await pause.Resume().ConfigureAwait(false);
            }

            throw;
        }

        return await SettlePausedPlaybackAsync(dispatched, paused).ConfigureAwait(false);
    }

    /// <summary>
    /// Revisión 2 de la ronda 19: the session BAXY paused before a new playback stays paused only when that playback
    /// crossed its effect. When it failed before any effect (no search result, the person using the PC, no browser)
    /// the session is resumed, so a failure never silences the music. Either way the receipt carries the pause; a
    /// pause that could not be undone is an effect of the turn, never «nothing happened».
    /// </summary>
    private static async ValueTask<ExternalCapabilityReceipt> SettlePausedPlaybackAsync(
        ExternalCapabilityReceipt receipt,
        IReadOnlyList<PausedPlayback> paused)
    {
        bool effectCrossed = receipt.Verified || receipt.EffectObserved || receipt.EffectMayHaveOccurred;
        var pauses = new List<AssistantPlaybackPause>();
        foreach (PausedPlayback pause in paused)
        {
            bool resumed = !effectCrossed && await pause.Resume().ConfigureAwait(false);
            pauses.Add(new AssistantPlaybackPause(pause.Source, pause.Title, resumed));
        }

        if (effectCrossed || pauses.All(pause => pause.Resumed))
        {
            return receipt with { AssistantPlaybackPauses = pauses };
        }

        JsonElement result = ExternalJson.Extended(receipt.Result, writer =>
        {
            writer.WriteStartArray("pausedAssistantPlayback");
            foreach (AssistantPlaybackPause pause in pauses.Where(pause => !pause.Resumed))
            {
                writer.WriteStartObject();
                writer.WriteString("sourceAppUserModelId", pause.SourceAppUserModelId);
                writer.WriteString("title", pause.Title);
                writer.WriteBoolean("resumed", false);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
        });
        return receipt with { EffectObserved = true, Result = result, AssistantPlaybackPauses = pauses };
    }

    // What BAXY paused before a new playback: how to play it again and what it was (its source and title).
    private sealed record PausedPlayback(Func<ValueTask<bool>> Resume, string Source, string Title);

    private async ValueTask<ExternalCapabilityReceipt> DispatchAsync(
        string operation,
        JsonElement arguments,
        IReadOnlyList<(string Source, string Title, bool Playing)>? sessionsBefore,
        CancellationToken cancellationToken)
    {
        ExternalCapabilityReceipt? lastFailure = null;
        foreach (IExternalOperationAdapter adapter in _adapters.Where(
            candidate => candidate.CanHandle(operation)))
        {
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                operation, arguments, cancellationToken)
                .ConfigureAwait(false);
            if (receipt.Verified
                || receipt.EffectObserved
                || receipt.EffectMayHaveOccurred)
            {
                await RememberAssistantPlaybackAsync(operation, receipt, sessionsBefore).ConfigureAwait(false);
                return receipt;
            }
            // Tanda 5: a failure that read its player's state (Result: the YouTube tab's video was not playing) is
            // the answer when no later adapter finds a player; a later «no client running here» never hides it.
            // M105 (DEV-D v4a D-s047): nor does the assistant's own YouTube tab being absent hide what the PC's
            // media session read (nothing plays at all), which answers more than that one tab.
            if (lastFailure?.Result is null && !OnlyNarrowsAnEarlierRead(lastFailure, receipt))
            {
                lastFailure = receipt;
            }
        }
        if (lastFailure is not null)
        {
            return lastFailure;
        }

        // Every operation of the catalog has an adapter that claims it; one none claims is not supported here.
        return ExternalJson.FailureBeforeEffect(operation, "external_operation_not_supported");
    }

    /// <summary>A verified playback BAXY started tells the media session adapter which session is its own.</summary>
    private static bool IsPlayback(string operation) => operation is "media.play.youtube" or "media.play.exact"
        or "media.play.query" or "streaming.play.named";

    /// <summary>
    /// A playback BAXY started tells the media session adapter which session is its own: the one a verified receipt
    /// names, or (ronda 19: the desktop client's receipt names none) the one that started playing during it. Ronda 19
    /// (t2-c01 T1 then T2): a press that failed after its effect was observed (the client resumed what it had loaded,
    /// not confirmed as the search) still left that music playing by BAXY's hand, so the session that started playing
    /// during it is BAXY's too, and «no, mejor en youtube» pauses it. A session already playing before the operation
    /// (the person's) never is.
    /// </summary>
    private async ValueTask RememberAssistantPlaybackAsync(
        string operation,
        ExternalCapabilityReceipt receipt,
        IReadOnlyList<(string Source, string Title, bool Playing)>? sessionsBefore)
    {
        if (!(receipt.Verified || receipt.EffectObserved) || !IsPlayback(operation))
        {
            return;
        }
        string? named = receipt.Verified && receipt.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("sourceAppUserModelId", out JsonElement source)
            && source.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(source.GetString())
                ? source.GetString()
                : null;
        // Revisión 2: what BAXY left playing is a source and the title it started there, so a later session of the
        // person's in the same app (another title) is never taken for BAXY's.
        string? title = null;
        if (sessionsBefore is not null
            && _adapters.OfType<WindowsMediaSessionAdapter>().FirstOrDefault() is { } sessions)
        {
            IReadOnlyList<(string Source, string Title, bool Playing)> after =
                await sessions.SessionsAsync().ConfigureAwait(false);
            named ??= WindowsMediaSessionAdapter.NewlyPlayingSource(sessionsBefore, after);
            title = named is null ? null : WindowsMediaSessionAdapter.NewlyPlayingTitle(sessionsBefore, after, named);
        }
        if (named is null)
        {
            return;
        }
        foreach (WindowsMediaSessionAdapter media in _adapters.OfType<WindowsMediaSessionAdapter>())
        {
            media.RememberAssistantPlayback(named, title, operation);
        }
    }
}
