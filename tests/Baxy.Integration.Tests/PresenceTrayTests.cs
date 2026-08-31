using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[Apartment(ApartmentState.STA)]
public sealed class PresenceTrayTests
{
    [Test]
    public void TrayWindowClassIsQueryableAfterNativeRegistration()
    {
        var shell = new RecordingTrayShell();
        using var tray = new PresenceTrayIcon(
            static () => { },
            static () => { },
            static () => { },
            shell);
        tray.Start();

        try
        {
            Assert.That(tray.IsRegistered, Is.True);
            Assert.That(tray.Handle, Is.Not.EqualTo(nint.Zero));
            Assert.That(PresenceTrayIcon.TryFind(out nint hwnd), Is.True);
            Assert.That(hwnd, Is.EqualTo(tray.Handle));
            Assert.That(shell.Added, Is.True);
            Assert.That(shell.CallbackMessage, Is.EqualTo(PresenceTrayIcon.CallbackMessage));
            Assert.That(shell.Tip, Is.EqualTo("BAXY"));
        }
        finally
        {
            tray.Dispose();
        }

        Assert.That(shell.Deleted, Is.True);
    }

    [Test]
    public void ListenAndExitCommandsArePostedToTheRegisteredWindow()
    {
        var events = new List<string>();
        var shell = new RecordingTrayShell();
        using var tray = new PresenceTrayIcon(
            () => events.Add("show"),
            () => events.Add("listen"),
            () => events.Add("exit"),
            shell);
        tray.Start();

        Assert.That(tray.Post(PresenceTrayIcon.ToggleListenMessage), Is.True);
        Pump();
        Assert.That(tray.Post(PresenceTrayIcon.ExitMessage), Is.True);
        Pump();

        Assert.That(events, Does.Contain("listen"));
        Assert.That(events, Does.Contain("exit"));
    }

    private static void Pump()
    {
        System.Windows.Threading.Dispatcher.CurrentDispatcher.Invoke(
            static () => { },
            System.Windows.Threading.DispatcherPriority.Background);
    }

    private sealed class RecordingTrayShell : ITrayIconShell
    {
        internal bool Added { get; private set; }

        internal bool Deleted { get; private set; }

        internal uint CallbackMessage { get; private set; }

        internal string? Tip { get; private set; }

        public bool Add(nint hwnd, uint callbackMessage, nint icon, string tip)
        {
            Added = hwnd != 0;
            CallbackMessage = callbackMessage;
            Tip = tip;
            return true;
        }

        public bool Delete(nint hwnd)
        {
            Deleted = hwnd != 0;
            return true;
        }
    }
}
