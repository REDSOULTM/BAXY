using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// PLAN_GENERAL A3 (uso real 2026-10-20: Steam's store refused four clicks while its page still moved): a changed surface
// is captured again until two captures in a row are the same.
public sealed class StableSurfaceTests
{
    private static VisibleControlSurface.CapturedWindow Frame(string drawing, int left = 0) =>
        new(7, [], left, 0, 800, 600, drawing);

    private static async Task<(string? Drawing, int Captures)> Settle(
        VisibleControlSurface.CapturedWindow latest, params VisibleControlSurface.CapturedWindow?[] next)
    {
        var queue = new Queue<VisibleControlSurface.CapturedWindow?>(next);
        int captures = 0;
        VisibleControlSurface.CapturedWindow? still = await VisibleControlSurface.StableSurfaceAsync(
            latest,
            (_, _) =>
            {
                captures++;
                return ValueTask.FromResult(queue.Count > 0 ? queue.Dequeue() : null);
            },
            (_, _) => Task.CompletedTask,
            CancellationToken.None);
        return (still?.Sha256, captures);
    }

    [Test]
    public async Task ASurfaceThatStopsMovingIsTakenOnItsFirstStillCapture()
    {
        var settled = await Settle(Frame("a"), Frame("b"), Frame("c"), Frame("c"), Frame("d"));
        Assert.That(settled, Is.EqualTo(("c", 3)));
    }

    [Test]
    public async Task AWindowThatMovedSettlesWhereItStops()
    {
        var settled = await Settle(Frame("a", left: 10), Frame("a", left: 40), Frame("a", left: 40));
        Assert.That(settled, Is.EqualTo(("a", 2)));
    }

    [Test]
    public async Task ASurfaceThatNeverStopsIsNotTakenAndTheWaitIsBounded()
    {
        var frames = Enumerable.Range(0, 20).Select(i => (VisibleControlSurface.CapturedWindow?)Frame("f" + i)).ToArray();
        var settled = await Settle(Frame("start"), frames);
        Assert.That(settled, Is.EqualTo(((string?)null, VisibleControlSurface.StableSurfaceReads)));
    }

    [Test]
    public async Task AWindowThatCannotBeReadIsNotTaken()
    {
        var settled = await Settle(Frame("a"), [null]);
        Assert.That(settled, Is.EqualTo(((string?)null, 1)));
    }
}
