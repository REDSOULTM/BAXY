using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class MissionEngineTests
{
    [Test]
    public void ExposesASinglePublicConstructor()
    {
        System.Reflection.ConstructorInfo[] constructors = typeof(MissionEngine)
            .GetConstructors();
        Assert.That(constructors, Has.Length.EqualTo(1));
        System.Reflection.ParameterInfo[] parameters = constructors[0].GetParameters();
        Assert.That(parameters, Has.Length.EqualTo(3));
        Assert.That(parameters[0].ParameterType, Is.EqualTo(typeof(OperationRegistry)));
        Assert.That(parameters[1].ParameterType, Is.EqualTo(typeof(IInvocationJournal)));
        Assert.That(parameters[2].ParameterType, Is.EqualTo(typeof(MissionEngineOptions)));
        Assert.That(parameters[2].IsOptional, Is.True);
    }

    [Test]
    public async Task ExecutesVerifiedEffectAndReplaysWithoutRepeatingIt()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");

        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(request with { RequestId = Guid.NewGuid().ToString("D") }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(first.Verified, Is.True);
            Assert.That(first.Replayed, Is.False);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task RejectsInvocationReuseWithDifferentArguments()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest first = CreateRequest("{\"content\":\"pan\",\"title\":\"Compras\"}");
        OperationRequest conflicting = first with
        {
            RequestId = Guid.NewGuid().ToString("D"),
            Arguments = Parse("{\"title\":\"Compras\",\"content\":\"café\"}"),
        };

        await engine.ExecuteAsync(first, CancellationToken.None);
        OperationResponse response = await engine.ExecuteAsync(conflicting, CancellationToken.None);

        Assert.That(response.ErrorCode, Is.EqualTo("idempotency_conflict"));
        Assert.That(handler.ExecutionCount, Is.EqualTo(1));
    }

    [Test]
    public async Task RejectsIncompleteInvocationReuseWithoutPoisoningTheJournal()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest original = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");
        await journal.RecordStartedAsync(
            original,
            RequestFingerprint.Compute(original),
            CancellationToken.None);
        OperationRequest conflicting = original with
        {
            RequestId = Guid.NewGuid().ToString("D"),
            Arguments = Parse("{\"title\":\"Compras\",\"content\":\"café\"}"),
        };

        OperationResponse conflict = await engine.ExecuteAsync(conflicting, CancellationToken.None);
        OperationResponse recovered = await engine.ExecuteAsync(
            original with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(conflict.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(conflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recovered.Verified, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task CanonicalFingerprintIgnoresObjectPropertyOrder()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest first = CreateRequest("{\"content\":\"pan\",\"title\":\"Compras\"}");
        OperationRequest reordered = first with
        {
            RequestId = Guid.NewGuid().ToString("D"),
            Arguments = Parse("{\"title\":\"Compras\",\"content\":\"pan\"}"),
        };

        await engine.ExecuteAsync(first, CancellationToken.None);
        OperationResponse response = await engine.ExecuteAsync(reordered, CancellationToken.None);

        Assert.That(response.Replayed, Is.True);
        Assert.That(handler.ExecutionCount, Is.EqualTo(1));
    }

    [Test]
    public async Task ConcurrentReplaysExecuteTheEffectOnceAndEchoEachCurrentRequestId()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest template = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");
        OperationRequest[] requests = Enumerable.Range(0, 16)
            .Select(_ => template with { RequestId = Guid.NewGuid().ToString("D") })
            .ToArray();
        var start = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        Task<OperationResponse>[] calls = requests
            .Select(async request =>
            {
                await start.Task;
                return await engine.ExecuteAsync(request, CancellationToken.None);
            })
            .ToArray();
        start.SetResult();

        OperationResponse[] responses = await Task.WhenAll(calls);

        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(responses.Count(static response => !response.Replayed), Is.EqualTo(1));
            Assert.That(responses.Count(static response => response.Replayed), Is.EqualTo(15));
            Assert.That(
                responses.Select(static response => response.RequestId),
                Is.EqualTo(requests.Select(static request => request.RequestId)));
            Assert.That(responses, Has.All.Matches<OperationResponse>(
                response => response.Status == OperationStatuses.Completed && response.Verified));
        });
    }

    [Test]
    public async Task RejectedInvocationReplaysAndCannotBeReusedForAnotherOperation()
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest unknown = CreateRequest("{}") with { Operation = "note.missing" };
        string replayRequestId = Guid.NewGuid().ToString("D");

        OperationResponse first = await engine.ExecuteAsync(unknown, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            unknown with { RequestId = replayRequestId },
            CancellationToken.None);
        OperationResponse conflictingReuse = await engine.ExecuteAsync(
            unknown with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                Operation = "note.create",
                Arguments = Parse("{\"title\":\"Compras\",\"content\":\"pan\"}"),
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(first.ErrorCode, Is.EqualTo("unknown_operation"));
            Assert.That(replay.ErrorCode, Is.EqualTo("unknown_operation"));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.RequestId, Is.EqualTo(replayRequestId));
            Assert.That(conflictingReuse.ErrorCode, Is.EqualTo("idempotency_conflict"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task FailedOutcomeResultIsJournaledAndReplayedWithoutReexecution()
    {
        JsonElement result = Parse("{\"candidates\":[{\"noteId\":\"candidate\"}]}");
        var handler = new FailedResultHandler(result);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"title\":\"Duplicada\"}");

        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(first.ErrorCode, Is.EqualTo("note_ambiguous"));
            Assert.That(first.Result?.GetRawText(), Is.EqualTo(result.GetRawText()));
            Assert.That(replay.Result?.GetRawText(), Is.EqualTo(result.GetRawText()));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task RetryableOutcomeRemainsStartedAndReexecutesWithTheSameIdentity()
    {
        var handler = new RetryableOnceHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");

        OperationResponse pending = await engine.ExecuteAsync(request, CancellationToken.None);
        CompletedInvocation? beforeRetry = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        OperationResponse recovered = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pending.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(pending.ErrorCode, Is.EqualTo("reconciliation_required"));
            Assert.That(beforeRetry, Is.Null);
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recovered.Replayed, Is.False);
            Assert.That(recovered.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(handler.ExecutionCount, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task UnexpectedHandlerFailureRemainsStartedAndRetriesWithTheSameIdentity()
    {
        var handler = new FailOnceHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");

        Assert.That(
            async () => await engine.ExecuteAsync(request, CancellationToken.None),
            Throws.TypeOf<InvalidOperationException>());
        string fingerprint = RequestFingerprint.Compute(request);
        string? startedFingerprint = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(startedFingerprint, Is.EqualTo(fingerprint));
            Assert.That(completed, Is.Null);
        });

        OperationResponse recovered = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recovered.Verified, Is.True);
            Assert.That(recovered.Replayed, Is.False);
            Assert.That(handler.ExecutionCount, Is.EqualTo(2));
        });
    }

    // D3 2026-09-20: External asks only for message/email operations; note.create as
    // Irreversible keeps the confirmation-before-effect check.
    [TestCase(OperationRisk.Irreversible, "confirmation_required")]
    [TestCase(OperationRisk.Forbidden, "operation_forbidden")]
    public async Task EnforcesRiskBeforeEffect(OperationRisk risk, string expectedError)
    {
        var handler = new CountingHandler(risk);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(CreateRequest("{}"), CancellationToken.None);

        Assert.That(response.ErrorCode, Is.EqualTo(expectedError));
        Assert.That(handler.ExecutionCount, Is.Zero);
    }

    private static OperationRequest CreateRequest(string json) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "note.create",
        Parse(json));

    private static JsonElement Parse(string json) => JsonDocument.Parse(json).RootElement.Clone();

    private sealed class CountingHandler(OperationRisk risk) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", risk, "Create a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private sealed class FailOnceHandler : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Create a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            if (ExecutionCount == 1)
            {
                throw new InvalidOperationException("simulated unmodeled post-effect failure");
            }

            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private sealed class FailedResultHandler(JsonElement result) : IOperationHandler
    {
        private readonly JsonElement _result = result.Clone();

        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Resolve a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Failure(
                "note_ambiguous",
                _result));
        }
    }

    private sealed class RetryableOnceHandler : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Resolve a recoverable operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(ExecutionCount == 1
                ? OperationOutcome.RetryableFailure(
                    "reconciliation_required")
                : OperationOutcome.Success());
        }
    }
}
