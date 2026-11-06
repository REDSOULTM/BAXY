using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// v3 r6 lectores (t2-r4 c04-5 «ya quedó, cierra configuración porfa» → «¿Quieres confirmar…?»): the engine asks a
/// handler for the risk of the invocation in front of it. A close the handler says loses nothing goes straight; any
/// other keeps the declared risk and asks; a forbidden operation stays forbidden whatever the handler says.
/// </summary>
[TestFixture]
public sealed class InvocationRiskTests
{
    [Test]
    public async Task AnInvocationTheHandlerAssessesReversibleGoesWithoutAsking()
    {
        var handler = new AssessingHandler(OperationRisk.Irreversible, documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_settings"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task AnyOtherInvocationOfTheSameOperationStillAsks()
    {
        // Contracaso: a window with a document (Word, Notepad, Paint) keeps work_loss and asks before the effect.
        var handler = new AssessingHandler(OperationRisk.Irreversible, documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task AHandlerThatFailsToAssessKeepsTheDeclaredRisk()
    {
        var handler = new AssessingHandler(OperationRisk.Irreversible, documentless: null);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_settings"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    // Auditoría del núcleo 2026-10-23: a read that fails with any exception (a window read's IOException or
    // Win32Exception, a timeout of its own) keeps the declared risk, in a read that could lower it and in one that could
    // raise it; it never ends the engine.
    [TestCase(typeof(IOException))]
    [TestCase(typeof(System.ComponentModel.Win32Exception))]
    [TestCase(typeof(TimeoutException))]
    [TestCase(typeof(OperationCanceledException))]
    public async Task AReadThatFailsWithAnyExceptionKeepsTheDeclaredRisk(Type failure)
    {
        var lowering = new FailingReadHandler(OperationRisk.Irreversible, (Exception)Activator.CreateInstance(failure)!);
        var raising = new FailingReadHandler(OperationRisk.Reversible, (Exception)Activator.CreateInstance(failure)!);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([lowering, raising]), journal);

        OperationResponse asked = await engine.ExecuteAsync(
            Request("""{"windowId":"win_settings"}"""), CancellationToken.None);
        OperationResponse ran = await engine.ExecuteAsync(
            Request("""{"windowId":"win_settings"}""") with { Operation = "app.open" }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(lowering.ExecutionCount, Is.Zero);
            Assert.That(ran.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(raising.PreflightCount, Is.EqualTo(1));
            Assert.That(raising.ExecutionCount, Is.EqualTo(1));
        });
    }

    // Auditoría del núcleo 2026-10-23: a MayRaise that throws says nothing; the invocation goes as declared, unread, and
    // the engine answers.
    [Test]
    public async Task AMayRaiseThatThrowsKeepsTheDeclaredRiskUnread()
    {
        var handler = new ThrowingMayRaiseHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_dialog"}""") with { Operation = "app.open" }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.PreflightCount, Is.Zero);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    private sealed class ThrowingMayRaiseHandler : IOperationHandler, IInvocationPreflight
    {
        public int ExecutionCount { get; private set; }

        public int PreflightCount { get; private set; }

        public OperationDefinition Definition { get; } = new("app.open", OperationRisk.Reversible, "Open an application.");

        public bool MayRaise(JsonElement arguments) => throw new System.ComponentModel.Win32Exception(5);

        public ValueTask<InvocationPreflightResult> PreflightAsync(
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            PreflightCount++;
            return ValueTask.FromResult(InvocationPreflightResult.Raised(OperationRisk.Irreversible));
        }

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    [Test]
    public void TheCallersCancellationDuringAReadGoesOnAsACancellation()
    {
        var handler = new FailingReadHandler(OperationRisk.Irreversible, null);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        using var cancelled = new CancellationTokenSource();
        handler.Cancel = cancelled;

        Assert.That(
            async () => await engine.ExecuteAsync(Request("""{"windowId":"win_settings"}"""), cancelled.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(handler.ExecutionCount, Is.Zero);
    }

    // Al máximo, flujos («¿Borro viejo.txt?» → «sí» → «no existe»): a target that is not there is that failure now,
    // with its candidates, and no yes is asked for what cannot run; a target there once asks as before.
    [Test]
    public async Task ATargetThatIsNotThereFailsWithoutAskingForAYes()
    {
        JsonElement candidates = JsonDocument.Parse("""{"candidates":["a/viejo.txt","b/viejo.txt"]}""").RootElement.Clone();
        var handler = new AssessingHandler(
            OperationRisk.Irreversible, documentless: null, OperationOutcome.Failure("known_file_ambiguous", candidates));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request("""{"windowId":"win_word"}""");

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(response.Result!.Value.GetProperty("candidates").GetArrayLength(), Is.EqualTo(2));
            Assert.That(response.EffectMayHaveOccurred, Is.False);
            Assert.That(handler.ExecutionCount, Is.Zero);
            // Terminal and journaled: the same invocation answers the same and reads nothing again.
            Assert.That(replay.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(handler.PreflightCount, Is.EqualTo(1));
        });
    }

    // Contracaso: an invocation that started before and never completed may have had its effect (the file is gone because
    // it was trashed): a «not found» now is not its end; it is reconciled with the person as before.
    [Test]
    public async Task AnInvocationStartedBeforeIsNotEndedByWhatIsMissingNow()
    {
        var handler = new AssessingHandler(
            OperationRisk.Irreversible, documentless: null, OperationOutcome.Failure("known_file_not_found"));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request("""{"windowId":"win_word"}""");
        await journal.RecordStartedAsync(request, RequestFingerprint.Compute(request), CancellationToken.None);

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(response.Result!.Value.GetProperty("reconciliationRequired").GetBoolean(), Is.True);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task ATargetThereOnceStillAsksAndRunsOnTheYes()
    {
        var handler = new AssessingHandler(OperationRisk.Irreversible, documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request("""{"windowId":"win_word"}""");

        OperationResponse asked = await engine.ExecuteAsync(request, CancellationToken.None);
        string token = asked.Result!.Value.GetProperty("token").GetString()!;
        OperationResponse confirmed = await engine.ExecuteAsync(
            request with { ConfirmationToken = token }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task AnInvocationThatNeedsNoYesIsNotReadFirst()
    {
        var handler = new AssessingHandler(
            OperationRisk.Reversible, documentless: null, OperationOutcome.Failure("known_file_not_found"));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.PreflightCount, Is.Zero);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    // Encargo 83: what the read found of a raised invocation reaches whoever asks the person, inside the challenge.
    [Test]
    public async Task TheChallengeOfARaisedInvocationCarriesWhatTheReadFound()
    {
        using JsonDocument facts = JsonDocument.Parse("""{"systemChange":{"control":"Interruptor"}}""");
        var handler = new RaisingHandler(InvocationPreflightResult.Raised(OperationRisk.Irreversible, facts.RootElement.Clone()));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse asked = await engine.ExecuteAsync(
            Request("""{"windowId":"win_panel"}""") with { Operation = "app.open" }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(asked.Result!.Value.GetProperty("facts").GetProperty("systemChange").GetProperty("control").GetString(),
                Is.EqualTo("Interruptor"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    // Renew al máximo (guarda msconfig, guarda diálogo destructivo): an invocation whose declared risk goes without
    // asking, and whose handler finds it riskier (an opening of msconfig, the «Sí» that replaces a file), waits for the
    // yes bound to it, and runs on that yes.
    [Test]
    public async Task AnInvocationTheHandlerFindsRiskierAsksThoughItsDeclaredRiskWouldNot()
    {
        var handler = new RaisingHandler(InvocationPreflightResult.Raised(OperationRisk.Irreversible));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request("""{"windowId":"win_dialog"}""") with { Operation = "app.open" };

        OperationResponse asked = await engine.ExecuteAsync(request, CancellationToken.None);
        int executedBeforeTheYes = handler.ExecutionCount;
        string token = asked.Result!.Value.GetProperty("token").GetString()!;
        OperationResponse confirmed = await engine.ExecuteAsync(
            request with { ConfirmationToken = token }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(executedBeforeTheYes, Is.Zero);
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    // Contracasos: a read that finds nothing riskier, or a failure, goes without asking and runs (a failure is never taken
    // from this read); in Bypass the invocation is not read and goes as the rest of what is risky.
    [Test]
    public async Task ARaisingReadThatFindsNothingOrAFailureGoesWithoutAsking()
    {
        foreach (InvocationPreflightResult found in new[]
        {
            InvocationPreflightResult.Proceed,
            InvocationPreflightResult.Fails(OperationOutcome.Failure("known_file_not_found")),
        })
        {
            var handler = new RaisingHandler(found);
            using var journal = new InMemoryInvocationJournal();
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

            OperationResponse response = await engine.ExecuteAsync(
                Request("""{"windowId":"win_dialog"}""") with { Operation = "app.open" }, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(handler.PreflightCount, Is.EqualTo(1));
                Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            });
        }
    }

    [Test]
    public async Task InBypassARaisingInvocationIsNotReadAndGoes()
    {
        var handler = new RaisingHandler(InvocationPreflightResult.Raised(OperationRisk.Irreversible));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new MissionEngineOptions { ConfirmationMode = static () => ConfirmationMode.Bypass });

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_dialog"}""") with { Operation = "app.open" }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.PreflightCount, Is.Zero);
        });
    }

    private sealed class RaisingHandler(InvocationPreflightResult found) : IOperationHandler, IInvocationPreflight
    {
        public int ExecutionCount { get; private set; }

        public int PreflightCount { get; private set; }

        public OperationDefinition Definition { get; } = new("app.open", OperationRisk.Reversible, "Open an application.");

        public bool MayRaise(JsonElement arguments) => true;

        public ValueTask<InvocationPreflightResult> PreflightAsync(
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            PreflightCount++;
            return ValueTask.FromResult(found);
        }

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    // A read of the invocation that fails (Irreversible: one that could lower it; Reversible as app.open: one that could
    // raise it), or, with no failure, cancels the caller's token as it reads.
    private sealed class FailingReadHandler(OperationRisk risk, Exception? failure) : IOperationHandler, IInvocationPreflight
    {
        public int ExecutionCount { get; private set; }

        public int PreflightCount { get; private set; }

        public CancellationTokenSource? Cancel { get; set; }

        public OperationDefinition Definition { get; } = risk == OperationRisk.Irreversible
            ? new("app.close", risk, "Close a resolved window.")
            : new("app.open", risk, "Open an application.");

        public bool MayRaise(JsonElement arguments) => true;

        public ValueTask<InvocationPreflightResult> PreflightAsync(
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            PreflightCount++;
            if (Cancel is { } cancel)
            {
                cancel.Cancel();
                cancellationToken.ThrowIfCancellationRequested();
            }

            throw failure!;
        }

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private static OperationRequest Request(string json) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "app.close",
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class AssessingHandler(OperationRisk risk, string? documentless, OperationOutcome? missing = null)
        : IOperationHandler, IInvocationPreflight
    {
        public int ExecutionCount { get; private set; }

        public int PreflightCount { get; private set; }

        public OperationDefinition Definition { get; } = new("app.close", risk, "Close a resolved window.");

        public ValueTask<InvocationPreflightResult> PreflightAsync(
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            PreflightCount++;
            if (missing is not null)
            {
                return ValueTask.FromResult(InvocationPreflightResult.Fails(missing));
            }

            if (documentless is null)
            {
                throw new InvalidOperationException("the window cannot be placed");
            }

            return ValueTask.FromResult(arguments.GetProperty("windowId").GetString() == documentless
                ? InvocationPreflightResult.Lowered(OperationRisk.Reversible)
                : InvocationPreflightResult.Proceed);
        }

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }
}
