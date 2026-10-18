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

    [TestCase("{}")]
    [TestCase("{\"appId\":3}")]
    [TestCase("{\"appId\":\"   \"}")]
    public async Task ArgumentsWithoutAnApplicationAreRefused(string json)
    {
        var windows = new FakeWindows([Frame("win_a", 100)]);
        var handler = new AppRestartHandler(windows, Opens([], 200), (_, _, _) => ValueTask.FromResult(true));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(windows.Closed, Is.Empty);
        });
    }

    private sealed class FakeWindows(WindowCandidate[] windows) : IWindowControlProvider
    {
        internal List<string> Closed { get; } = [];

        internal string? Prompts { get; init; }

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
