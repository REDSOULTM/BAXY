using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The heartbeat's probes of the PC: nvidia-smi's output is read within its 2 s limit (ReadToEnd before
/// WaitForExit(2000) waited as long as the program kept its pipe open), and every per-program microphone key under
/// NonPackaged is disposed, also the ones after the one that answers.
/// </summary>
[TestFixture]
public sealed class HeartbeatProbeTests
{
    [Test]
    public void AReadThatNeverEndsGivesNothingWithinTheLimit()
    {
        var neverEnds = new TaskCompletionSource<string>();
        var clock = System.Diagnostics.Stopwatch.StartNew();

        string? output = HeartbeatMoment.ReadWithin(neverEnds.Task, TimeSpan.FromMilliseconds(100));

        Assert.That(output, Is.Null);
        Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(5)));
    }

    [Test]
    public void AReadThatEndsGivesItsOutputAndAFailedOneNothing()
    {
        Assert.That(HeartbeatMoment.ReadWithin(Task.FromResult("37\n"), TimeSpan.FromSeconds(1)), Is.EqualTo("37\n"));
        Assert.That(HeartbeatMoment.ReadWithin(Task.FromException<string>(new InvalidOperationException()),
            TimeSpan.FromSeconds(1)), Is.Null);
    }

    [Test]
    public void EveryChildKeyOpenedIsDisposedWhetherOrNotItHoldsTheMicrophone()
    {
        var opened = new List<FakeKey>();
        string[] names = ["a", "missing", "held", "after"];

        bool held = HeartbeatMoment.AnyChildHeld(
            names,
            name =>
            {
                if (name == "missing")
                {
                    return null;
                }

                var key = new FakeKey(name);
                opened.Add(key);
                return key;
            },
            static (name, _) => name == "held");

        Assert.That(held, Is.True);
        Assert.That(opened.Select(static key => key.Name), Is.EqualTo(new[] { "a", "held" }));
        Assert.That(opened.All(static key => key.Disposed), Is.True);
    }

    [Test]
    public void AKeyWhoseCheckFailsIsDisposedToo()
    {
        var key = new FakeKey("broken");

        Assert.Throws<System.Security.SecurityException>(() => HeartbeatMoment.AnyChildHeld(
            ["broken"], _ => key, static (_, _) => throw new System.Security.SecurityException()));
        Assert.That(key.Disposed, Is.True);
    }

    private sealed class FakeKey(string name) : IDisposable
    {
        internal string Name { get; } = name;

        internal bool Disposed { get; private set; }

        public void Dispose() => Disposed = true;
    }
}
