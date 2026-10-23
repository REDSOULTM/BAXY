using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// app.restart (auditoría de los pedidos reales, 2026-10-17) against fake windows, a fake opening and fake process
/// exits: no real application is closed or opened. Its windows close gracefully, its processes must end on their own,
/// and only a new process opened by app.open counts as the restart.
/// </summary>
[TestFixture]
public sealed class AppRestartHandlerTests
{
    private static OperationInvocation Invocation(string json = "{\"appId\":\"Spotify\"}") =>
        new("r", "m", "i", JsonDocument.Parse(json).RootElement);

    private static WindowCandidate Frame(string id, int process, bool owned = false) =>
        new(id, process, "Spotify", "normal", false, 0, 0, 800, 600, "Spotify", owned);

    private static Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> Opens(
        List<OperationInvocation> calls, int processId, bool alreadyRunning = false) =>
        (invocation, _) =>
        {
            calls.Add(invocation);
            return ValueTask.FromResult(OperationOutcome.Success(JsonSerializer.SerializeToElement(
                new { appId = "Spotify", alreadyRunning, processId, windowHandle = 4242L })));
        };

    [Test]
    public async Task ClosesEveryFrameWaitsForTheProcessAndCountsOnlyANewProcess()
    {
        var windows = new FakeWindows([Frame("win_a", 100), Frame("win_b", 100), Frame("win_dialog", 100, owned: true)]);
        var opens = new List<OperationInvocation>();
        var waited = new List<int>();
        var handler = new AppRestartHandler(windows, Opens(opens, 200), (pid, _, _) =>
        {
            waited.Add(pid);
            return ValueTask.FromResult(true);
        });

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            Assert.That(windows.Closed, Is.EqualTo(new[] { "win_a", "win_b" }), "the owned dialog goes with its frame");
            Assert.That(waited, Is.EqualTo(new[] { 100 }));
            Assert.That(opens, Has.Count.EqualTo(1));
            Assert.That(opens[0].Arguments.GetProperty("appId").GetString(), Is.EqualTo("Spotify"));
            Assert.That(opens[0].Arguments.GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("closedWindows").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result!.Value.GetProperty("reopened").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("opened").GetProperty("processId").GetInt32(), Is.EqualTo(200));
        });
    }

    // FT/proveedores goal (review of receipts): a packaged application's frame belongs to the shared ApplicationFrameHost
    // (here 300), which never ends with it: it is not waited for, and the reopening app.open verifies is the restart.
    [Test]
    public async Task APackagedApplicationsSharedHostIsNotWaitedFor()
    {
        var windows = new FakeWindows([Frame("win_calc", 300)]);
        var opens = new List<OperationInvocation>();
        var waited = new List<int>();
        var handler = new AppRestartHandler(windows, Opens(opens, 300), (pid, _, _) =>
        {
            waited.Add(pid);
            return ValueTask.FromResult(false);
        }, sharedHost: pid => pid == 300);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True, outcome.ErrorCode);
            Assert.That(waited, Is.Empty, "the shared host is not waited for");
            Assert.That(opens, Has.Count.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("reopened").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AWindowThatAsksToSaveStopsEverythingAndNothingIsReopened()
    {
        var windows = new FakeWindows([Frame("win_a", 100), Frame("win_b", 100)]) { Prompts = "win_b" };
        var opens = new List<OperationInvocation>();
        var handler = new AppRestartHandler(windows, Opens(opens, 200), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True, "one window had already closed");
            Assert.That(opens, Is.Empty);
        });
    }

    [Test]
    public async Task AnApplicationThatKeepsRunningHiddenIsSaidAndNeitherKilledNorReopened()
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var opens = new List<OperationInvocation>();
        var handler = new AppRestartHandler(windows, Opens(opens, 200), (_, _, _) => ValueTask.FromResult(false));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_kept_running"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("stillRunningProcessIds")[0].GetInt32(), Is.EqualTo(100));
            Assert.That(opens, Is.Empty);
        });
    }

    [TestCase(true, 300)]
    [TestCase(false, 100)]
    public async Task AnOpeningThatFoundAProcessAlreadyThereIsNotARestart(bool alreadyRunning, int processId)
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var handler = new AppRestartHandler(
            windows, Opens([], processId, alreadyRunning), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.That(outcome.ErrorCode, Is.EqualTo("app_restart_not_verified"));
    }

    // Auditoría del Core (w8): a reopening that failed said only its code; what it observed (a launch issued and no window
    // verified yet) goes with the restart's failure as reopening, never as an opening.
    [Test]
    public async Task AFailedReopeningKeepsWhatTheOpeningObserved()
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var handler = new AppRestartHandler(
            windows,
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure(
                "verification_failed",
                JsonSerializer.SerializeToElement(new { launchIssued = true, next = "a launch of Spotify was issued" }),
                effectMayHaveOccurred: true)),
            (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        JsonElement receipt = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.CauseCode, Is.EqualTo("app_reopen_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.GetProperty("closedWindows").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.GetProperty("reopened").GetBoolean(), Is.False);
            Assert.That(receipt.TryGetProperty("opened", out _), Is.False);
            Assert.That(receipt.GetProperty("reopening").GetProperty("launchIssued").GetBoolean(), Is.True);
        });
    }

    // Contracase: a reopening that failed with nothing observed adds nothing.
    [Test]
    public async Task AFailedReopeningWithNoFactsAddsNone()
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var handler = new AppRestartHandler(
            windows,
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure("launch_failed")),
            (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("launch_failed"));
            Assert.That(outcome.Result!.Value.TryGetProperty("reopening", out _), Is.False);
        });
    }

    // Auditoría del Core (w8): every closed process waited ExitWait of its own; three that kept running waited 30 s. One
    // deadline for all: the first takes the whole wait, the others what is left of it (none here).
    [Test]
    public async Task EveryClosedProcessIsWaitedForWithinOneSharedDeadline()
    {
        var windows = new FakeWindows([Frame("win_a", 100), Frame("win_b", 101), Frame("win_c", 102)]);
        var clock = new SteppedClock();
        var waits = new List<TimeSpan>();
        var handler = new AppRestartHandler(windows, Opens([], 200), (_, wait, _) =>
        {
            waits.Add(wait);
            clock.Advance(wait);
            return ValueTask.FromResult(false);
        }, time: clock);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_kept_running"));
            Assert.That(waits, Is.EqualTo(new[] { AppRestartHandler.ExitWait, TimeSpan.Zero, TimeSpan.Zero }));
            Assert.That(outcome.Result!.Value.GetProperty("stillRunningProcessIds").GetArrayLength(), Is.EqualTo(3));
        });
    }

    // Auditoría del Core (w8): an application with no window and its processes running in the background failed bare;
    // app.close names those processes, and so does the restart now. Nothing was closed nor reopened.
    [Test]
    public async Task AnApplicationRunningOnlyInTheBackgroundSaysItsProcesses()
    {
        var windows = new FakeWindows([]) { Background = [700, 701] };
        var opens = new List<OperationInvocation>();
        var handler = new AppRestartHandler(windows, Opens(opens, 200), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        JsonElement receipt = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(ApplicationWindowCloser.AppRunningInBackground));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.GetProperty("processIds").EnumerateArray().Select(id => id.GetInt32()),
                Is.EqualTo(new[] { 700, 701 }));
            Assert.That(receipt.GetProperty("windows").GetInt32(), Is.Zero);
            Assert.That(receipt.GetProperty("closedWindows").GetInt32(), Is.Zero);
            Assert.That(receipt.GetProperty("reopened").GetBoolean(), Is.False);
            Assert.That(windows.Closed, Is.Empty);
            Assert.That(opens, Is.Empty);
        });
    }

    private sealed class SteppedClock : TimeProvider
    {
        private long _ticks;

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _ticks;

        internal void Advance(TimeSpan by) => _ticks += by.Ticks;
    }

    [Test]
    public async Task AnApplicationWithNoWindowIsNotRunningAndNothingHappens()
    {
        var windows = new FakeWindows([Frame("win_dialog", 100, owned: true)]);
        var opens = new List<OperationInvocation>();
        var handler = new AppRestartHandler(windows, Opens(opens, 200), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_running"));
            Assert.That(windows.Closed, Is.Empty);
            Assert.That(opens, Is.Empty);
        });
    }

    // P5.3: the refusal names appId and what is wrong with it: the schema's problem, or a path or a command line
    // where the application's name goes.
    [TestCase("{}", "required and missing")]
    [TestCase("{\"appId\":3}", "expected text")]
    [TestCase("{\"appId\":\"   \"}", "expected text")]
    [TestCase("{\"appId\":\"C:/Windows/notepad.exe\"}", "expected an application's name, not a path or a command")]
    public async Task ArgumentsWithoutAnApplicationAreRefused(string json, string problem)
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var handler = new AppRestartHandler(windows, Opens([], 200), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(outcome.ArgumentProblems.Single().Name, Is.EqualTo("appId"));
            Assert.That(outcome.ArgumentProblems.Single().Problem, Does.StartWith(problem));
            Assert.That(windows.Closed, Is.Empty);
        });
    }

    private sealed class FakeWindows(WindowCandidate[] windows) : IWindowControlProvider
    {
        internal List<string> Closed { get; } = [];

        internal string? Prompts { get; init; }

        internal IReadOnlyList<int> Background { get; init; } = [];

        public ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(
            string applicationName, CancellationToken cancellationToken) =>
            ValueTask.FromResult(Background);

        public ValueTask<WindowResolveResult> ResolveApplicationAsync(
            string applicationName, int limit, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new WindowResolveResult(true, true, windows, null));

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken)
        {
            WindowCandidate window = windows.Single(candidate => candidate.WindowId == windowId);
            if (windowId == Prompts)
                return ValueTask.FromResult(new WindowCloseResult(true, true, window.ProcessId, null, ClosePrompted: true));
            Closed.Add(windowId);
            return ValueTask.FromResult(new WindowCloseResult(true, true, window.ProcessId, null, Title: window.Title));
        }

        public ValueTask<WindowResolveResult> ResolveForegroundAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveAsync(
            string processName, int limit, CancellationToken cancellationToken, bool byTitle = false, int offset = 0) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId, WindowControlAction action, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }
}
