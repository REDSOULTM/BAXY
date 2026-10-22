using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
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
