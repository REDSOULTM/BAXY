using System.Globalization;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Estab G4 (tandas f2nb t2-c01 t1, t4-c01 t3: «media.play.query» failed in stage «started» with
/// <c>spotify_foreground_not_verified</c>, and the final said «no pude confirmar si se hizo»): a script stopped before
/// its search is run once more, after the host brought the client's window up the way a mission's act takes it (the
/// helper's burst, <see cref="IInputBurst.BringUpAsync"/>; its rules in ForegroundSequenceTests); it is the same one
/// retry an exact selection's discovery has. A call whose scripts all stopped before searching pressed nothing: its
/// failure says no effect, never an uncertain one.
/// </summary>
[TestFixture]
public sealed class SpotifyFrontRetryTests
{
    private const nint Client = 0x5150;

    private const string BeforeSearch =
        "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_uia_failed\",\"stage\":\"started\",\"detail\":\"spotify_foreground_not_verified\"}";

    private const string Played =
        "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"Los Bunkers - Llueve sobre la ciudad\",\"selectedControl\":\"Reproducir Los Bunkers\",\"presses\":1,\"processId\":42}";

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    [TestCase("media.play.query", """{"provider":"spotify","query":"los bunkers"}""")]
    [TestCase("media.play.exact", """{"provider":"spotify","title":"Llueve sobre la ciudad"}""")]
    public async Task AScriptStoppedBeforeItsSearchIsRunOnceMoreWithTheClientBroughtUp(string operation, string arguments)
    {
        var runner = new Runner(BeforeSearch, Played);
        var lease = new BringingLease(runner);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = lease };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(runner.Calls, Is.EqualTo(2));
            Assert.That(lease.Burst.BroughtUp, Is.EqualTo(new[] { (Client, 1) }), "brought up once, between the runs");
            Assert.That(lease.Burst.Restores, Is.EqualTo(1), "the burst gives the person their front back at the end");
        });
    }

    // Both runs stopped before searching: nothing was pressed, so nothing can have played; the stage and the detail
    // still travel for the log.
    [Test]
    public async Task ACallThatNeverSearchedFailsWithNoEffectNeverAnUncertainOne()
    {
        var runner = new Runner(BeforeSearch, BeforeSearch);
        var lease = new BringingLease(runner);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = lease };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"cumbia"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_uia_failed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("stage").GetString(), Is.EqualTo("started"));
            Assert.That(receipt.Result?.GetProperty("detail").GetString(), Is.EqualTo("spotify_foreground_not_verified"));
            Assert.That(runner.Calls, Is.EqualTo(2), "one retry, never a second");
        });
    }

    // Contracases: a query stopped after its search is never run again (a second search could press twice) and stays
    // uncertain; an exact selection that searched and then stopped before searching again is not «no effect» either.
    [Test]
    public async Task AQueryStoppedAfterItsSearchIsNeverRetriedAndStaysUncertain()
    {
        var runner = new Runner(
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_uia_failed\",\"stage\":\"searched\",\"detail\":\"spotify_element_not_actionable\"}",
            Played);
        var lease = new BringingLease(runner);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = lease };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"cumbia"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(lease.Burst.BroughtUp, Is.Empty);
        });
    }

    [Test]
    public async Task AnExactSelectionThatSearchedOnceIsNotTakenForOneThatNeverDid()
    {
        var runner = new Runner(
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\"}", BeforeSearch);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = new BringingLease(runner) };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Llueve sobre la ciudad"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_uia_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(2));
        });
    }

    // SP2 (tandas n3 del notebook: three searches killed at the 65 s budget with nothing said): every run, the retry's
    // included, is given a deadline the margin short of its own budget, so the script answers before it is killed.
    [Test]
    public async Task EveryRunIsGivenADeadlineTheMarginShortOfItsBudget()
    {
        var runner = new Runner(BeforeSearch, Played);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = new BringingLease(runner) };

        _ = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"cumbia"}"""), CancellationToken.None);

        Assert.That(runner.Runs, Has.Count.EqualTo(2));
        foreach ((IReadOnlyList<string> arguments, TimeSpan budget) in runner.Runs)
        {
            int at = arguments.ToList().IndexOf("-DeadlineMs");
            Assert.That(at, Is.GreaterThan(0), "the deadline is passed");
            Assert.That(
                long.Parse(arguments[at + 1], CultureInfo.InvariantCulture),
                Is.EqualTo((long)(budget - SpotifyDesktopAdapter.DeadlineMargin).TotalMilliseconds));
        }
    }

    // A run the deadline stopped after its search says where it was and the time of each stage; it stays uncertain.
    // SP3 (tandas n10 del notebook, t1-c07 and t2-c01: «spotify_exact_result_not_found» after 24 s with an empty
    // receipt): a search that picked nothing says the same, with what its last look of the page showed.
    [TestCase(
        "{\"ok\":false,\"effectObserved\":true,\"error\":\"spotify_uia_failed\",\"stage\":\"play_clicked\",\"detail\":\"spotify_deadline_reached\",\"timings\":\"started=10512;searched=14800;play_clicked=59990;\"}",
        "play_clicked",
        "spotify_deadline_reached",
        "started=10512;searched=14800;play_clicked=59990;")]
    [TestCase(
        "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\",\"stage\":\"searched\",\"detail\":\"spotify_exact_result_not_found;searches=2;cold=0;rows=640;before=610;plays=12;fresh=0;shown=0;box=1;iconic=0\",\"timings\":\"started=1212;researched=9330;searched=21354;\"}",
        "searched",
        "spotify_exact_result_not_found;searches=2;cold=0;rows=640;before=610;plays=12;fresh=0;shown=0;box=1;iconic=0",
        "started=1212;researched=9330;searched=21354;")]
    public async Task ARunStoppedAfterItsSearchCarriesItsStageDetailAndTimings(
        string output, string stage, string detail, string timings)
    {
        var runner = new Runner(output);
        var adapter = new SpotifyDesktopAdapter(runner, clientWindow: () => Client) { InputLease = new BringingLease(runner) };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"cumbia"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(1), "a run stopped after its search is never run again");
            Assert.That(receipt.Result?.GetProperty("stage").GetString(), Is.EqualTo(stage));
            Assert.That(receipt.Result?.GetProperty("detail").GetString(), Is.EqualTo(detail));
            Assert.That(receipt.Result?.GetProperty("timings").GetString(), Is.EqualTo(timings));
        });
    }

    private sealed class Runner(params string[] outputs) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        internal List<(IReadOnlyList<string> Arguments, TimeSpan Budget)> Runs { get; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            string output = outputs[Math.Min(Calls, outputs.Length - 1)];
            Runs.Add(([.. arguments], timeout));
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class BringingLease(Runner runner) : IForegroundLease
    {
        internal BringingBurst Burst { get; } = new(runner);

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            throw new AssertionException("a helper's call acquires no burst on a known window");

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult<IInputBurst>(Burst);
    }

    // A helper's burst that records each window brought up and how many runs had been made by then.
    private sealed class BringingBurst(Runner runner) : IInputBurst
    {
        internal List<(nint Window, int RunsBefore)> BroughtUp { get; } = [];

        internal int Restores { get; private set; }

        public string? Refusal => null;

        public long WaitedMs => 0;

        public bool UserActed => false;

        public ValueTask<bool> BringUpAsync(nint window, CancellationToken cancellationToken)
        {
            BroughtUp.Add((window, runner.Calls));
            return ValueTask.FromResult(true);
        }

        public bool Restore()
        {
            Restores++;
            return true;
        }
    }
}
