using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M149 (D71.2, dueño 2026-10-03): «cierra la ventana activa» is the window the person is acting in. With Opera
/// in front and YouTube behind it, Opera — never YouTube. When the person writes to BAXY its own window holds the
/// foreground, so the active window is the one right below it in the z-order that is not BAXY's. Any other
/// foreground (the harness guard Notepad, D17) stays what it was.
/// </summary>
[TestFixture]
public sealed class WindowActiveBehindBaxyTests
{
    [TestCase("Baxy")]
    [TestCase("Baxy.App")]
    public async Task BaxyInFrontNamesTheWindowThePersonWasUsingNotTheOneBehindIt(string ownProcess)
    {
        var platform = new ZOrderPlatform(
            (ownProcess, "normal", "BAXY"),
            ("opera", "maximized", "Opera"),
            ("msedge", "normal", "YouTube - Microsoft Edge"));
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult result = await provider.ResolveForegroundAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Windows.Select(static window => window.ProcessName), Is.EqualTo(new[] { "opera" }));
            Assert.That(result.Windows[0].Foreground, Is.True, "the person's active window");
            Assert.That(result.Windows[0].Title, Is.EqualTo("Opera"));
        });
    }

    [Test]
    public async Task ClosingTheActiveWindowBehindBaxyClosesThatWindowAndNotBaxy()
    {
        var platform = new ZOrderPlatform(
            ("Baxy", "normal", "BAXY"),
            ("opera", "normal", "Opera"),
            ("msedge", "normal", "YouTube - Microsoft Edge"));
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult active = await provider.ResolveForegroundAsync(CancellationToken.None);
        WindowCloseResult closed = await provider.CloseAsync(active.Windows[0].WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(closed.Succeeded, Is.True);
            Assert.That(closed.Verified, Is.True);
            Assert.That(platform.CloseRequests, Is.EqualTo(new[] { "opera" }));
        });
    }

    [Test]
    public async Task BaxysOwnAuxiliaryAndMinimizedWindowsAreSkipped()
    {
        var platform = new ZOrderPlatform(
            ("Baxy", "normal", "BAXY"),
            ("Baxy", "normal", "BAXY — ajustes"),
            ("Spotify", "minimized", "Spotify Premium"),
            ("notepad", "normal", "notas.txt - Bloc de notas"),
            ("Code", "maximized", "Visual Studio Code"));

        WindowResolveResult result = await new WindowsWindowControlProvider(platform)
            .ResolveForegroundAsync(CancellationToken.None);

        Assert.That(result.Windows.Select(static window => window.ProcessName), Is.EqualTo(new[] { "notepad" }));
    }

    [Test]
    public async Task NothingBehindBaxyIsSaidAndNothingIsNamed()
    {
        var platform = new ZOrderPlatform(
            ("Baxy", "normal", "BAXY"),
            ("Spotify", "minimized", "Spotify Premium"));

        WindowResolveResult result = await new WindowsWindowControlProvider(platform)
            .ResolveForegroundAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.Windows, Is.Empty);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.WindowNotFound));
        });
    }

    [Test]
    public async Task TheHarnessGuardInFrontStaysTheActiveWindow()
    {
        // D17: the official-run guard keeps a disposable Notepad in front so «ciérralo» never names VS Code.
        var platform = new ZOrderPlatform(
            ("Notepad", "normal", "baxy-guardia.txt: Bloc de notas"),
            ("Baxy", "normal", "BAXY"),
            ("Code", "maximized", "Visual Studio Code"));

        WindowResolveResult result = await new WindowsWindowControlProvider(platform)
            .ResolveForegroundAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Windows.Select(static window => window.ProcessName), Is.EqualTo(new[] { "Notepad" }));
            Assert.That(result.Windows[0].Foreground, Is.True);
            Assert.That(platform.BehindReads, Is.Zero, "a foreground that is not BAXY's is never looked behind");
        });
    }

    [Test]
    public async Task TheFrontChangingWhileReadingFailsClosed()
    {
        var platform = new ZOrderPlatform(
            ("Baxy", "normal", "BAXY"),
            ("opera", "normal", "Opera"),
            ("msedge", "normal", "YouTube - Microsoft Edge"))
        {
            // Between the read of the window behind BAXY and its verification the person clicked YouTube.
            OnBehindRead = static platform => platform.BringToFront("msedge"),
        };

        WindowResolveResult result = await new WindowsWindowControlProvider(platform)
            .ResolveForegroundAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.Windows, Is.Empty);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
        });
    }

    /// <summary>Top-level windows in z-order, the first one in front.</summary>
    private sealed class ZOrderPlatform : IWindowControlPlatform
    {
        private readonly List<WindowIdentity> _order;
        private readonly Dictionary<WindowIdentity, (string State, string Title)> _windows;

        public ZOrderPlatform(params (string Process, string State, string Title)[] windows)
        {
            _order = windows.Select((window, index) => new WindowIdentity(index + 1, index + 10, index,
                window.Process, DateTimeOffset.UnixEpoch)).ToList();
            _windows = _order.Zip(windows).ToDictionary(pair => pair.First, pair => (pair.Second.State, pair.Second.Title));
        }

        public int BehindReads { get; private set; }
        public List<string> CloseRequests { get; } = [];
        public Action<ZOrderPlatform>? OnBehindRead { get; init; }

        public void BringToFront(string process)
        {
            WindowIdentity identity = _order.First(window => window.ProcessName == process);
            _order.Remove(identity);
            _order.Insert(0, identity);
        }

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => _order.Count == 0 ? null : Snapshot(_order[0]);

        public IReadOnlyList<WindowSnapshot> DesktopWindowsBehind(WindowIdentity front)
        {
            BehindReads++;
            int index = _order.FindIndex(window => window.Handle == front.Handle);
            List<WindowSnapshot> behind = index < 0 ? [] : _order.Skip(index + 1).Select(Snapshot).ToList();
            OnBehindRead?.Invoke(this);
            return behind;
        }

        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);

        public WindowSnapshot Observe(WindowIdentity identity)
        {
            WindowIdentity known = _order.FirstOrDefault(window => window.Handle == identity.Handle)
                ?? throw new WindowIdentityChangedException();
            return Snapshot(known);
        }

        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;

        public bool RequestClose(WindowIdentity identity)
        {
            WindowIdentity known = _order.First(window => window.Handle == identity.Handle);
            CloseRequests.Add(known.ProcessName);
            _order.Remove(known);
            return true;
        }

        public bool RequestSystemClose(WindowIdentity identity) => false;
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private WindowSnapshot Snapshot(WindowIdentity identity) =>
            new(identity, _windows[identity].State, _order.Count > 0 && _order[0].Handle == identity.Handle,
                new WindowBounds(0, 0, 640, 480), _windows[identity].Title);
    }
}
