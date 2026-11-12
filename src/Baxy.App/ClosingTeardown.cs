using System.ComponentModel;
using System.Windows;

namespace Baxy.App;

/// <summary>
/// The main window's exit: its first Closing is cancelled and the teardown (view, bridge, core, mind) runs once; then
/// the window is closed for good and <c>closed</c> runs. CER1 (INFORME_UPD1, live 11-11: 3 of 8 asks to exit left BAXY
/// open, each with its line in unhandled.v1.jsonl): when everything the teardown waited for was already over, its
/// Close() came while that Closing was still running, and WPF refuses it (learn.microsoft.com, Window.Closing:
/// «InvalidOperationException … Close() is called while a window is closing», read 2026-11-11; github.com/dotnet/wpf,
/// Window.InternalClose → VerifyNotClosing). The last
/// Close() is posted to the window's dispatcher, which runs it after the handler that cancelled has returned. A
/// teardown that fails is recorded and the window still closes: the person asked to exit.
/// </summary>
internal sealed class ClosingTeardown(Window window, Func<Task> teardown, Action closed, string? directory = null)
{
    private bool _started;
    private bool _over;

    /// <summary>The teardown ran: the next Closing goes through.</summary>
    internal bool IsOver => _over;

    internal void OnClosing(CancelEventArgs eventArgs)
    {
        if (_over)
        {
            return;
        }

        eventArgs.Cancel = true;
        // A second ask while the first is under way (the tray's Exit after the exit event) finds it running.
        if (_started)
        {
            return;
        }

        _started = true;
        UnhandledFailures.Watch(TearDownThenCloseAsync(), "exit", directory);
    }

    private async Task TearDownThenCloseAsync()
    {
        try
        {
            await teardown();
        }
        catch (Exception exception)
        {
            UnhandledFailures.Record("exit", exception, directory);
        }

        _over = true;
        _ = window.Dispatcher.BeginInvoke(() =>
        {
            window.Close();
            closed();
        });
    }
}
