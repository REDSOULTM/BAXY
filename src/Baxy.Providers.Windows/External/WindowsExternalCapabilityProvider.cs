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
    private int _disposed;

    public WindowsExternalCapabilityProvider()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXY",
            "1"))
    {
    }

    public WindowsExternalCapabilityProvider(string dataRoot)
        : this(CreateDefaultAdapters(dataRoot), ForegroundLease.Shared, ActOnProtectedWindow)
    {
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
            new WingetPackageAdapter(),
            new ShellCommandAdapter(),
            new WindowsFileToolsAdapter(),
            new PresentationDocumentAdapter(),
            new ExplorerFolderAdapter(),
            desktopInteraction,
            visibleControls,
            new WindowsScrollAdapter(visibleControls),
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
            new MicrosoftAccountAdapter(root),
        ];
    }

    /// <param name="missionFront">The lease that brings a mission's window to the front before its act
    /// (<see cref="IForegroundLease.TakeForMissionAsync"/>); null (the test seams that name none) brings nothing.</param>
    /// <param name="actRefused">Whether an act would reach a window it never may (<see cref="ActOnProtectedWindow"/>);
    /// null (the test seams, whose adapters reach no window) refuses nothing.</param>
    internal WindowsExternalCapabilityProvider(
        IExternalOperationAdapter[] adapters,
        IForegroundLease? missionFront = null,
        Func<string, JsonElement, bool>? actRefused = null)
    {
        _adapters = adapters ?? throw new ArgumentNullException(nameof(adapters));
        _missionFront = missionFront;
        _actRefused = actRefused;
    }

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
    /// its <c>youtube_tab_not_found</c> replaced the system read, so the reply spoke only of a YouTube video.
    /// </summary>
    private static bool OnlyNarrowsAnEarlierRead(ExternalCapabilityReceipt? earlier, ExternalCapabilityReceipt later) =>
        earlier?.ErrorCode == "media_session_not_found" && later.ErrorCode == "youtube_tab_not_found";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (_actRefused?.Invoke(operation, arguments) == true)
            return ExternalJson.FailureBeforeEffect(operation, "protected_window");
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

            sessionsBefore = await sessions.SessionsAsync().ConfigureAwait(false);
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
