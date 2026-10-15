using System.Text.Json;
using Baxy.Contracts;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Review of fable/cu-v3-pausa: what was seen before the wait for the person's pause is not trusted after it. The
/// wait can last the lease's whole ceiling and happens exactly while the person is active, so a point located on the
/// earlier capture, or a baseline taken before it, may describe a window the person has since changed.
/// </summary>
[TestFixture]
public sealed class PauseRecheckTests
{
    private const nint Mission = 0x4660;

    [Test]
    public async Task ASurfaceThePersonScrolledWhileWaitedForIsRedrawnAndNotTheSame()
    {
        var surface = new FakeSurface(Capture(Mission, "aaaa"));
        var lease = new WaitingLease(() => surface.Current = Capture(Mission, "bbbb"));
        VisibleControlSurface.CapturedWindow located = surface.Current;

        _ = await lease.AcquireAsync(Mission, CancellationToken.None);
        VisibleControlSurface.SurfaceAfterWait recheck =
            await VisibleControlSurface.SurfaceAfterWaitAsync(located, surface.CaptureAsync, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(recheck.Same, Is.False);
            Assert.That(recheck.Redrawn, Is.True);
            Assert.That(recheck.Moved, Is.False);
            Assert.That(recheck.Again?.Sha256, Is.EqualTo("bbbb"), "the new capture is the post-read's baseline");
        });
    }

    [Test]
    public async Task AWindowMovedOrResizedWhileWaitedForHoldsNoLocatedPoint()
    {
        var surface = new FakeSurface(Capture(Mission, "aaaa"));
        VisibleControlSurface.CapturedWindow located = surface.Current;
        surface.Current = Capture(Mission, "aaaa", left: 140);
        VisibleControlSurface.SurfaceAfterWait moved =
            await VisibleControlSurface.SurfaceAfterWaitAsync(located, surface.CaptureAsync, CancellationToken.None);
        surface.Current = Capture(Mission, "aaaa", width: 640);
        VisibleControlSurface.SurfaceAfterWait resized =
            await VisibleControlSurface.SurfaceAfterWaitAsync(located, surface.CaptureAsync, CancellationToken.None);
        surface.Gone = true;
        VisibleControlSurface.SurfaceAfterWait gone =
            await VisibleControlSurface.SurfaceAfterWaitAsync(located, surface.CaptureAsync, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(moved.Moved, Is.True);
            Assert.That(resized.Moved, Is.True);
            Assert.That(gone.Same, Is.False);
            Assert.That(gone.Again, Is.Null);
        });
    }

    // Contracase: a window nobody touched while waited for is the same surface, and its point still holds.
    [Test]
    public async Task AnUntouchedWindowIsTheSameSurface()
    {
        var surface = new FakeSurface(Capture(Mission, "aaaa"));
        VisibleControlSurface.CapturedWindow located = surface.Current;
        surface.Current = Capture(Mission, "aaaa");

        VisibleControlSurface.SurfaceAfterWait recheck =
            await VisibleControlSurface.SurfaceAfterWaitAsync(located, surface.CaptureAsync, CancellationToken.None);

        Assert.That(recheck.Same, Is.True);
    }

    // The wheel on the window in front: the burst is taken first and the window captured inside it, so neither the
    // aim nor the baseline comes from before the wait.
    [Test]
    public async Task AWheelOnTheWindowInFrontCapturesItOnlyInsideTheBurst()
    {
        var order = new List<string>();
        var surface = new FakeSurface(Capture(Mission, "aaaa")) { Order = order };
        // The person scrolls while waited for, then touches the mouse again right after the pause: nothing turns.
        var lease = new WaitingLease(() => surface.Current = Capture(Mission, "bbbb"), personActsAfter: true)
        {
            Order = order,
        };
        var scroll = new WindowsScrollAdapter(
            lease: lease, foreground: _ => ValueTask.FromResult(Mission), capture: surface.CaptureAsync);

        ExternalCapabilityReceipt receipt = await scroll.InvokeAsync(
            "input.scroll", Json("""{"direction":"down"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(order, Is.EqualTo(new[] { "acquire", "capture" }));
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(lease.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
        });
    }

    // Contracases: no window in front takes no burst, and a capture of another window than the leased one is refused.
    [Test]
    public async Task NoWindowInFrontOrAnotherWindowCapturedGetsNoWheel()
    {
        var idle = new WaitingLease(() => { });
        ExternalCapabilityReceipt none = await new WindowsScrollAdapter(
                lease: idle,
                foreground: _ => ValueTask.FromResult<nint>(0),
                capture: (_, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
            .InvokeAsync("input.scroll", Json("""{"direction":"up"}"""), CancellationToken.None);

        var other = new WaitingLease(() => { });
        ExternalCapabilityReceipt elsewhere = await new WindowsScrollAdapter(
                lease: other,
                foreground: _ => ValueTask.FromResult(Mission),
                capture: (_, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(Capture(0x9999, "cccc")))
            .InvokeAsync("input.scroll", Json("""{"direction":"up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(none.ErrorCode, Is.EqualTo("active_window_not_found"));
            Assert.That(idle.Burst, Is.Null);
            Assert.That(elsewhere.ErrorCode, Is.EqualTo("active_window_not_found"));
            Assert.That(elsewhere.EffectMayHaveOccurred, Is.False);
            Assert.That(other.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
        });
    }

    // Safety review r10a: the window holding the front and the point lying in its rectangle do not say what the wheel
    // reaches. A window of another application kept always on top over the aim (a picture-in-picture) gets no wheel:
    // the point is asked for the window it shows, at the very aim, before anything turns.
    [Test]
    public async Task AWheelAimedAtAPointAnotherWindowCoversTurnsNothing()
    {
        var asked = new List<(nint Window, int X, int Y)>();
        var lease = new WaitingLease(() => { });
        var scroll = new WindowsScrollAdapter(
            lease: lease,
            foreground: _ => ValueTask.FromResult(Mission),
            capture: (_, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(Capture(Mission, "aaaa")),
            shows: (window, x, y) =>
            {
                asked.Add((window, x, y));
                return false;
            });

        ExternalCapabilityReceipt receipt = await scroll.InvokeAsync(
            "input.scroll", Json("""{"direction":"down"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(asked, Is.EqualTo(new[] { (Mission, 500, 380) }), "the window's centre, the wheel's aim");
            Assert.That(lease.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
        });
    }

    // Contracase: a point that shows the mission's window passes this check and goes on to the next one (the window in
    // front, which this fake handle never is: the wheel still turns nothing here, for that other reason).
    [Test]
    public async Task AWheelAimedAtAPointOfItsOwnWindowGoesOnToTheFrontCheck()
    {
        var scroll = new WindowsScrollAdapter(
            lease: new WaitingLease(() => { }),
            foreground: _ => ValueTask.FromResult(Mission),
            capture: (_, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(Capture(Mission, "aaaa")),
            shows: (window, _, _) => window == Mission);

        ExternalCapabilityReceipt receipt = await scroll.InvokeAsync(
            "input.scroll", Json("""{"direction":"down"}"""), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
    }

    // A window that comes over the aim between notches stops the wheel before the next one, and the receipt says it
    // was covered (never a whole scroll). Contracase: an aim that keeps showing the window turns every notch.
    [Test]
    public async Task AWheelCoveredBetweenNotchesStopsAndSaysSo()
    {
        var shown = new Queue<bool>([true, true, false, true]);
        int notches = 0;
        (int turned, bool covered) = await WindowsScrollAdapter.TurnWhileShownAsync(
            5, () => true, () => shown.Dequeue(), () => notches++, CancellationToken.None, pauseMs: 0);

        int clearNotches = 0;
        (int clearTurned, bool clearCovered) = await WindowsScrollAdapter.TurnWhileShownAsync(
            5, () => true, () => true, () => clearNotches++, CancellationToken.None, pauseMs: 0);

        Assert.Multiple(() =>
        {
            Assert.That((turned, covered), Is.EqualTo((2, true)));
            Assert.That(notches, Is.EqualTo(2), "nothing turned once the aim was covered");
            Assert.That((clearTurned, clearCovered), Is.EqualTo((5, false)));
            Assert.That(clearNotches, Is.EqualTo(5));
        });
    }

    private static VisibleControlSurface.CapturedWindow Capture(
        nint hwnd, string sha, int left = 100, int top = 80, int width = 800, int height = 600) =>
        new(hwnd, [], left, top, width, height, sha);

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private sealed class FakeSurface(VisibleControlSurface.CapturedWindow initial)
    {
        internal VisibleControlSurface.CapturedWindow Current { get; set; } = initial;

        internal bool Gone { get; set; }

        internal List<string>? Order { get; init; }

        internal ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(nint hwnd, CancellationToken token)
        {
            Order?.Add("capture");
            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(Gone ? null : Current);
        }
    }

    // A lease whose wait lets the person change the window before it grants the burst.
    private sealed class WaitingLease(Action personMeanwhile, bool personActsAfter = false) : IForegroundLease
    {
        internal FakeInputBurst? Burst { get; private set; }

        internal List<string>? Order { get; init; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            Order?.Add("acquire");
            personMeanwhile();
            Burst = new FakeInputBurst { WaitedMs = 1_200, UserActed = personActsAfter };
            return ValueTask.FromResult<IInputBurst>(Burst);
        }

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            AcquireAsync(0, cancellationToken);
    }
}
