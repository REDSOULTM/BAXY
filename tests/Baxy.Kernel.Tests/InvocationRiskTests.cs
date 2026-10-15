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
    public async Task AForbiddenOperationStaysForbiddenWhateverTheHandlerSays()
    {
        var handler = new AssessingHandler(OperationRisk.Forbidden, documentless: "win_settings");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            Request("""{"windowId":"win_settings"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("operation_forbidden"));
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

    private static OperationRequest Request(string json) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "app.close",
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class AssessingHandler(OperationRisk risk, string? documentless)
        : IOperationHandler, IInvocationRiskAssessor
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } = new("app.close", risk, "Close a resolved window.");

        public OperationRisk? AssessInvocationRisk(JsonElement arguments)
        {
            if (documentless is null)
            {
                throw new InvalidOperationException("the window cannot be placed");
            }

            return arguments.GetProperty("windowId").GetString() == documentless ? OperationRisk.Reversible : null;
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
