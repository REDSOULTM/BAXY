using System.Diagnostics;
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
    private int _disposed;

    public WindowsExternalCapabilityProvider()
        : this(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXY",
            "1"))
    {
    }

    public WindowsExternalCapabilityProvider(string dataRoot)
        : this(CreateDefaultAdapters(dataRoot))
    {
    }

    private static IExternalOperationAdapter[] CreateDefaultAdapters(string dataRoot)
    {
        string root = Path.GetFullPath(dataRoot);
        var browserSessionContext = new CdpBrowserSessionContext();
        return [
            new DesktopMessagingAdapter(),
            new WindowsMicrophoneAdapter(),
            new WindowsAudioAdjustmentAdapter(),
            new WindowsAppVolumeAdapter(),
            // MUSIC1593: the local YouTube player answers media.status and
            // media.control while it plays (SMTC never sees mpv); without an
            // active player it stands aside and the SMTC adapter answers.
            new YouTubeMpvAdapter(),
            new WindowsMediaSessionAdapter(),
            new SpotifyDesktopAdapter(),
            new SteamLocalAdapter(),
            new WindowsGameInstallationAdapter(),
            new WindowsDeviceControlAdapter(
                root,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY")),
            new WingetPackageAdapter(root),
            new WindowsInventoryAdapter(),
            new WindowsDesktopInteractionAdapter(),
            new WindowsVisibleControlAdapter(),
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
            new WebBrowserAdapter(root, browserSessionContext),
            new OpenMeteoWeatherAdapter(),
            new GoogleNewsHeadlinesAdapter(),
            new MicrosoftGraphCalendarAdapter(),
            new MicrosoftAccountAdapter(root),
        ];
    }

    internal WindowsExternalCapabilityProvider(IExternalOperationAdapter[] adapters) =>
        _adapters = adapters ?? throw new ArgumentNullException(nameof(adapters));

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

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
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
                return receipt;
            }
            lastFailure = receipt;
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
            "filesystem.known.duplicates" or "filesystem.known.list" or "filesystem.known.search"
                or "filesystem.known.trash.named" =>
                "windows_known_folder_authority_required",
            "filesystem.path.ensure.absent" => "windows_absolute_path_absence_authority_required",
            "document.pdf.read" => "windows_known_pdf_text_authority_required",
            "filesystem.sandbox.append.named" or "filesystem.sandbox.diff.named"
                or "filesystem.sandbox.move.named" => "sandbox_named_file_authority_required",
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
            "streaming.navigate" or "streaming.play.named" =>
                "streaming_authenticated_session_required",
            "web.search" => "web_search_provider_not_configured",
            "calendar.event.create" or "calendar.event.list" => "calendar_account_adapter_required",
            "email.latest.read" or "email.latest.reply" => "outlook_authenticated_profile_required",
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

    private static bool ProcessExists(string name)
    {
        Process[] processes = Process.GetProcessesByName(name);
        try { return processes.Length > 0; }
        finally { foreach (Process process in processes) process.Dispose(); }
    }
}
