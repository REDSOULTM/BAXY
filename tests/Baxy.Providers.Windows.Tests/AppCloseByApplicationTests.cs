using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// app.close with appId (auditoría de los pedidos reales, 2026-10-17): exactly one of windowId and appId; with appId
/// the application's windows are resolved and closed here, each as app.close closes one (fake windows: nothing real is
/// closed).
/// </summary>
[TestFixture]
public sealed class AppCloseByApplicationTests
{
    private static OperationInvocation Invocation(string json) => new("r", "m", "i", JsonDocument.Parse(json).RootElement);

    private static WindowCandidate Frame(string id, int process, string title, bool owned = false) =>
        new(id, process, "mspaint", "normal", false, 0, 0, 800, 600, title, owned);

    [Test]
    public async Task ByNameEveryFrameClosesAndTheReceiptNamesWhatClosed()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Sin título - Paint"), Frame("win_b", 101, "dibujo - Paint"),
            Frame("win_dialog", 100, "Guardar como", owned: true)]);

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Paint\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            Assert.That(windows.Closed, Is.EqualTo(new[] { "win_a", "win_b" }));
            Assert.That(outcome.Result!.Value.GetProperty("closedWindows").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result!.Value.GetProperty("processIds").GetArrayLength(), Is.EqualTo(2));
            Assert.That(outcome.Result!.Value.GetProperty("titles")[1].GetString(), Is.EqualTo("dibujo - Paint"));
        });
    }

    [TestCase("{}")]
    [TestCase("{\"appId\":\"Paint\",\"windowId\":\"win_a\"}")]
    public async Task ExactlyOneOfWindowIdAndAppIdIsAsked(string json)
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Paint")]);

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(windows.Closed, Is.Empty);
        });
    }

    [Test]
    public async Task AnApplicationWithNoWindowIsNotRunningAndNothingCloses()
    {
        var windows = new FakeWindows([]);

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Paint\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_running"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
        });
    }

    // Renew al máximo (auditoría de flujos): «cierra Steam» with Steam only in the notification area, or with its window
    // hidden by the close, said the application was not running (or closed): it runs, with no window, and is said so.
    [Test]
    public async Task AnApplicationRunningWithNoWindowIsSaidRunningInTheBackground()
    {
        var windows = new FakeWindows([]) { Background = [4242] };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Steam\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_running_in_background"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("processIds")[0].GetInt32(), Is.EqualTo(4242));
            Assert.That(windows.Closed, Is.Empty);
        });
    }

    [Test]
    public async Task AWindowThatOnlyHidesLeavesTheApplicationRunningInTheBackground()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Steam")]) { Hides = "win_a" };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Steam\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False, "a hidden window is no closed application");
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_running_in_background"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True, "its window was hidden");
            Assert.That(outcome.Result!.Value.GetProperty("hiddenWindows").GetInt32(), Is.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("processIds")[0].GetInt32(), Is.EqualTo(100));
        });
    }

    [Test]
    public async Task AWindowThatAsksToSaveStopsAndIsSaid()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Paint"), Frame("win_b", 100, "Paint")]) { Prompts = "win_a" };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Paint\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(outcome.Result!.Value.GetProperty("closePrompted").GetBoolean(), Is.True);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False, "no window had closed yet");
            Assert.That(windows.Closed, Is.Empty);
        });
    }

    // FT/proveedores goal (review of receipts): nine of ten windows minimized and one refused: the failure carries what
    // was done (the counts), its effect is possible, and it is never a success.
    [Test]
    public async Task APartialMinimizeAllCarriesItsCountsWithTheFailure()
    {
        var windows = new FakeWindows([])
        {
            MinimizeAll = new WindowMinimizeAllResult(false, false, 10, 9, 1, "window_minimize_all_incomplete",
                EffectMayHaveOccurred: true),
        };

        OperationOutcome outcome = await new WindowMinimizeAllHandler(windows).ExecuteAsync(
            Invocation("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("window_minimize_all_incomplete"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("minimized").GetInt32(), Is.EqualTo(9));
            Assert.That(outcome.Result!.Value.GetProperty("remainingVisible").GetInt32(), Is.EqualTo(1));
        });
    }

    private sealed class FakeWindows(WindowCandidate[] windows) : IWindowControlProvider
    {
        internal WindowMinimizeAllResult? MinimizeAll { get; init; }

        public ValueTask<WindowMinimizeAllResult> MinimizeAllAsync(CancellationToken cancellationToken) =>
            ValueTask.FromResult(MinimizeAll ?? throw new AssertionException("not used"));

        internal List<string> Closed { get; } = [];

        internal string? Prompts { get; init; }

        internal string? Hides { get; init; }

        internal int[] Background { get; init; } = [];

        public ValueTask<WindowResolveResult> ResolveApplicationAsync(
            string applicationName, int limit, CancellationToken cancellationToken) =>
            ValueTask.FromResult(windows.Length == 0
                ? new WindowResolveResult(false, false, [], WindowControlErrorCodes.WindowNotFound)
                : new WindowResolveResult(true, true, windows, null));

        public ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(
            string applicationName, CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<int>>(Background);

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken)
        {
            WindowCandidate window = windows.Single(candidate => candidate.WindowId == windowId);
            if (windowId == Prompts)
                return ValueTask.FromResult(new WindowCloseResult(true, true, window.ProcessId, null, ClosePrompted: true));
            if (windowId == Hides)
                return ValueTask.FromResult(new WindowCloseResult(
                    true, true, window.ProcessId, null, Outcome: WindowCloseOutcomes.Hidden));
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
