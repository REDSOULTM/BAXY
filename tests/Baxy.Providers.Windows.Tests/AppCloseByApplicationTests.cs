using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
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
            Assert.That(outcome.ArgumentProblems.Single().OneOf, Is.EqualTo(new[] { "appId", "windowId" }));
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

    // Al máximo, flujos: an application asked for by its name with no window to close is that failure before any yes;
    // one with its windows leaves the close to ask (and to resolve them again).
    [Test]
    public async Task AnApplicationNotRunningFailsBeforeTheYesAndOneRunningIsAsked()
    {
        var none = new AppCloseHandler(new FakeWindows([]));
        var running = new FakeWindows([Frame("win_a", 100, "Sin título - Paint")]);

        InvocationPreflightResult missing = await none.PreflightAsync(
            JsonDocument.Parse("{\"appId\":\"Paint\"}").RootElement, CancellationToken.None);
        InvocationPreflightResult there = await new AppCloseHandler(running).PreflightAsync(
            JsonDocument.Parse("{\"appId\":\"Paint\"}").RootElement, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.Failure?.ErrorCode, Is.EqualTo("app_not_running"));
            Assert.That(missing.Failure?.EffectMayHaveOccurred, Is.False);
            Assert.That(there.Failure, Is.Null);
            Assert.That(there.Risk, Is.Null, "a window holding a document keeps work_loss");
            Assert.That(running.Closed, Is.Empty);
        });
    }

    // Al máximo, flujos («cierra discord» asked every time): app.close by the application's name lowers its risk as a
    // close by a window does when every window it has holds no document of the person (the provider's rule, with the
    // microphone's); one window with a document, or one it cannot place, keeps the yes. Fake windows: nothing closes
    // for real.
    [TestCase(new[] { "win_discord", "win_discord_2" }, false)]
    [TestCase(new[] { "win_notepad" }, true)]
    public async Task ByNameAnApplicationAllOfWhoseWindowsHoldNoDocumentClosesWithoutAsking(string[] ids, bool asks)
    {
        var windows = new FakeWindows([.. ids.Select((id, index) => Frame(id, 100 + index, id))])
        {
            Documentless = ["win_discord", "win_discord_2"],
        };
        string root = Path.Combine(Path.GetTempPath(), "baxy-app-close-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([new AppCloseHandler(windows)]), journal);

            OperationResponse response = await engine.ExecuteAsync(
                new OperationRequest(
                    ProtocolTypes.OperationRequest, Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
                    Guid.NewGuid().ToString("D"), "app.close", JsonDocument.Parse("{\"appId\":\"Discord\"}").RootElement),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(response.ErrorCode, asks ? Is.EqualTo("confirmation_required") : Is.Null);
                Assert.That(windows.Closed, asks ? Is.Empty : Is.EqualTo(ids));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
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

        internal string[] Documentless { get; init; } = [];

        public bool HoldsNoDocument(string windowId) => Documentless.Contains(windowId);

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
