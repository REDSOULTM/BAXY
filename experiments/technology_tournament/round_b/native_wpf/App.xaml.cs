using System.Windows;

namespace Baxy.Tournament.RoundB.Dotnet;

public partial class App : Application, IDisposable
{
    private Mutex? _singleInstance;

    protected override void OnStartup(StartupEventArgs e)
    {
        _singleInstance = new Mutex(initiallyOwned: true, "Local\\BAXY.RoundB.NativeWpf", out var created);
        if (!created)
        {
            Shutdown(0);
            return;
        }
        base.OnStartup(e);
        MainWindow = new MainWindow();
        MainWindow.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        Dispose();
        base.OnExit(e);
    }

    public void Dispose()
    {
        if (_singleInstance is not null)
        {
            try { _singleInstance.ReleaseMutex(); }
            catch (ApplicationException) { }
            _singleInstance.Dispose();
            _singleInstance = null;
        }
        GC.SuppressFinalize(this);
    }
}
