namespace Baxy.App;

/// <summary>
/// Orden de las marcas de arranque de la ventana. La vista y el motor arrancan
/// en paralelo; una sonda de comprobación (<c>--ui-probe</c>) corre después de
/// que la vista está lista y nunca retrasa las marcas de «lista», que así
/// miden el arranque y no la duración de la sonda.
/// </summary>
internal static class ShellStartupSequence
{
    internal static async Task RunAsync(
        Func<Task> startShell,
        Func<Task> initializeField,
        Func<Task>? probe)
    {
        ArgumentNullException.ThrowIfNull(startShell);
        ArgumentNullException.ThrowIfNull(initializeField);
        Record(ShellTraceStages.StartupShellBegin);
        Task shell = startShell();
        Task? probeRun = null;
        try
        {
            Record(ShellTraceStages.StartupFieldBegin);
            await initializeField();
            Record(ShellTraceStages.StartupFieldReady);
            probeRun = probe?.Invoke();
        }
        finally
        {
            await shell;
            Record(ShellTraceStages.StartupShellReady);
        }

        Record(ShellTraceStages.StartupReady);
        if (probeRun is not null)
        {
            await probeRun;
        }
    }

    private static void Record(string stage) =>
        ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", stage);
}
