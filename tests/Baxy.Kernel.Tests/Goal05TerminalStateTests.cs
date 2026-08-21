using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class Goal05TerminalStateTests
{
    [OneTimeSetUp]
    public void ResetScratchLog() => Goal05KernelScratch.Write("terminal-states.log", string.Empty);
    [Test]
    public async Task RetryableFailureStaysPendingAndTheSameInvocationCanRetry()
    {
        var handler = new ScriptedHandler(
            OperationOutcome.RetryableFailure(
                "reconciliation_required",
                effectMayHaveOccurred: true,
                causeCode: "effect_uncertain"),
            OperationOutcome.Success());
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request("note.create", "{\"title\":\"Goal05\",\"content\":\"pending\"}");

        OperationResponse pending = await engine.ExecuteAsync(request, CancellationToken.None);
        CompletedInvocation? beforeRetry = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        OperationResponse recovered = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pending.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(pending.Verified, Is.False);
            Assert.That(pending.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(beforeRetry, Is.Null);
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recovered.Verified, Is.True);
            Assert.That(recovered.Replayed, Is.False);
            Assert.That(recovered.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(handler.ExecutionCount, Is.EqualTo(2));
        });
        Goal05KernelScratch.Append(
            "terminal-states.log",
            $"retryable status={pending.Status} recovered={recovered.Status} executions={handler.ExecutionCount}{Environment.NewLine}");
    }

    [Test]
    public async Task AmbiguousNonRetryableEffectIsTerminalFailedAndReplayDoesNotReapply()
    {
        var handler = new ScriptedHandler(
            OperationOutcome.Failure(
                "external_verification_failed",
                effectMayHaveOccurred: true,
                causeCode: "external_effect_ambiguous"));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = Request(
            "note.create",
            "{\"title\":\"Goal05\",\"content\":\"ambiguous\"}");

        OperationResponse failed = await engine.ExecuteAsync(request, CancellationToken.None);
        CompletedInvocation? recorded = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(failed.Verified, Is.False);
            Assert.That(failed.EffectMayHaveOccurred, Is.True);
            Assert.That(failed.CauseCode, Is.EqualTo("external_effect_ambiguous"));
            Assert.That(recorded, Is.Not.Null);
            Assert.That(recorded!.Response.EffectMayHaveOccurred, Is.True);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(replay.EffectMayHaveOccurred, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
        Goal05KernelScratch.Append(
            "terminal-states.log",
            $"ambiguous status={failed.Status} replayed={replay.Replayed} executions={handler.ExecutionCount}{Environment.NewLine}");
    }

    [Test]
    public async Task ConfirmationTokenDoesNotAuthorizeADifferentInvocation()
    {
        var handler = new ScriptedHandler(OperationOutcome.Success());
        handler.DefinitionOverride = new OperationDefinition(
            "message.send",
            OperationRisk.External,
            "Send a message.");
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest original = Request(
            "message.send",
            "{\"destination\":\"equipo\"}");
        OperationResponse challenge = await engine.ExecuteAsync(original, CancellationToken.None);
        string token = challenge.Result!.Value.GetProperty("token").GetString()!;

        OperationResponse otherInvocation = await engine.ExecuteAsync(
            original with
            {
                RequestId = NewId(),
                InvocationId = NewId(),
                ConfirmationToken = token,
            },
            CancellationToken.None);
        OperationResponse granted = await engine.ExecuteAsync(
            original with { RequestId = NewId(), ConfirmationToken = token },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(challenge.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(challenge.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(otherInvocation.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(otherInvocation.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(granted.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
        Goal05KernelScratch.Append(
            "terminal-states.log",
            $"confirmation other={otherInvocation.Status} granted={granted.Status} executions={handler.ExecutionCount}{Environment.NewLine}");
    }

    private static OperationRequest Request(string operation, string json) => new(
        ProtocolTypes.OperationRequest,
        NewId(),
        NewId(),
        NewId(),
        operation,
        JsonDocument.Parse(json).RootElement.Clone());

    private static string NewId() => Guid.NewGuid().ToString("D");

    private sealed class ScriptedHandler : IOperationHandler
    {
        private readonly Queue<OperationOutcome> _outcomes;

        public ScriptedHandler(params OperationOutcome[] outcomes)
        {
            _outcomes = new Queue<OperationOutcome>(outcomes);
            DefinitionOverride = new OperationDefinition(
                "note.create",
                OperationRisk.Reversible,
                "Test operation.");
        }

        public int ExecutionCount { get; private set; }

        public OperationDefinition DefinitionOverride { get; set; }

        public OperationDefinition Definition => DefinitionOverride;

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            if (_outcomes.Count == 0)
            {
                throw new InvalidOperationException("No scripted outcome remains.");
            }

            return ValueTask.FromResult(_outcomes.Dequeue());
        }
    }
}

internal static class Goal05KernelScratch
{
    private const string DirectoryPath =
        @"C:\Users\usuario\AppData\Local\Temp\grok-goal-317c6834ac48\implementer";

    internal static void Write(string name, string content)
    {
        if (!Directory.Exists(DirectoryPath))
        {
            return;
        }

        File.WriteAllText(Path.Combine(DirectoryPath, name), content);
    }

    internal static void Append(string name, string content)
    {
        if (!Directory.Exists(DirectoryPath))
        {
            return;
        }

        File.AppendAllText(Path.Combine(DirectoryPath, name), content);
    }
}
