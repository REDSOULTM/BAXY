using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real (tandas 4–7, the official window): «abre el homescreen» minimized BAXY's own window with the rest, and
/// its reply went into a minimized window. Showing the desktop leaves the companion the person talks to on screen.
/// </summary>
[TestFixture]
public sealed class WindowMinimizeAllOwnWindowTests
{
    [TestCase("Baxy")]
    [TestCase("Baxy.App")]
    public async Task ShowingTheDesktopLeavesBaxyOnScreen(string ownProcess)
    {
        var platform = new DesktopPlatform(("editor", "normal"), (ownProcess, "normal"), ("msedge", "maximized"));

        WindowMinimizeAllResult result = await new WindowsWindowControlProvider(platform).MinimizeAllAsync(CancellationToken.None);

        Assert.That(platform.Minimized, Is.EquivalentTo(new[] { "editor", "msedge" }));
        Assert.That(result.Verified, Is.True);
    }

    [Test]
    public async Task OnlyBaxyVisibleIsAlreadyTheDesktop()
    {
        var platform = new DesktopPlatform(("Baxy", "normal"));

        WindowMinimizeAllResult result = await new WindowsWindowControlProvider(platform).MinimizeAllAsync(CancellationToken.None);

        Assert.That(platform.Minimized, Is.Empty);
        Assert.That(result.Verified, Is.True);
    }

    private sealed class DesktopPlatform : IWindowControlPlatform
    {
        private readonly Dictionary<WindowIdentity, (string Process, string State)> _state;

        public DesktopPlatform(params (string Process, string State)[] windows)
        {
            _state = windows
                .Select((window, index) => (Identity: new WindowIdentity(index + 1, index + 10, index, window.Process,
                    DateTimeOffset.UnixEpoch), window))
                .ToDictionary(pair => pair.Identity, pair => pair.window);
        }

        public List<string> Minimized { get; } = [];

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);

        public IReadOnlyList<WindowSnapshot> DesktopWindows() =>
            _state.Select(pair => Snapshot(pair.Key)).ToList();

        public WindowSnapshot Observe(WindowIdentity identity) => Snapshot(identity);

        public bool Execute(WindowIdentity identity, WindowControlAction action)
        {
            if (action == WindowControlAction.Minimize)
            {
                Minimized.Add(identity.ProcessName);
                _state[identity] = (identity.ProcessName, "minimized");
            }
            return true;
        }

        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;
        public bool RequestClose(WindowIdentity identity) => false;
        public bool RequestSystemClose(WindowIdentity identity) => false;
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private WindowSnapshot Snapshot(WindowIdentity identity) =>
            new(identity, _state[identity].State, false, new WindowBounds(0, 0, 640, 480), identity.ProcessName);
    }
}
