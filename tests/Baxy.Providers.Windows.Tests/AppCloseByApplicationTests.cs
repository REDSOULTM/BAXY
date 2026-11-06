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

    // Renew al máximo (auditoría de flujos): «cierra Steam» with Steam only in the notification area, or with its window
    // hidden by the close, said the application was not running (or closed): it runs, with no window, and is said so.
    [Test]
    public async Task AnApplicationRunningWithNoWindowIsSaidRunningInTheBackground()
    {
        var windows = new FakeWindows([]) { Background = [4242] };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Steam\"}"), CancellationToken.None);
        // Said before the person is asked to confirm a close (IInvocationPreflight), with the same processes.
        InvocationPreflightResult before = await new AppCloseHandler(windows).PreflightAsync(
            JsonDocument.Parse("{\"appId\":\"Steam\"}").RootElement, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_running_in_background"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("processIds")[0].GetInt32(), Is.EqualTo(4242));
            Assert.That(windows.Closed, Is.Empty);
            Assert.That(before.Failure, Is.Null, "uso-129: it is asked to quit; nothing is said before trying");
            Assert.That(before.Risk, Is.EqualTo(OperationRisk.Reversible), "with no window it shows no document");
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

    // uso-129: «cierra X» with X in the notification area answered «quedó abierto en segundo plano» and stopped; it is
    // asked to quit as Windows asks at the end of a session, and the receipt says what came of it.
    [Test]
    public async Task AnApplicationInTheBackgroundIsAskedToQuitAndTheReceiptSaysItExited()
    {
        var windows = new FakeWindows([]) { Background = [4242], Quit = new(true, null, []) };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Bandeja\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            Assert.That(windows.AskedToQuit, Is.EqualTo(new[] { 4242 }));
            Assert.That(outcome.Result!.Value.GetProperty("applicationExited").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("changed", out _), Is.False, "it did change");
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    [Test]
    public async Task AWindowThatHidesIsFollowedByTheQuitAndHelpersLeftBehindAreSaid()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Bandeja")])
        {
            Hides = "win_a",
            Background = [100],
            Quit = new(true, null, [new RemainingProcess(101, "ayudante")]),
        };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Bandeja\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, "its main process ended");
            Assert.That(windows.AskedToQuit, Is.EqualTo(new[] { 100 }));
            Assert.That(outcome.Result!.Value.GetProperty("stillRunning")[0].GetProperty("name").GetString(), Is.EqualTo("ayudante"));
        });
    }

    [Test]
    public async Task AnApplicationThatStaysAfterBeingAskedSaysItsMainProcessAndTheCallThatForcesIt()
    {
        var windows = new FakeWindows([]) { Background = [4242], Quit = new(true, "bandeja", [new RemainingProcess(4242, "bandeja")]) };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Bandeja\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_running_in_background"));
            Assert.That(outcome.Result!.Value.GetProperty("applicationExited").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("mainStillRunning").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("mainProcessName").GetString(), Is.EqualTo("bandeja"));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(),
                Does.StartWith("system_process_terminate_named {\"name\":\"bandeja\"}"));
        });
    }

    [Test]
    public async Task AClosedWindowWhoseProcessStaysIsAskedToQuitToo()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Bandeja")]) { Background = [100], Quit = new(true, null, []) };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Bandeja\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(windows.AskedToQuit, Is.EqualTo(new[] { 100 }));
            Assert.That(outcome.Result!.Value.GetProperty("closedWindows").GetInt32(), Is.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("applicationExited").GetBoolean(), Is.True);
        });
    }

    // Controls: a dialog of its own stops everything, and one window asked by its id only ever concerns that window.
    [Test]
    public async Task AWindowAskingToSaveIsNeverFollowedByTheQuit()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "doc")]) { Prompts = "win_a", Background = [100] };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Bandeja\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(windows.AskedToQuit, Is.Empty);
        });
    }

    [Test]
    public async Task OneWindowClosedByItsIdNeverAsksTheApplicationToQuit()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "uno"), Frame("win_b", 100, "dos")]) { Hides = "win_a", Background = [100] };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"windowId\":\"win_a\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result!.Value.GetProperty("hidden").GetBoolean(), Is.True);
            Assert.That(windows.AskedToQuit, Is.Empty);
        });
    }

    [Test]
    public async Task AnOrdinaryApplicationClosesWithoutAskingAnythingElse()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Paint")]);

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Paint\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(windows.AskedToQuit, Is.Empty);
            Assert.That(outcome.Result!.Value.TryGetProperty("applicationExited", out _), Is.False);
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

    // Revisión del núcleo (q-core): a window that already hid before another asks to save is an effect that did occur;
    // the stop said nothing had happened (only closed windows counted there, not the hidden ones the end counts).
    [Test]
    public async Task AStopAfterAWindowHidSaysItsEffectMayHaveOccurred()
    {
        var windows = new FakeWindows([Frame("win_a", 100, "Steam"), Frame("win_b", 100, "Steam")])
        {
            Hides = "win_a",
            Prompts = "win_b",
        };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation("{\"appId\":\"Steam\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True, "a window had hidden already");
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

    // P1.1(b) F024 (falsedades v11, base y candidato): after a close or a minimize, «¿había algo sin guardar?» got «no,
    // no había nada sin guardar» in a turn with no read. Windows only tells whether the application answered the polite
    // close with a dialog of its own; whether it held unsaved changes is not readable, and the receipt says both. With
    // the aid off, the receipt is as before.
    [TestCase("{\"appId\":\"Paint\"}", "unsaved_not_read", true)]
    [TestCase("{\"windowId\":\"win_a\"}", "unsaved_not_read", true)]
    [TestCase("{\"appId\":\"Paint\"}", "none", false)]
    [TestCase("{\"windowId\":\"win_a\"}", "none", false)]
    public async Task AClosedWindowSaysItDidNotAskToSaveAndThatUnsavedChangesAreNotRead(string json, string aids, bool said)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var windows = new FakeWindows([Frame("win_a", 100, "dibujo - Paint")]);

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("closePrompted", out JsonElement prompted)
                && !prompted.GetBoolean(), Is.EqualTo(said));
            Assert.That(outcome.Result!.Value.TryGetProperty("unsavedChanges", out JsonElement unsaved)
                && unsaved.GetString() == "not_readable", Is.EqualTo(said));
        });
    }

    // A window that only hid, or one that asked to save, closed nothing: neither field is said.
    [TestCase("{\"appId\":\"Paint\"}", true)]
    [TestCase("{\"windowId\":\"win_a\"}", true)]
    [TestCase("{\"windowId\":\"win_a\"}", false)]
    public async Task AWindowThatHidOrAskedToSaveSaysNothingOfUnreadChanges(string json, bool hides)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("unsaved_not_read");
        var windows = new FakeWindows([Frame("win_a", 100, "Paint")])
        {
            Hides = hides ? "win_a" : null,
            Prompts = hides ? null : "win_a",
        };

        OperationOutcome outcome = await new AppCloseHandler(windows).ExecuteAsync(
            Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result!.Value.TryGetProperty("closePrompted", out JsonElement prompted)
                && !prompted.GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.TryGetProperty("unsavedChanges", out _), Is.False);
        });
    }

    [TestCase(WindowControlAction.Minimize, "unsaved_not_read", true)]
    [TestCase(WindowControlAction.Minimize, "none", false)]
    [TestCase(WindowControlAction.Maximize, "unsaved_not_read", false)]
    public async Task OnlyAMinimizedWindowSaysUnsavedChangesAreNotRead(WindowControlAction action, string aids, bool said)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var windows = new FakeWindows([Frame("win_a", 100, "dibujo - Paint")]);

        OperationOutcome outcome = await new WindowActionHandler("window.minimize", action, windows)
            .ExecuteAsync(Invocation("{\"windowId\":\"win_a\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("unsavedChanges", out JsonElement unsaved)
                && unsaved.GetString() == "not_readable", Is.EqualTo(said));
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

        internal string? Hides { get; init; }

        internal int[] Background { get; init; } = [];

        internal ApplicationQuitResult Quit { get; init; } = ApplicationQuitResult.NotTried;

        internal List<int> AskedToQuit { get; } = [];

        public ValueTask<ApplicationQuitResult> QuitApplicationAsync(
            IReadOnlyCollection<int> processIds, CancellationToken cancellationToken)
        {
            AskedToQuit.AddRange(processIds);
            return ValueTask.FromResult(Quit);
        }

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
            ValueTask.FromResult(new WindowActionResult(true, true,
                windows.Single(candidate => candidate.WindowId == windowId) with { State = action.ToString() }, null));

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }
}
