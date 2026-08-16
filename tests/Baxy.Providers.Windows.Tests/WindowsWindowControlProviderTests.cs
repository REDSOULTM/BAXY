using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsWindowControlProviderTests
{
    [Test]
    public async Task ForegroundResolveReturnsOnlyVerifiedActiveWindow()
    {
        var platform = new FakePlatform { Foreground = true };
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult result = await provider.ResolveForegroundAsync(
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Windows, Has.Count.EqualTo(1));
            Assert.That(result.Windows[0].ProcessName, Is.EqualTo("notepad"));
            Assert.That(result.Windows[0].Foreground, Is.True);
            Assert.That(result.Windows[0].WindowId, Does.Match("^win_[0-9a-f]{32}$"));
        });
    }

    [Test]
    public async Task ResolveIssuesOpaqueIdAndActionConsumesThenRefreshesIt()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad.exe", 10, CancellationToken.None);
        string firstId = resolved.Windows.Single().WindowId;
        WindowActionResult focused = await provider.ExecuteAsync(
            firstId, WindowControlAction.Focus, CancellationToken.None);
        WindowActionResult replayed = await provider.ExecuteAsync(
            firstId, WindowControlAction.Focus, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(resolved.Succeeded, Is.True);
            Assert.That(resolved.Verified, Is.True);
            Assert.That(firstId, Does.Match("^win_[0-9a-f]{32}$"));
            Assert.That(focused.Succeeded, Is.True);
            Assert.That(focused.Verified, Is.True);
            Assert.That(focused.Window!.Foreground, Is.True);
            Assert.That(focused.Window.WindowId, Is.Not.EqualTo(firstId));
            Assert.That(replayed.Succeeded, Is.False);
            Assert.That(replayed.ErrorCode,
                Is.EqualTo(WindowControlErrorCodes.InvalidOrExpiredWindowId));
        });
    }

    [Test]
    public async Task ChangedIdentityFailsClosedBeforeDispatch()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);
        platform.IdentityChanged = true;

        WindowActionResult result = await provider.ExecuteAsync(
            resolved.Windows.Single().WindowId,
            WindowControlAction.Minimize,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ErrorCode,
                Is.EqualTo(WindowControlErrorCodes.WindowIdentityChanged));
            Assert.That(platform.ExecuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task CloseConsumesHandleAndSucceedsOnlyAfterIndependentAbsenceProbe()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);

        WindowCloseResult closed = await provider.CloseAsync(
            resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(closed.Succeeded, Is.True);
            Assert.That(closed.Verified, Is.True);
            Assert.That(closed.ProcessId, Is.EqualTo(42));
            Assert.That(platform.CloseCalls, Is.EqualTo(1));
            Assert.That(platform.SystemCloseCalls, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task CloseFallsBackToVerifiedSystemCommandForHostedOrUiAccessWindows(
        bool primaryAccepted)
    {
        var platform = new FakePlatform
        {
            PrimaryCloseAccepted = primaryAccepted,
            PrimaryCloseCloses = false,
            SystemCloseAccepted = true,
            SystemCloseCloses = true,
        };
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);

        WindowCloseResult result = await provider.CloseAsync(
            resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.CloseCalls, Is.EqualTo(1));
            Assert.That(platform.SystemCloseCalls, Is.EqualTo(1));
            Assert.That(platform.Closed, Is.True);
        });
    }

    [TestCase(WindowControlAction.Minimize, "minimized", false)]
    [TestCase(WindowControlAction.Maximize, "maximized", false)]
    [TestCase(WindowControlAction.Restore, "normal", false)]
    public async Task WindowStateActionsWaitForObservableConvergence(
        WindowControlAction action,
        string expectedState,
        bool expectedForeground)
    {
        var platform = new FakePlatform
        {
            ActionConvergenceDelayCount = 3,
            Foreground = action == WindowControlAction.Minimize,
        };
        if (action == WindowControlAction.Restore)
        {
            platform.SetInitialState("maximized");
        }
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);

        WindowActionResult result = await provider.ExecuteAsync(
            resolved.Windows.Single().WindowId, action, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Window?.State, Is.EqualTo(expectedState));
            Assert.That(result.Window?.Foreground, Is.EqualTo(expectedForeground));
            Assert.That(platform.DelayCalls, Is.EqualTo(3));
            Assert.That(platform.ExecuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task MoveAndResizePreserveUnchangedDimensionsAndVerifyExactBounds()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult first = await provider.ResolveAsync("notepad", 10, CancellationToken.None);
        WindowActionResult moved = await provider.SetBoundsAsync(
            first.Windows.Single().WindowId, 20, 30, null, null, CancellationToken.None);
        WindowActionResult resized = await provider.SetBoundsAsync(
            moved.Window!.WindowId, null, null, 800, 600, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(moved.Succeeded, Is.True);
            Assert.That((moved.Window.X, moved.Window.Y), Is.EqualTo((20, 30)));
            Assert.That((moved.Window.Width, moved.Window.Height), Is.EqualTo((640, 480)));
            Assert.That((resized.Window!.X, resized.Window.Y), Is.EqualTo((20, 30)));
            Assert.That((resized.Window.Width, resized.Window.Height), Is.EqualTo((800, 600)));
            Assert.That(platform.SetBoundsCalls, Is.EqualTo(2));
        });
    }

    [TestCase("")]
    [TestCase("C:\\Windows\\notepad.exe")]
    [TestCase("notepad:evil")]
    public async Task ResolveRejectsUnboundedOrPathLikeSelectors(string selector)
    {
        var provider = new WindowsWindowControlProvider(new FakePlatform());

        WindowResolveResult result = await provider.ResolveAsync(
            selector, 10, CancellationToken.None);

        Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidSelector));
    }

    private sealed class FakePlatform : IWindowControlPlatform
    {
        private readonly WindowIdentity _identity = new(
            (nint)0x1234, 42, 638_880_000_000_000_000, "notepad", DateTimeOffset.UnixEpoch);
        private string _state = "normal";
        private bool _foreground;
        private WindowBounds _bounds = new(0, 0, 640, 480);

        public DateTimeOffset UtcNow { get; set; } =
            new(2026, 7, 16, 0, 0, 0, TimeSpan.Zero);
        public bool IdentityChanged { get; set; }
        public int ExecuteCalls { get; private set; }
        public int CloseCalls { get; private set; }
        public int SystemCloseCalls { get; private set; }
        public bool Closed { get; private set; }
        public int SetBoundsCalls { get; private set; }
        public int DelayCalls { get; private set; }
        public int ActionConvergenceDelayCount { get; set; }
        public bool PrimaryCloseAccepted { get; set; } = true;
        public bool PrimaryCloseCloses { get; set; } = true;
        public bool SystemCloseAccepted { get; set; }
        public bool SystemCloseCloses { get; set; }
        private WindowControlAction? _pendingAction;
        public bool Foreground
        {
            get => _foreground;
            set => _foreground = value;
        }

        public WindowSnapshot? FindForegroundWindow() => _foreground
            ? new WindowSnapshot(_identity, _state, true, _bounds)
            : null;

        public IReadOnlyList<WindowSnapshot> FindVisibleWindows(string processName, int limit)
        {
            Assert.That(processName, Is.EqualTo("notepad").IgnoreCase);
            Assert.That(limit, Is.EqualTo(10));
            return [new WindowSnapshot(_identity, _state, _foreground, _bounds)];
        }

        public WindowSnapshot Observe(WindowIdentity identity)
        {
            if (IdentityChanged || Closed) throw new WindowIdentityChangedException();
            Assert.That(identity.Handle, Is.EqualTo(_identity.Handle));
            Assert.That(identity.ProcessCreationTimeUtcTicks,
                Is.EqualTo(_identity.ProcessCreationTimeUtcTicks));
            return new WindowSnapshot(identity, _state, _foreground, _bounds);
        }

        public bool Execute(WindowIdentity identity, WindowControlAction action)
        {
            ExecuteCalls++;
            _ = Observe(identity);
            if (ActionConvergenceDelayCount > 0)
            {
                _pendingAction = action;
                return true;
            }

            ApplyAction(action);
            return true;
        }

        private void ApplyAction(WindowControlAction action)
        {
            switch (action)
            {
                case WindowControlAction.Focus:
                    _foreground = true;
                    _state = "normal";
                    break;
                case WindowControlAction.Minimize:
                    _foreground = false;
                    _state = "minimized";
                    break;
                case WindowControlAction.Maximize:
                    _state = "maximized";
                    break;
                case WindowControlAction.Restore:
                    _state = "normal";
                    break;
            }
        }

        public bool RequestClose(WindowIdentity identity)
        {
            CloseCalls++;
            _ = Observe(identity);
            if (PrimaryCloseCloses)
            {
                Closed = true;
            }
            return PrimaryCloseAccepted;
        }

        public bool RequestSystemClose(WindowIdentity identity)
        {
            SystemCloseCalls++;
            _ = Observe(identity);
            if (SystemCloseCloses)
            {
                Closed = true;
            }
            return SystemCloseAccepted;
        }

        public bool SetBounds(WindowIdentity identity, WindowBounds bounds)
        {
            SetBoundsCalls++;
            _ = Observe(identity);
            _bounds = bounds;
            return true;
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DelayCalls++;
            if (_pendingAction is { } action
                && DelayCalls >= ActionConvergenceDelayCount)
            {
                _pendingAction = null;
                ApplyAction(action);
            }
            return ValueTask.CompletedTask;
        }

        public void SetInitialState(string state) => _state = state;
    }
}
