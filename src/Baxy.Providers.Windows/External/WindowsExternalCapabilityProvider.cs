using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Production gate boundary for account-, application- and hardware-bound tools.
/// It probes prerequisites but delegates no effect until an authenticated official
/// adapter is injected. Failure is explicit and can never be mistaken for success.
/// </summary>
public sealed class WindowsExternalCapabilityProvider : IExternalCapabilityProvider, IDisposable
{
    private readonly IExternalOperationAdapter[] _adapters;
    private readonly IForegroundLease? _missionFront;
    private int _disposed;

    public WindowsExternalCapabilityProvider()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXY",
            "1"))
    {
    }

    public WindowsExternalCapabilityProvider(string dataRoot)
        : this(CreateDefaultAdapters(dataRoot), ForegroundLease.Shared)
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
            // media.control/media.status after SMTC and before the Spotify automation,
            // so «para la canción» stops what was just played instead of reaching for
            // a player that is not running.
            new WebBrowserAdapter(root, browserSessionContext),
            new SpotifyDesktopAdapter(),
            new SteamLocalAdapter(visibleControls),
            new WindowsGameInstallationAdapter(),
            new WindowsDeviceControlAdapter(
                root,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY")),
            new WingetPackageAdapter(root),
            new ShellCommandAdapter(),
            new WindowsFileToolsAdapter(),
            new PresentationDocumentAdapter(),
            new ExplorerFolderAdapter(),
            new WindowsInventoryAdapter(),
            desktopInteraction,
            visibleControls,
            new WindowsScrollAdapter(visibleControls),
            new WindowsKnownFileAdapter(root),
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
            new GoogleNewsHeadlinesAdapter(),
            new MicrosoftGraphCalendarAdapter(),
            new MicrosoftAccountAdapter(root),
        ];
    }

    /// <param name="missionFront">The lease that brings a mission's window to the front before its act
    /// (<see cref="IForegroundLease.TakeForMissionAsync"/>); null (the test seams that name none) brings nothing.</param>
    internal WindowsExternalCapabilityProvider(IExternalOperationAdapter[] adapters, IForegroundLease? missionFront = null)
    {
        _adapters = adapters ?? throw new ArgumentNullException(nameof(adapters));
        _missionFront = missionFront;
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
        // The owner's decision of 2026-10-10 («no molestar», simple form): an act of a mission is done with the mission's
        // window in front, brought after the person's pause; the lease gives the front back at the person's first input,
        // after a text and once the mission ended. Nothing is sent when the person does not pause, Windows does not give
        // the front or the mission already ended: never behind their window.
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

        string error = operation switch
        {
            "media.play.exact" or "media.play.query" => ProcessExists("Spotify")
                ? "spotify_session_authority_required" : "spotify_client_not_running",
            "media.play.youtube" => "youtube_cdp_playback_required",
            "media.control" => "smtc_session_adapter_required",
            "media.seek.relative" => "smtc_session_adapter_required",
            "media.status" => "smtc_session_adapter_required",
            "audio.microphone.mute" => "default_microphone_endpoint_required",
            "audio.volume.adjust" => "default_audio_output_endpoint_required",
            "browser.control" or "browser.navigate" or "browser.navigate.named"
                or "browser.page.read" or "browser.tabs.list" =>
                "cdp_browser_session_required",
            "filesystem.folder.open" => "windows_shell_folder_adapter_required",
            "filesystem.file.open.latest" => "windows_shell_file_adapter_required",
            "file.edit" or "file.find" or "file.read" or "filesystem.known.duplicates"
                or "filesystem.known.trash.named" =>
                "windows_known_folder_authority_required",
            "filesystem.path.ensure.absent" => "windows_absolute_path_absence_authority_required",
            "filesystem.explorer.count" => "windows_shell_explorer_folder_authority_required",
            "filesystem.sandbox.diff.named" or "filesystem.sandbox.move.named" =>
                "sandbox_named_file_authority_required",
            "backup.known.create" or "backup.known.list" or "backup.known.restore.latest"
                or "backup.known.verify.latest" =>
                "windows_known_backup_authority_required",
            "clipboard.copy" => "focused_window_clipboard_copy_sendinput_required",
            "clipboard.paste" => "focused_window_clipboard_sendinput_required",
            "input.key.press" => "focused_window_sendinput_required",
            "input.keyboard.layout" => "focused_window_keyboard_layout_required",
            "input.keyboard.open" => "windows_on_screen_keyboard_required",
            "input.keyboard.status" => "focused_window_keyboard_layout_required",
            "input.pointer.control" => "pointer_win32_adapter_required",
            "input.select.all" => "focused_uia_control_required",
            "input.text.type" => "focused_window_text_input_required",
            "input.visible.click" => "visible_uia_control_required",
            "input.visible.controls" => "visible_uia_control_required",
            "input.scroll" => "visible_window_surface_required",
            "streaming.navigate" or "streaming.play.named" =>
                "streaming_authenticated_session_required",
            "web.search" => "web_search_provider_not_configured",
            "web.fetch" => "web_page_reader_not_configured",
            "calendar.event.create" or "calendar.event.list" => "calendar_account_adapter_required",
            "email.latest.read" or "email.latest.reply" or "email.send" => "outlook_authenticated_profile_required",
            "office.document.create" or "office.document.read" =>
                "office_authenticated_adapter_required",
            "message.recipient.resolve" or "message.send" =>
                ProcessExists("WhatsApp") || ProcessExists("Discord")
                    ? "messaging_session_adapter_required" : "messaging_client_not_running",
            "notification.cancel.at" or "notification.cancel.latest" or "notification.diagnose"
                or "notification.list" or "notification.schedule" =>
                "windows_task_scheduler_required",
            "game.installed.named" => "steam_epic_game_manifest_inventory_required",
            "bluetooth.device.list" or "bluetooth.device.pair" or "bluetooth.radio.set"
                or "bluetooth.radio.status" =>
                "bluetooth_hardware_gate_required",
            "game.install.prepare" or "game.install.commit" or "game.install.named" or "game.install.status"
                or "game.install.cancel"
                or "game.purchase.prepare" or "game.purchase.commit"
                or "game.catalog.list" or "game.launch" =>
                ProcessExists("steam") ? "steam_session_adapter_required" : "steam_client_not_running",
            "vision.describe" => string.IsNullOrWhiteSpace(
                Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"))
                    ? "vision_provider_not_configured" : "vision_session_adapter_required",
            "peripheral.list" or "peripheral.print" or "peripheral.scan" =>
                "peripheral_hardware_gate_required",
            "display.status" => "windows_display_api_required",
            "calculator.expression.evaluate" => "windows_calculator_uia_required",
            "software.python.status" => "windows_registry_read_required",
            "software.python.package.status" => "python_pip_read_required",
            "storage.removable.list" => "windows_driveinfo_read_required",
            "client.channel.locate" => "client_quick_switcher_uia_required",
            "ocr.read" => "windows_ocr_language_pack_gate_required",
            "package.install.prepare" or "package.install.commit" => "winget_adapter_gate_required",
            "system.settings.adjust" or "system.settings.set" or "system.settings.status" =>
                "windows_setting_hardware_gate_required",
            "system.power" => "power_transition_physical_gate_required",
            "system.application.crash.diagnose" => "windows_application_eventlog_required",
            "system.process.terminate.named" => "windows_process_termination_authority_required",
            "system.recyclebin.empty" => "windows_recycle_bin_authority_required",
            "wifi.connect" or "wifi.connect.named" or "wifi.disconnect" or "wifi.ensure.connected"
                or "wifi.profile.list" or "wifi.radio.set" or "wifi.radio.status" or "wifi.scan" or "wifi.status" =>
                "wlan_profile_hardware_gate_required",
            _ => "external_operation_not_supported",
        };
        return new ExternalCapabilityReceipt(operation, false, false, null, error);
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

    private static bool ProcessExists(string name)
    {
        Process[] processes = Process.GetProcessesByName(name);
        try { return processes.Length > 0; }
        finally { foreach (Process process in processes) process.Dispose(); }
    }
}
