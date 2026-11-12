using System.Diagnostics.CodeAnalysis;
using System.Windows;

namespace Baxy.App;

[SuppressMessage(
    "Design",
    "CA1001:Types that own disposable fields should be disposable",
    Justification = "WPF owns the Application lifetime; OnExit releases the mutex deterministically.")]
public partial class App : Application
{
    private const string InstanceMutexName = @"Local\BAXY.Product.App";
    private const int StartWindowFailed = 3;
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
    private string? _sessionEnding;
    private DateTimeOffset _startedAt;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        // SRCH1: baxy-core's hidden page reader is this executable started for that alone: no instance of its own, no
        // window shown, no trace of an App start (HiddenPageReader).
        if (HiddenPageReader.IsRequested(e.Args))
        {
            HiddenPageReader.Start(this, e.Args[1]);
            return;
        }

        // INS-1: a store's uninstall starts this executable for that alone (ScheduledRingsUninstall): no instance, no
        // window, and it ends by itself.
        if (ScheduledRingsUninstall.IsRequested(e.Args))
        {
            Shutdown(ScheduledRingsUninstall.Run());
            return;
        }

        UnhandledFailures.Attach(this);
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
                catch (Exception exception)
                {
                    // uso-116: the cause travels with the failure; «conductor_failed» alone left a run with nothing to read.
                    Console.Error.WriteLine(new System.Text.Json.Nodes.JsonObject
                    {
                        ["type"] = "terminal",
                        ["kind"] = "blocked_environment",
                        ["diagnostic"] = "conductor_failed",
                        ["cause"] = $"{exception.GetType().Name}: {exception.Message}",
                    }.ToJsonString());
                    code = 1;
                }

                Shutdown(code);
            });
            return;
        }

        try
        {
            StartWindow(e);
        }
        catch (Exception exception)
        {
            // 2026-11-05 (a profile the private storage refuses): the dispatcher's handler absorbed this, and BAXY stayed
            // alive with no window, holding the one instance's mutex: every later start yielded to it and nothing opened.
            UnhandledFailures.Record("startup", exception);
            if (!FieldUiProbe.IsRequested(e.Args))
            {
                MessageBox.Show(
                    UiLanguage.Say("BAXY no pudo abrirse. Vuelve a intentarlo; si se repite, reinstálalo: tus datos no se borran.",
                        "BAXY could not open. Try again; if it happens again, reinstall it: your data is not deleted."),
                    "BAXY",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
            }

            Shutdown(StartWindowFailed);
        }
    }

    private void StartWindow(StartupEventArgs e)
    {
        _presence = PresenceHost.CreateDefault();
        _presence.Start(e.Args);
        _startedAt = DateTimeOffset.UtcNow;
        MindRestarts.Record(new MindLoss(MindLoss.AppStart), TimeSpan.Zero);
        PresenceHost presence = _presence;
        _showRequest = new EventWaitHandle(false, EventResetMode.AutoReset, ShowRequestName);
        _showWait = ThreadPool.RegisterWaitForSingleObject(
            _showRequest, (_, _) => presence.ShowMainWindow(), null, Timeout.Infinite, executeOnlyOnce: false);
        _exitRequest = new EventWaitHandle(false, EventResetMode.AutoReset, ExitRequestName);
        // CER1: heard every time, not once. An ask that did not close BAXY (its Close() refused inside Closing) left
        // the update's installer and baxy.exit asking in vain; one while the first is under way changes nothing.
        _exitWait = ThreadPool.RegisterWaitForSingleObject(
            _exitRequest, (_, _) => Dispatcher.BeginInvoke(() => presence.RequestExit("exit_request")), null,
            Timeout.Infinite, executeOnlyOnce: false);
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

    protected override void OnSessionEnding(SessionEndingCancelEventArgs e)
    {
        _sessionEnding = "session_" + e.ReasonSessionEnding.ToString().ToLowerInvariant();
        base.OnSessionEnding(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        if (_presence is not null)
        {
            // Feria 2026-10-27: who closed it, so that a mind started anew by the App opened again reads as such.
            string via = _presence.ExitVia ?? _sessionEnding ?? "unrequested";
            MindRestarts.Record(new MindLoss(MindLoss.AppExit + "." + via, ExitCode: e.ApplicationExitCode),
                DateTimeOffset.UtcNow - _startedAt);
        }

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
