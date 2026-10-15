using System.Globalization;
using System.IO;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// Daily presence: tray, Windows autostart, published readiness, and idle
/// samples. Keep-warm stays on the live process_lifecycle path.
/// </summary>
internal sealed class PresenceHost : IDisposable
{
    internal static readonly TimeSpan IdleSamplePeriod = TimeSpan.FromSeconds(15);

    private readonly WindowsAutostartRegistration _autostart;
    private readonly PresenceStatusStore _store;
    private readonly PresenceIdleSampler _sampler;
    private readonly ITrayIconShell? _trayShell;
    private readonly bool _registerNativeTray;
    private DispatcherTimer? _idleTimer;
    private PresenceTrayIcon? _tray;
    private MainWindow? _window;
    private MainWindowViewModel? _viewModel;
    private bool _exitRequested;
    private bool _disposed;
    private bool _listeningSampled;
    private bool _sampling;

    internal PresenceHost(
        WindowsAutostartRegistration autostart,
        PresenceStatusStore store,
        PresenceIdleSampler sampler,
        ITrayIconShell? trayShell = null,
        bool registerNativeTray = true)
    {
        _autostart = autostart ?? throw new ArgumentNullException(nameof(autostart));
        _store = store ?? throw new ArgumentNullException(nameof(store));
        _sampler = sampler ?? throw new ArgumentNullException(nameof(sampler));
        _trayShell = trayShell;
        _registerNativeTray = registerNativeTray;
    }

    internal static PresenceHost CreateDefault() =>
        new(
            WindowsAutostartRegistration.CreateDefault(),
            PresenceStatusStore.CreateDefault(),
            new PresenceIdleSampler(OwnedProcessReader.CreateDefault()));

    internal bool StartHidden { get; private set; }

    internal bool IsExitRequested => _exitRequested;

    internal bool TrayRegistered => _tray?.IsRegistered == true;

    internal string? AutostartCommand { get; private set; }

    internal string StatusPath => _store.StatusPath;

    internal IReadOnlyList<PresenceIdleSnapshot> IdleSamples => _sampler.Samples;

    internal void Start(IReadOnlyList<string> arguments)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        StartHidden = WindowsAutostartRegistration.IsStartHidden(arguments);
        AutostartCommand = _autostart.EnsureRegistered(arguments);
        if (_registerNativeTray)
        {
            _tray = new PresenceTrayIcon(
                ShowMainWindow,
                ToggleListen,
                RequestExit,
                _trayShell);
            _tray.Start();
        }

