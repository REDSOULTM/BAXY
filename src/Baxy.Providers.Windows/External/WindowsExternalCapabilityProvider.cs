using System.Runtime.CompilerServices;
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
    private readonly IOpenedApplicationKeyboard? _openedKeyboard;
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
            OpenedApplicationKeyboard.Product)
    {
        _refusedProcess = RefusedProcess;
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
        var desktopInteraction = new WindowsDesktopInteractionAdapter(visibleControls);
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
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY")),
            new WindowsDisplayModeAdapter(),
            new WingetPackageAdapter(),
            new ShellCommandAdapter(),
            new WindowsFileToolsAdapter(),
            new PresentationDocumentAdapter(),
            new ExplorerFolderAdapter(),
            desktopInteraction,
            visibleControls,
            new WindowsScrollAdapter(visibleControls) { ActRefused = VisibleControlSurface.ActRefused },
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
        ];
    }

    /// <param name="missionFront">The lease that brings a mission's window to the front before its act
    /// (<see cref="IForegroundLease.TakeForMissionAsync"/>); null (the test seams that name none) brings nothing.</param>
    /// <param name="actRefused">Whether an act would reach a window it never may (<see cref="ActOnProtectedWindow"/>);
    /// null (the test seams, whose adapters reach no window) refuses nothing.</param>
    /// <param name="openedKeyboard">The window of the application app.open just opened that a keyboard act with no
    /// window goes to (<see cref="OpenedApplicationKeyboard"/>); null (the test seams) sends it to the front, as before.</param>
    internal WindowsExternalCapabilityProvider(
        IExternalOperationAdapter[] adapters,
        IForegroundLease? missionFront = null,
        Func<string, JsonElement, bool>? actRefused = null,
        IOpenedApplicationKeyboard? openedKeyboard = null)
    {
        _adapters = adapters ?? throw new ArgumentNullException(nameof(adapters));
        _missionFront = missionFront;
        _actRefused = actRefused;
        _openedKeyboard = openedKeyboard;
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
    private static string? RefusedProcess(string operation, JsonElement arguments)
    {
        nint target = ActTarget(operation, arguments);
        uint processId = target == 0 ? 0 : VisibleControlSurface.ProcessOf(target);
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

    private static bool ActOnProtectedWindow(string operation, JsonElement arguments) =>
        ActTarget(operation, arguments) is var target and not 0 && VisibleControlSurface.ActRefused(target);

    /// <summary>
    /// The window an input act reaches: the window it names, else the one in front (the pointer's click and wheel, the
    /// window under the pointer); 0 for an operation that is no input act.
    /// </summary>
    private static nint ActTarget(string operation, JsonElement arguments) => operation switch
    {
        "input.visible.click" or "input.key.press" or "input.text.type" or "input.scroll" or "input.select.all"
            or "clipboard.copy" or "clipboard.paste" or "input.keyboard.layout" =>
            MissionWindow(arguments) is var window and not 0 ? window : VisibleControlSurface.FrontWindow(),
        "input.pointer.control" when arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("action", out JsonElement action)
            && action.GetString() is "click" or "scroll_down" => VisibleControlSurface.PointerWindow(),
        _ => 0,
    };

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

        return await InvokeBoundAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
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
                    // BAXY Renew cu (C18): a paste with no app opened went to the window in front (a developer's) and
                    // the reply blamed the app it meant; the fact of where it went, and how another window is reached.
                    if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.ProtectedFrontNext))
                    {
                        writer.WriteString("next", $"nothing was sent: the window it would go to belongs to {program}, "
                            + "where BAXY does not act; BAXY itself can open the application it meant (app_open) or bring "
                            + "its window to the front (window_focus) and then do this step again there");
                    }

                    writer.WriteEndObject();
                }), "protected_window");
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
        return MediaSessionCalls.Diagnosed(
            await InvokeWatchedAsync(operation, arguments, cancellationToken).ConfigureAwait(false), unanswered);
    }

    private async ValueTask<ExternalCapabilityReceipt> InvokeWatchedAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        IReadOnlyList<(string Source, string Title, bool Playing)>? sessionsBefore = null;
        var paused = new List<(WindowsMediaSessionAdapter Media, (string Source, string Title) Session)>();
        if (IsPlayback(operation)
            && _adapters.OfType<WindowsMediaSessionAdapter>().FirstOrDefault() is { } sessions)
        {
            foreach (WindowsMediaSessionAdapter media in _adapters.OfType<WindowsMediaSessionAdapter>())
            {
                if (await media.PauseAssistantPlaybackBeforeAsync(operation).ConfigureAwait(false) is { } session)
                {
                    paused.Add((media, session));
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
            foreach ((WindowsMediaSessionAdapter media, (string Source, string Title) session) in paused)
            {
                _ = await media.ResumeAssistantPlaybackAsync(session).ConfigureAwait(false);
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
        IReadOnlyList<(WindowsMediaSessionAdapter Media, (string Source, string Title) Session)> paused)
    {
        bool effectCrossed = receipt.Verified || receipt.EffectObserved || receipt.EffectMayHaveOccurred;
        var pauses = new List<AssistantPlaybackPause>();
        foreach ((WindowsMediaSessionAdapter media, (string Source, string Title) session) in paused)
        {
            bool resumed = !effectCrossed
                && await media.ResumeAssistantPlaybackAsync(session).ConfigureAwait(false);
            pauses.Add(new AssistantPlaybackPause(session.Source, session.Title, resumed));
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
