using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class OperationOutcomeNarrationTests
{
    [Test]
    public async Task MissionEngineProjectsHandlerResultThroughInjectedNarrator()
    {
        const string canary = "HANDLER-RESULT-MUST-NOT-BECOME-NARRATION";
        JsonElement result = JsonDocument.Parse($"{{\"canary\":\"{canary}\"}}")
            .RootElement
            .Clone();
        var handler = new ResultHandler(result);
        var narrator = new FixedNarrator("Narración separada y determinista.");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { Narrator = narrator });
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            handler.Definition.Name,
            JsonDocument.Parse("{}").RootElement.Clone());

        OperationResponse response = await engine.ExecuteAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Message, Is.EqualTo("Narración separada y determinista."));
            Assert.That(response.Message, Does.Not.Contain(canary));
            Assert.That(response.Result?.GetProperty("canary").GetString(), Is.EqualTo(canary));
            Assert.That(narrator.ObservedOperation, Is.EqualTo(handler.Definition.Name));
            Assert.That(narrator.ObservedOutcome, Is.SameAs(handler.Outcome));
        });
    }

    [Test]
    public void OperationOutcomeDoesNotExposeNaturalLanguageMessage()
    {
        Assert.That(typeof(OperationOutcome).GetProperty("Message"), Is.Null);
        Assert.That(
            typeof(OperationOutcome).GetConstructors()
                .SelectMany(static constructor => constructor.GetParameters())
                .Select(static parameter => parameter.Name),
            Does.Not.Contain("message"));
    }

    private sealed class ResultHandler(JsonElement result) : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public OperationOutcome Outcome { get; } = OperationOutcome.Success(result);

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(Outcome);
        }
    }

    private sealed class FixedNarrator(string message) : IOperationResponseNarrator
    {
        public string? ObservedOperation { get; private set; }

        public OperationOutcome? ObservedOutcome { get; private set; }

        public string Narrate(string operation, OperationOutcome outcome)
        {
            ObservedOperation = operation;
            ObservedOutcome = outcome;
            return message;
        }

        public string NarrateStatus(string operation, string status, string? errorCode)
        {
            ObservedOperation = operation;
            return message;
        }
    }
}
