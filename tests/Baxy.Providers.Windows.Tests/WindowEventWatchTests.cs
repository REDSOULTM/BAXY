using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Renew al máximo (w6-settle): the window events a cold start's settle waits on. The hooks are Windows' own (out of
// context: nothing is loaded into any application); the family watched is a process that does not run, so no event of
// it ever comes and only the watch's own thread, quiet and removal are seen.
public sealed class WindowEventWatchTests
{
    // No process runs with this id (process ids are multiples of four).
    private const int NoProcess = 0x7FFF_FFFD;

    [Test]
    public void TheWatchHooksOnItsOwnThreadAndRemovesItsHooksThereWhenDisposed()
    {
        WindowEventWatch? watch = WindowEventWatch.Start([NoProcess]);
        Assert.That(watch, Is.Not.Null, "Windows took the hooks");
        Assert.That(watch!.Running, Is.True);

        watch.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(watch.Unhooked, Is.EqualTo(1), "both hooks removed by the thread that holds them");
            Assert.That(watch.Running, Is.False);
        });
        watch.Dispose();
    }

    [Test]
    public async Task AFamilyWithNoEventIsQuietOnceTheQuietSpanPassed()
    {
        using WindowEventWatch watch = WindowEventWatch.Start([NoProcess])!;

        (bool quiet, TimeSpan waited) = await watch.QuietAsync(
            TimeSpan.FromMilliseconds(60), TimeSpan.FromSeconds(2), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(quiet, Is.True);
            Assert.That(waited, Is.GreaterThanOrEqualTo(TimeSpan.FromMilliseconds(50)), "the quiet counts from the wait");
            Assert.That(waited, Is.LessThan(TimeSpan.FromSeconds(2)));
        });
    }

    // A quiet longer than the wait's limit is never reached within it: the wait returns at once, not quiet.
    [Test]
    public async Task AQuietBeyondTheLimitReturnsAtOnceNotQuiet()
    {
        using WindowEventWatch watch = WindowEventWatch.Start([NoProcess])!;

        (bool quiet, TimeSpan waited) = await watch.QuietAsync(
            TimeSpan.FromSeconds(1), TimeSpan.FromMilliseconds(400), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(quiet, Is.False);
            Assert.That(waited, Is.LessThan(TimeSpan.FromMilliseconds(400)));
        });
    }

    // A wait cancelled while it sleeps ends with the cancellation; disposing the watch then still removes the hooks.
    [Test]
    public void ACancelledWaitEndsAndTheHooksAreStillRemoved()
    {
        WindowEventWatch watch = WindowEventWatch.Start([NoProcess])!;
        using var cancel = new CancellationTokenSource(TimeSpan.FromMilliseconds(50));

        Assert.CatchAsync<OperationCanceledException>(async () =>
            await watch.QuietAsync(TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(10), cancel.Token));
        watch.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(watch.Unhooked, Is.EqualTo(1));
            Assert.That(watch.Running, Is.False);
        });
    }

    // The wait's arithmetic: quiet once the last event is «quiet» old; else it sleeps until it could be; an event so
    // recent that the quiet cannot come within the limit (a flood) ends the wait, not quiet.
    [TestCase(0, 300, true, 0)]
    [TestCase(100, 50, false, 200)]
    [TestCase(300, 50, false, 0)]
    [TestCase(390, 0, false, 0)]
    public void TheWaitStepsTowardTheQuietWithinItsLimit(int waitedMs, int sinceLastMs, bool quiet, int sleepMs)
    {
        (bool reached, TimeSpan sleep) = WindowEventWatch.Step(
            TimeSpan.FromMilliseconds(waitedMs),
            TimeSpan.FromMilliseconds(sinceLastMs),
            TimeSpan.FromMilliseconds(250),
            TimeSpan.FromMilliseconds(400));

        Assert.Multiple(() =>
        {
            Assert.That(reached, Is.EqualTo(quiet));
            Assert.That(sleep, Is.EqualTo(TimeSpan.FromMilliseconds(sleepMs)));
        });
    }
}
