using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.Threading;
using System.Windows;

namespace Baxy.App;

[SuppressMessage(
    "Design",
    "CA1001:Types that own disposable fields should be disposable",
    Justification = "WPF owns the Application lifetime; OnExit releases the mutex, tray and show-event.")]
public partial class App : Application
{
    private const string InstanceMutexName = @"Local\BAXY.Product.App";
    private const string ShowEventName = @"Local\BAXY.Product.Show";
    private Mutex? _instanceMutex;
    private EventWaitHandle? _showEvent;
    private Thread? _showWaiter;
    private TrayPresence? _tray;
    private bool _startHidden;

    internal bool QuitRequested { get; private set; }

    internal TrayPresence? Tray => _tray;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.ProcessStart);

        _startHidden = HasTrayArgument(e.Args);
        _instanceMutex = new Mutex(initiallyOwned: true, InstanceMutexName, out var isFirstInstance);
        if (!isFirstInstance)
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "process",
                ShellTraceStages.ProcessYielded);
            using var show = new EventWaitHandle(false, EventResetMode.AutoReset, ShowEventName);
            _ = show.Set();
            _instanceMutex.Dispose();
            _instanceMutex = null;
            Shutdown(0);
            return;
        }

        _showEvent = new EventWaitHandle(false, EventResetMode.AutoReset, ShowEventName);
        _showWaiter = new Thread(WaitForShowRequests)
        {
            IsBackground = true,
            Name = "BAXY-presence-show",
        };
        _showWaiter.Start();

        string? executable = Environment.ProcessPath;
        if (!string.IsNullOrWhiteSpace(executable) && File.Exists(executable))
        {
            WindowsAutostart.EnsureRegistered(executable);
        }

        _tray = new TrayPresence();
        _tray.ShowRequested += ShowFromTray;
        _tray.QuitRequested += RequestQuit;
        MainWindow = new MainWindow();
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.WindowCreated);
        MainWindow.Show();
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.WindowShown);
        if (_startHidden && MainWindow is MainWindow window)
        {
            window.HideToTray();
        }
    }

    internal void ShowFromTray()
    {
        if (MainWindow is not MainWindow window)
        {
            return;
        }

        window.RestoreFromTray();
    }

    internal void RequestQuit()
    {
        QuitRequested = true;
        MainWindow?.Close();
    }

    private void WaitForShowRequests()
    {
        EventWaitHandle? handle = _showEvent;
        if (handle is null)
        {
            return;
        }

        while (true)
        {
            try
            {
                if (!handle.WaitOne())
                {
                    return;
                }
            }
            catch (ObjectDisposedException)
            {
                return;
            }

            _ = Dispatcher.BeginInvoke(ShowFromTray);
        }
    }

    private static bool HasTrayArgument(string[] args)
    {
        foreach (string argument in args)
        {
            if (string.Equals(argument, WindowsAutostart.TrayArgument, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _tray?.Dispose();
        _tray = null;
        _showEvent?.Dispose();
        _showEvent = null;
        if (_instanceMutex is not null)
        {
            try
            {
                _instanceMutex.ReleaseMutex();
            }
            catch (ApplicationException)
            {
                // The mutex can already be released during an abnormal shutdown.
            }

            _instanceMutex.Dispose();
            _instanceMutex = null;
        }

        base.OnExit(e);
    }
}
