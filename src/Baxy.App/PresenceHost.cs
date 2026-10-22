namespace Baxy.App;

/// <summary>
/// Daily presence: the tray icon, Windows autostart and the heartbeat.
/// </summary>
internal sealed class PresenceHost : IDisposable
{
    private readonly WindowsAutostartRegistration _autostart;
    private PresenceTrayIcon? _tray;
    private Heartbeat? _heartbeat;
    private ProposalToast? _toast;
    private Presentation.TrayMenu? _menu;
    private MainWindow? _window;
    private MainWindowViewModel? _viewModel;
    private bool _exitRequested;
    private bool _disposed;

    private PresenceHost(WindowsAutostartRegistration autostart)
    {
        _autostart = autostart;
    }

    internal static PresenceHost CreateDefault() => new(WindowsAutostartRegistration.CreateDefault());

    internal bool StartHidden { get; private set; }

    internal bool IsExitRequested => _exitRequested;

    internal void Start(IReadOnlyList<string> arguments)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        StartHidden = WindowsAutostartRegistration.IsStartHidden(arguments);
        // The owner may switch the sign-in start off in Settings; then it is never written back on its own.
        if (FieldSettings.CreateDefault().AutostartWanted)
        {
            _autostart.EnsureRegistered(arguments);
        }
        _tray = new PresenceTrayIcon(ShowMainWindow, ShowMenu);
        _tray.Start();
    }

    internal void Attach(MainWindow window, MainWindowViewModel viewModel)
    {
        ArgumentNullException.ThrowIfNull(window);
        ArgumentNullException.ThrowIfNull(viewModel);
        _window = window;
        _viewModel = viewModel;
        _viewModel.NotificationRequested += text => _tray?.Notify(text);
        MainWindowViewModel answering = viewModel;
        _toast = new ProposalToast();
        _viewModel.ProposalNotificationRequested += (question, why, asked) =>
        {
            // The toast answers the proposal it shows, never one asked after it (2026-10-22, review of the App).
            if (_toast?.Show(question, why, approve => window.Dispatcher.InvokeAsync(() => answering.AnswerConfirmationAsync(
                    approve, System.Diagnostics.Stopwatch.GetTimestamp(), CancellationToken.None, asked))) != true)
            {
                _tray?.Notify(question);
            }
        };
        _viewModel.ConfirmationResolved += _ => _toast?.Hide();
        if (Heartbeat.Enabled && _heartbeat is null)
        {
            MainWindowViewModel beating = viewModel;
            _heartbeat = new Heartbeat(
                (moment, speak) => window.Dispatcher.InvokeAsync(
                    () => beating.RunBeatAsync(moment, speak, CancellationToken.None)).Task.Unwrap(),
                () => window.Dispatcher.Invoke(() => beating.CanBeat),
                () => window.Dispatcher.Invoke(() => (IReadOnlyList<ConversationMessage>)[.. beating.Messages]),
                () => window.Dispatcher.InvokeAsync(() => beating.RememberedAsync(CancellationToken.None)).Task.Unwrap(),
                () => window.Dispatcher.InvokeAsync(() => beating.PendingRemindersAsync(CancellationToken.None)).Task.Unwrap(),
                beating.Settings.QuietDuring,
                activity => window.Dispatcher.BeginInvoke(() => beating.ReportActivity(activity)));
            _heartbeat.Start();
        }

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

    // BAXY's own tray menu (design v4) at the pointer, with what BAXY is doing now; one open at a time.
    private void ShowMenu(int x, int y)
    {
        MainWindowViewModel? viewModel = _viewModel;
        _menu?.Close();
        var state = new Presentation.TrayMenu.State(
            viewModel is { IsListening: true } or { IsWakeListening: true },
            viewModel?.IsMicAvailable == true,
            viewModel?.IsPowered != false,
            viewModel is { IsReady: true, IsMindReady: true });
        _menu = new Presentation.TrayMenu(state, ShowMainWindow, ToggleListen, TogglePower, RequestExit);
        _menu.Closed += (_, _) => _menu = null;
        _menu.ShowAt(x, y);
    }

    private void TogglePower()
    {
        if (_viewModel is { } viewModel)
        {
            _ = viewModel.SetPowerAsync(!viewModel.IsPowered, CancellationToken.None);
        }
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

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _viewModel = null;
        _menu?.Close();
        _menu = null;
        _ = _heartbeat?.DisposeAsync().AsTask();
        _heartbeat = null;
        _tray?.Dispose();
        _tray = null;
        _window = null;
    }
}
