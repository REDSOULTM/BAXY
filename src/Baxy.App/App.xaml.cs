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
            Shutdown(0);
            return;
        }

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
    }

    protected override void OnExit(ExitEventArgs e)
    {
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
