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
    private Mutex? _instanceMutex;
    private PresenceHost? _presence;

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
