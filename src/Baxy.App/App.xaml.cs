using System.Diagnostics.CodeAnalysis;
using System.Threading;
using System.Windows;

namespace Baxy.App;

[SuppressMessage(
    "Design",
    "CA1001:Types that own disposable fields should be disposable",
    Justification = "WPF owns the Application lifetime; OnExit releases the mutex deterministically.")]
public partial class App : Application
{
    private const string InstanceMutexName = @"Local\BAXY.Product.App";
    // FT/proveedores goal (review of the App): BAXY started again while it runs (hidden in the tray) exited without a
    // word; it asks the running one to show its window, as a click on the tray icon does.
    private const string ShowRequestName = @"Local\BAXY.Product.App.Show";
    // And the development launcher (main.py) asks it to exit as the tray's «Salir» does (the conversation kept,
    // the icon removed) before it would end it by force.
    private const string ExitRequestName = @"Local\BAXY.Product.App.Exit";
    private Mutex? _instanceMutex;
    private PresenceHost? _presence;
    private EventWaitHandle? _showRequest;
    private RegisteredWaitHandle? _showWait;
    private EventWaitHandle? _exitRequest;
    private RegisteredWaitHandle? _exitWait;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.ProcessStart);

        _instanceMutex = new Mutex(initiallyOwned: true, InstanceMutexName, out var isFirstInstance);
        if (!isFirstInstance)
        {
            // Otra instancia ya posee el escritorio. Se registra para que un
            // diagnóstico de arranque distinga «no arrancó» de «cedió el turno».
            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "process",
                ShellTraceStages.ProcessYielded);
            _instanceMutex.Dispose();
            _instanceMutex = null;
            if (ProductConductorHost.IsRequested(e.Args))
            {
                Console.Error.WriteLine(
                    "{\"type\":\"terminal\",\"kind\":\"blocked_environment\",\"diagnostic\":\"instance_already_running\"}");
                Shutdown(2);
                return;
            }

            try
            {
                if (EventWaitHandle.TryOpenExisting(ShowRequestName, out EventWaitHandle? show))
                {
                    using (show)
                        _ = show.Set();
                }
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or WaitHandleCannotBeOpenedException)
            {
                // The running BAXY cannot be asked: it stays as it is.
            }

            Shutdown(0);
            return;
        }

        if (ProductConductorHost.IsRequested(e.Args))
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Startup,
                "process",
                ShellTraceStages.WindowCreated);
            Dispatcher.BeginInvoke(async () =>
            {
                int code = 1;
                try
                {
                    code = await ProductConductorHost.RunAsync(e.Args, Dispatcher);
                }
                catch (Exception)
                {
                    Console.Error.WriteLine(
                        "{\"type\":\"terminal\",\"kind\":\"blocked_environment\",\"diagnostic\":\"conductor_failed\"}");
                    code = 1;
                }

                Shutdown(code);
            });
            return;
        }

        _presence = PresenceHost.CreateDefault();
        _presence.Start(e.Args);
        PresenceHost presence = _presence;
        _showRequest = new EventWaitHandle(false, EventResetMode.AutoReset, ShowRequestName);
        _showWait = ThreadPool.RegisterWaitForSingleObject(
            _showRequest, (_, _) => presence.ShowMainWindow(), null, Timeout.Infinite, executeOnlyOnce: false);
        _exitRequest = new EventWaitHandle(false, EventResetMode.AutoReset, ExitRequestName);
        _exitWait = ThreadPool.RegisterWaitForSingleObject(
            _exitRequest, (_, _) => Dispatcher.BeginInvoke(presence.RequestExit), null, Timeout.Infinite,
            executeOnlyOnce: true);
        var window = new MainWindow(_presence);
        MainWindow = window;
        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.WindowCreated);
        window.Show();
        if (_presence.StartHidden)
        {
            window.Hide();
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Startup,
            "process",
            ShellTraceStages.WindowShown);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _exitWait?.Unregister(null);
        _exitWait = null;
        _exitRequest?.Dispose();
        _exitRequest = null;
        _showWait?.Unregister(null);
        _showWait = null;
        _showRequest?.Dispose();
        _showRequest = null;
        _presence?.Dispose();
        _presence = null;
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