        Publish();
    }

    internal void Attach(MainWindow window, MainWindowViewModel viewModel)
    {
        ArgumentNullException.ThrowIfNull(window);
        ArgumentNullException.ThrowIfNull(viewModel);
        _window = window;
        if (_viewModel is not null)
        {
            _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        }

        _viewModel = viewModel;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        Publish();
        SyncIdleTimer();
    }

    internal void ShowMainWindow()
    {
        MainWindow? window = _window;
        if (window is null)
        {
            return;
        }

        if (window.Dispatcher.CheckAccess())
        {
            window.Show();
            window.Activate();
            if (window.WindowState == System.Windows.WindowState.Minimized)
            {
                window.WindowState = System.Windows.WindowState.Normal;
            }

            return;
        }

        _ = window.Dispatcher.BeginInvoke(ShowMainWindow);
    }

    internal void ToggleListen()
    {
        MainWindow? window = _window;
        MainWindowViewModel? viewModel = _viewModel;
        if (window is null || viewModel is null)
        {
            return;
        }

        if (!window.Dispatcher.CheckAccess())
        {
            _ = window.Dispatcher.BeginInvoke(ToggleListen);
            return;
        }

        _ = viewModel.ToggleWakeVoiceAsync(CancellationToken.None);
    }

    internal void RequestExit()
    {
        _exitRequested = true;
        MainWindow? window = _window;
        if (window is null)
        {
            System.Windows.Application.Current?.Shutdown();
            return;
        }

        if (window.Dispatcher.CheckAccess())
        {
            window.Close();
            return;
        }

        _ = window.Dispatcher.BeginInvoke(window.Close);
    }

    internal void Publish()
    {
        MainWindowViewModel? viewModel = _viewModel;
        bool ready = viewModel?.IsReady == true;
        bool inputEnabled = viewModel?.IsInputEnabled == true;
        bool listening = viewModel is { IsListening: true } or { IsWakeListening: true };
        bool wakeListening = viewModel?.IsWakeListening == true;
        bool mindReady = viewModel?.IsMindReady == true;
        bool micAvailable = viewModel?.IsMicAvailable == true;
        DateTimeOffset? firstWake = viewModel?.FirstWakeUtc;
        string terminal = ResolveTerminal(viewModel);
        _tray?.SetListening(listening);
        var document = new PresenceStatusDocument(
            PresenceLimits.StatusSchema,
            DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ready,
            inputEnabled,
            listening,
            wakeListening,
            mindReady,
            micAvailable,
            firstWake?.ToString("O", CultureInfo.InvariantCulture),
            terminal,
            _tray?.Handle.ToInt64() ?? 0,
            TrayRegistered,
            _autostart.IsRegistered(),
            AutostartCommand,
            _sampler.Samples.Count > 0
                ? _sampler.Samples[^1].Processes
                : []);
        _store.WriteStatus(document);
    }

    /// <summary>
    /// Reads the view's state on the caller's (window) thread, the processes
    /// off it, and writes the sample back on the caller's thread. A tick that
    /// arrives while a read is still running is skipped, never queued.
    /// </summary>
    internal async Task<PresenceIdleSnapshot?> CaptureIdleSampleAsync()
    {
        if (_sampling)
        {
            return null;
        }

        _sampling = true;
        try
        {
            MainWindowViewModel? viewModel = _viewModel;
            PresenceIdleSnapshot snapshot = await _sampler.CaptureAsync(
                viewModel?.IsReady == true,
                viewModel?.IsInputEnabled == true,
                viewModel is { IsListening: true } or { IsWakeListening: true },
                viewModel?.FirstWakeUtc,
                ResolveTerminal(viewModel));
            if (_disposed)
            {
                return snapshot;
            }

            _store.AppendSample(snapshot);
            Publish();
            return snapshot;
        }
        finally
        {
            _sampling = false;
        }
    }

    private async void CaptureIdleSampleInBackground()
    {
        try
        {
            _ = await CaptureIdleSampleAsync();
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            // An idle sample is diagnostic: a failed read never reaches the person.
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        if (_idleTimer is not null)
        {
            _idleTimer.Stop();
            _idleTimer.Tick -= OnIdleTick;
        }
        if (_viewModel is not null)
        {
            _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
            _viewModel = null;
        }

        _tray?.Dispose();
        _tray = null;
        _window = null;
    }

    private void OnViewModelPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs eventArgs)
    {
        Publish();
        SyncIdleTimer();
    }

    private void SyncIdleTimer()
    {
        bool listening = _viewModel is { IsListening: true } or { IsWakeListening: true };
        if (listening)
        {
            if (!_listeningSampled)
            {
                CaptureIdleSampleInBackground();
                _listeningSampled = true;
            }

            if (!IdleTimer.IsEnabled)
            {
                IdleTimer.Start();
            }
        }
        else if (_idleTimer is { IsEnabled: true })
        {
            _idleTimer.Stop();
        }
    }

    private DispatcherTimer IdleTimer
    {
        get
        {
            if (_idleTimer is null)
            {
                _idleTimer = new DispatcherTimer { Interval = IdleSamplePeriod };
                _idleTimer.Tick += OnIdleTick;
            }

            return _idleTimer;
        }
    }

    private void OnIdleTick(object? sender, EventArgs eventArgs) => CaptureIdleSampleInBackground();

    private static string ResolveTerminal(MainWindowViewModel? viewModel)
    {
        if (viewModel is null)
        {
            return "starting";
        }

        if (viewModel.HasStartupError)
        {
            return "failed";
        }

        if (viewModel.IsReady)
        {
            return "ready";
        }

        return "starting";
    }
}
