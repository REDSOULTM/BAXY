using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría final G1/G2: «cerrame todo» asks every desktop window but BAXY's own to close (no application is spared
/// by a list of its own); a window that asks to save stays and is said to remain; only a window BAXY's request reached
/// counts as closed, and one that ended without being asked is already gone. Renew al máximo (lote 4, d): the windows
/// no act reaches (a terminal, a console, an editor, a system tool) are kept too, and said so.
/// </summary>
[TestFixture]
public sealed class CloseAllTests
{
    [Test]
    public async Task OnlyWindowsBaxyAskedCountAsClosedAndOnlyBaxysOwnAreKept()
    {
        var platform = new DesktopPlatform(
            new("Spotify", Answer.Close),
            new("Discord", Answer.Close),
            new("Baxy", Answer.Close),
            new("notepad", Answer.AsksToSave),
            new("vanished", Answer.RefusedButGone));
        var provider = new WindowsWindowControlProvider(platform);

        WindowCloseAllResult result = await provider.CloseAllAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Found, Is.EqualTo(5));
            Assert.That(result.Kept, Is.EqualTo(1));
            Assert.That(result.KeptProcesses, Is.EqualTo(new[] { "Baxy" }));
            Assert.That(result.Closed, Is.EqualTo(2), "Spotify and Discord were asked and closed");
            Assert.That(result.ProtectedKept, Is.Zero);
            Assert.That(result.AlreadyGone, Is.EqualTo(1), "the window whose request Windows refused was not BAXY's");
            Assert.That(result.Remaining, Is.EqualTo(1));
            Assert.That(result.RemainingProcesses, Is.EqualTo(new[] { "notepad" }));
            Assert.That(platform.Asked, Does.Not.Contain("Baxy"));
        });
    }

    // Renew al máximo (lote 4, d): a console's close ends what runs in it without asking (Windows ends the processes
    // attached to it), and an editor or a terminal is where the developer's agent lives: «cerrame todo» leaves every
    // window an act would not reach (VisibleControlSurface.ProtectedFrom: a terminal, a console, an editor, a system
    // configuration tool) open, and says how many and which, as it says BAXY's own.
    [Test]
    public async Task TheProtectedWindowsAreLeftOpenAndSaidSo()
    {
        var platform = new DesktopPlatform(
            new("WindowsTerminal", Answer.Close),
            new("cmd", Answer.Close),
            new("powershell", Answer.Close),
            new("Code", Answer.Close),
            new("msconfig", Answer.Close),
            new("notepad", Answer.Close),
            new("Baxy", Answer.Close));
        var provider = new WindowsWindowControlProvider(platform);

        WindowCloseAllResult result = await provider.CloseAllAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.Asked, Is.EqualTo(new[] { "notepad" }), "no close reached a protected window");
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Found, Is.EqualTo(7));
            Assert.That(result.Closed, Is.EqualTo(1));
            Assert.That(result.Remaining, Is.Zero);
            Assert.That(result.Kept, Is.EqualTo(6));
            Assert.That(result.KeptProcesses, Is.EqualTo(new[] { "Baxy", "cmd", "Code", "msconfig", "powershell", "WindowsTerminal" }));
            Assert.That(result.ProtectedKept, Is.EqualTo(5), "BAXY's own is kept, not protected");
            Assert.That(result.ProtectedProcesses, Is.EqualTo(new[] { "cmd", "Code", "msconfig", "powershell", "WindowsTerminal" }));
        });
    }

    private enum Answer
    {
        Close,
        AsksToSave,
        RefusedButGone,
    }

    private sealed record Desktop(string Process, Answer Answer);

    private sealed class DesktopPlatform : IWindowControlPlatform
    {
        private readonly Dictionary<nint, (WindowIdentity Identity, Answer Answer)> _windows = [];
        private readonly HashSet<nint> _open = [];

        public DesktopPlatform(params Desktop[] windows)
        {
            nint handle = 100;
            foreach (Desktop window in windows)
            {
                handle++;
                _windows[handle] = (new WindowIdentity(handle, (int)handle, 1, window.Process, DateTimeOffset.UnixEpoch),
                    window.Answer);
                _open.Add(handle);
            }
        }

        public List<string> Asked { get; } = [];

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);

        public IReadOnlyList<WindowSnapshot> DesktopWindows() =>
            [.. _windows.Values.Select(window => Snapshot(window.Identity))];

        public WindowSnapshot Observe(WindowIdentity identity) =>
            _open.Contains(identity.Handle) ? Snapshot(identity) : throw new WindowIdentityChangedException();

        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;

        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;

        public bool RequestClose(WindowIdentity identity) => Request(identity);

        public bool RequestSystemClose(WindowIdentity identity) => Request(identity);

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private bool Request(WindowIdentity identity)
        {
            _ = Observe(identity);
            Asked.Add(identity.ProcessName);
            switch (_windows[identity.Handle].Answer)
            {
                case Answer.Close:
                    _open.Remove(identity.Handle);
                    return true;
                case Answer.RefusedButGone:
                    // Windows did not take the request; the window ended by itself.
                    _open.Remove(identity.Handle);
                    return false;
                default:
                    return true;
            }
        }

        private static WindowSnapshot Snapshot(WindowIdentity identity) =>
            new(identity, "normal", false, new WindowBounds(0, 0, 800, 600), identity.ProcessName);
    }
}
