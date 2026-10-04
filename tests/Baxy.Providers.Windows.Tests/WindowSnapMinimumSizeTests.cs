using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M159 (DEV-I v4w I-s048 «pasame la ventana de spotify a la derecha», I-w21-t2, H-w01-t2/t3, F-w28-t3): on a
/// 1536-wide work area half is 768, and Spotify will not be narrower than about 814. Windows keeps the asked position
/// and clamps the size, so the exact-half check failed every time («la verificación del lado derecho falló»). A
/// window whose own minimum is larger than the half ends flush against the asked edge at that minimum, inside the
/// work area, and the result says it did not fit (LargerThanRequested). Nothing here touches a real window.
/// </summary>
[TestFixture]
public sealed class WindowSnapMinimumSizeTests
{
    private static readonly WindowBounds WorkArea = new(0, 0, 1536, 816);

    // The real rows: Spotify already flush right (I-s048, F-w28-t3), past the right edge (I-w21-t2), and elsewhere.
    [TestCase(722, 0, 814, 816)]
    [TestCase(768, 0, 814, 816)]
    [TestCase(100, 50, 900, 600)]
    public async Task AWindowWiderThanHalfEndsFlushRightAtItsMinimum(int x, int y, int width, int height)
    {
        var platform = new SnapPlatform(new WindowBounds(x, y, width, height)) { MinimumWidth = 814 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(Bounds(result.Window!), Is.EqualTo(new WindowBounds(722, 0, 814, 816)));
            Assert.That(result.LargerThanRequested, Is.EqualTo(new WindowRequestedSize(768, 816)));
            Assert.That(platform.Moves, Is.EqualTo(new[]
            {
                new WindowBounds(768, 0, 768, 816),
                new WindowBounds(722, 0, 814, 816),
            }));
        });
    }

    // H-w01-t3 «…to the left»: the same window, the other side; Windows' clamp already leaves it on the left edge.
    [Test]
    public async Task AWindowWiderThanHalfOnTheLeftNeedsNoSecondMove()
    {
        var platform = new SnapPlatform(new WindowBounds(768, 0, 800, 816)) { MinimumWidth = 800 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "left");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(Bounds(result.Window!), Is.EqualTo(new WindowBounds(0, 0, 800, 816)));
            Assert.That(result.LargerThanRequested, Is.EqualTo(new WindowRequestedSize(768, 816)));
            Assert.That(platform.Moves, Has.Count.EqualTo(1));
        });
    }

    // A window that pulls itself back onto the screen after the clamp (Spotify's 722) is already flush.
    [Test]
    public async Task AWindowThatPullsItselfBackOnScreenIsAcceptedWhereItSettled()
    {
        var platform = new SnapPlatform(new WindowBounds(100, 0, 900, 816))
        {
            MinimumWidth = 814,
            PullsBackOnScreen = true,
        };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(Bounds(result.Window!), Is.EqualTo(new WindowBounds(722, 0, 814, 816)));
            Assert.That(result.LargerThanRequested, Is.Not.Null);
            Assert.That(platform.Moves, Has.Count.EqualTo(1));
        });
    }

    // Does not change: a window that fits takes the exact half, as before, and says nothing more.
    [TestCase("right", 768)]
    [TestCase("left", 0)]
    public async Task AWindowThatFitsTakesTheExactHalfAsBefore(string side, int x)
    {
        var platform = new SnapPlatform(new WindowBounds(100, 50, 1000, 700)) { MinimumWidth = 500 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, side);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(Bounds(result.Window!), Is.EqualTo(new WindowBounds(x, 0, 768, 816)));
            Assert.That(result.LargerThanRequested, Is.Null);
            Assert.That(platform.Moves, Has.Count.EqualTo(1));
        });
    }

    // Does not change: a read taken before the move landed (the old, wider bounds) is not taken for a minimum.
    [Test]
    public async Task AStaleReadOfTheOldBoundsIsNotTakenForAMinimum()
    {
        var platform = new SnapPlatform(new WindowBounds(768, 0, 1000, 816)) { StaleReadsAfterMove = 1 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(Bounds(result.Window!), Is.EqualTo(new WindowBounds(768, 0, 768, 816)));
            Assert.That(result.LargerThanRequested, Is.Null);
        });
    }

    // Still a failure: the window wider than half never reaches the asked edge.
    [Test]
    public async Task AWindowThatNeverReachesTheAskedEdgeStillFails()
    {
        var platform = new SnapPlatform(new WindowBounds(100, 0, 900, 816))
        {
            MinimumWidth = 814,
            IgnoresMovesAfterFirst = true,
        };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(result.LargerThanRequested, Is.Null);
        });
    }

    // Still a failure: a minimum wider than the whole work area does not fit anywhere on it.
    [Test]
    public async Task AWindowWiderThanTheWorkAreaStillFails()
    {
        var platform = new SnapPlatform(new WindowBounds(0, 0, 1600, 816)) { MinimumWidth = 1600 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "left");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
        });
    }

    // Still a failure: a window that ends smaller than the half (a maximum size) is not a minimum.
    [Test]
    public async Task AWindowSmallerThanTheHalfStillFails()
    {
        var platform = new SnapPlatform(new WindowBounds(100, 0, 500, 500)) { MaximumWidth = 600 };
        var provider = new WindowsWindowControlProvider(platform);

        WindowActionResult result = await SnapAsync(provider, "right");

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
        });
    }

    private static async Task<WindowActionResult> SnapAsync(WindowsWindowControlProvider provider, string side)
    {
        WindowResolveResult resolved = await provider.ResolveForegroundAsync(CancellationToken.None);
        Assert.That(resolved.Succeeded, Is.True);
        return await provider.SnapAsync(resolved.Windows.Single().WindowId, side, CancellationToken.None);
    }

    private static WindowBounds Bounds(WindowCandidate window) =>
        new(window.X, window.Y, window.Width, window.Height);

    /// <summary>One window on a 1536×816 work area that enforces its own minimum the way Windows does: the asked
    /// position is kept and the size clamped.</summary>
    private sealed class SnapPlatform(WindowBounds bounds) : IWindowControlPlatform
    {
        private readonly WindowIdentity _identity = new(
            (nint)0x5150, 77, 638_880_000_000_000_000, "Spotify", DateTimeOffset.UnixEpoch);
        private WindowBounds _bounds = bounds;
        private WindowBounds? _stale;
        private int _staleReads;

        public int MinimumWidth { get; init; }
        public int MaximumWidth { get; init; } = int.MaxValue;
        public bool PullsBackOnScreen { get; init; }
        public bool IgnoresMovesAfterFirst { get; init; }
        public int StaleReadsAfterMove { get; init; }
        public List<WindowBounds> Moves { get; } = [];
        public DateTimeOffset UtcNow { get; } = new(2026, 10, 4, 0, 0, 0, TimeSpan.Zero);

        public WindowSnapshot? FindForegroundWindow() => Snapshot(_bounds);

        public WindowEnumeration FindVisibleWindows(string processName, int limit,
            bool byTitle = false, int offset = 0, bool allWindows = false,
            CancellationToken cancellationToken = default) =>
            new([Snapshot(_bounds)], 1, true);

        public WindowSnapshot Observe(WindowIdentity identity)
        {
            Assert.That(identity.Handle, Is.EqualTo(_identity.Handle));
            if (_staleReads > 0 && _stale is not null)
            {
                _staleReads--;
                return Snapshot(_stale);
            }
            return Snapshot(_bounds);
        }

        public WindowBounds? WorkArea(WindowIdentity identity) => WindowSnapMinimumSizeTests.WorkArea;

        public bool SetBounds(WindowIdentity identity, WindowBounds requested)
        {
            Moves.Add(requested);
            if (IgnoresMovesAfterFirst && Moves.Count > 1)
            {
                return true;
            }
            _stale = _bounds;
            _staleReads = StaleReadsAfterMove;
            int width = Math.Min(Math.Max(requested.Width, MinimumWidth), MaximumWidth);
            int x = requested.X;
            int right = WindowSnapMinimumSizeTests.WorkArea.X + WindowSnapMinimumSizeTests.WorkArea.Width;
            if (PullsBackOnScreen && x + width > right)
            {
                x = right - width;
            }
            _bounds = new WindowBounds(x, requested.Y, width, requested.Height);
            return true;
        }

        public bool Execute(WindowIdentity identity, WindowControlAction action) => true;
        public bool RequestClose(WindowIdentity identity) => false;
        public bool RequestSystemClose(WindowIdentity identity) => false;

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
            ValueTask.CompletedTask;

        private WindowSnapshot Snapshot(WindowBounds current) =>
            new(_identity, "normal", true, current, "Mon Laferte - Mi Buen Amor");
    }
}
