using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
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
        // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que realmente son
        // peligrosas»): a start that may have acted, of a reversible note, is retried without asking.
        OperationResponse recovered = await engine.ExecuteAsync(
            original with { RequestId = Guid.NewGuid().ToString("D") }, CancellationToken.None);

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

    // Revisión 2026-10-25 (reservas de reintento): a retryable answer is retried as before within its window; past it,
    // the next invocation finds it ended (its own failure written final, so its reservation is free) and a late retry
    // replays that failure instead of running again.
    [Test]
    public async Task ARetryNobodyMadeWithinItsWindowEndsWithItsOwnFailure()
    {
        var handler = new RetryableOnceHandler();
        var other = new CountingHandler(OperationRisk.Reversible, "task.create");
        var time = new ManualTime(DateTimeOffset.Parse("2026-10-25T20:00:00Z", System.Globalization.CultureInfo.InvariantCulture));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([handler, other]),
            journal,
            new MissionEngineOptions { Time = time });
        OperationRequest request = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");

        OperationResponse pending = await engine.ExecuteAsync(request, CancellationToken.None);
        time.Advance(MissionEngine.RetryWindow - TimeSpan.FromSeconds(1));
        await engine.ExecuteAsync(OtherRequest(), CancellationToken.None);
        CompletedInvocation? withinTheWindow = await journal.FindCompletedAsync(request.InvocationId, CancellationToken.None);
        time.Advance(TimeSpan.FromSeconds(2));
        await engine.ExecuteAsync(OtherRequest(), CancellationToken.None);
        CompletedInvocation? pastTheWindow = await journal.FindCompletedAsync(request.InvocationId, CancellationToken.None);
        OperationResponse late = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pending.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(withinTheWindow, Is.Null);
            Assert.That(pastTheWindow?.Response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(pastTheWindow?.Response.ErrorCode, Is.EqualTo("reconciliation_required"));
            Assert.That(late.Replayed, Is.True);
            Assert.That(late.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(late.EffectMayHaveOccurred, Is.False);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });

        static OperationRequest OtherRequest() => new(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "task.create",
            JsonDocument.Parse("{}").RootElement.Clone());
    }

    // Revisión 2026-10-22 (K-6): the yes was given to one execution. A retryable outcome whose effect may have happened
    // leaves the invocation open, and the same token used to run it again without asking; it is spent, and the retry
    // asks again, saying an execution already began (reconciliationRequired). One with no effect keeps its grant
    // (ConfirmationAuthorityTests.Retryable_outcome_keeps_grant_and_terminal_outcome_revokes_it).
    [Test]
    public async Task ARetryableOutcomeSpendsTheConfirmationAndTheRetryAsksAgain()
    {
        var handler = new RetryableOnceHandler(OperationRisk.Irreversible, effectMayHaveOccurred: true);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"title\":\"Compras\",\"content\":\"pan\"}");

        OperationResponse challenge = await engine.ExecuteAsync(request, CancellationToken.None);
        string token = challenge.Result!.Value.GetProperty("token").GetString()!;
        OperationResponse confirmed = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D"), ConfirmationToken = token },
            CancellationToken.None);
        OperationResponse retried = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D"), ConfirmationToken = token },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(confirmed.ErrorCode, Is.EqualTo("reconciliation_required"));
            Assert.That(retried.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(retried.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(retried.Result!.Value.GetProperty("reconciliationRequired").GetBoolean(), Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
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

        // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que realmente son
        // peligrosas»): the handler threw after it may have acted, but a reversible note that asks nothing with these
        // arguments is retried on the same identity without asking (auditoría del núcleo 2026-10-23 had it ask).
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

    // Revisión 2026-10-22 (K-5): a JSON string with a lone surrogate («\uD800») parses, but reading it as text throws;
    // it used to escape the engine before any terminal state and end the core (exit 70). It is refused as invalid
    // arguments, in a value or in a name, and nothing runs.
    [TestCase("""{"title":"\uD800","content":"pan"}""")]
    [TestCase("""{"title":"Compras","content":["\uDC00x"]}""")]
    [TestCase("""{"\uD800":"pan"}""")]
    public async Task ArgumentsThatAreNotTextAreRefusedAsInvalidArguments(string json)
    {
        var handler = new CountingHandler(OperationRisk.Reversible);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(CreateRequest(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(response.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    // Auditoría del núcleo 2026-10-23: an invocation whose earlier run may have acted is never run again without the
    // person: not in Bypass, and not on the yes given before that run (it was for that run only).
    [Test]
    public async Task AnUncertainStartAsksBeforeRunningAgainEvenInBypassAndOnAnEarlierYes()
    {
        var handler = new RetryableOnceHandler(OperationRisk.Irreversible, effectMayHaveOccurred: false);
        ConfirmationMode mode = ConfirmationMode.Normal;
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => mode });
        OperationRequest request = CreateRequest("{}");
        await journal.RecordStartedAsync(request, RequestFingerprint.Compute(request), CancellationToken.None);

        mode = ConfirmationMode.Bypass;
        OperationResponse inBypass = await engine.ExecuteAsync(request, CancellationToken.None);
        mode = ConfirmationMode.Normal;
        (OperationResponse asked, OperationResponse confirmed) = await UncertainStart.RetryAsync(engine, request);

        Assert.Multiple(() =>
        {
            Assert.That(inBypass.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(inBypass.Result!.Value.GetProperty("reconciliationRequired").GetBoolean(), Is.True);
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            // The yes to the reconciliation runs it; a retryable run with nothing done keeps it pending.
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que realmente son
    // peligrosas»): a retry of an invocation that started and did not end runs without asking when it only reads or
    // changes something reversibly and asks nothing with these arguments (it asked before); one whose arguments ask (a
    // click on «Enviar») still asks with reconciliationRequired, as an irreversible one does.
    [TestCase(OperationRisk.ReadOnly, "note.list", "{}", false)]
    [TestCase(OperationRisk.Reversible, "note.create", "{\"title\":\"Compras\",\"content\":\"pan\"}", false)]
    [TestCase(OperationRisk.Reversible, "input.visible.click", "{\"label\":\"Enviar\"}", true)]
    [TestCase(OperationRisk.Irreversible, "note.delete", "{}", true)]
    public async Task AnUncertainStartAsksAgainOnlyWhenItsRiskOrArgumentsDo(
        OperationRisk risk, string operation, string arguments, bool asks)
    {
        var handler = new CountingHandler(risk, operation);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest(arguments) with { Operation = operation };
        await journal.RecordStartedAsync(request, RequestFingerprint.Compute(request), CancellationToken.None);

        OperationResponse retried = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(retried.ErrorCode, asks ? Is.EqualTo("confirmation_required") : Is.Null);
            Assert.That(handler.ExecutionCount, Is.EqualTo(asks ? 0 : 1));
            if (asks)
                Assert.That(retried.Result!.Value.GetProperty("reconciliationRequired").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AYesGivenBeforeARunThatMayHaveActedDoesNotRunItAgain()
    {
        var handler = new RetryableOnceHandler(OperationRisk.Irreversible, effectMayHaveOccurred: true);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{}");

        OperationResponse challenge = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationRequest approved = request with
        {
            ConfirmationToken = challenge.Result!.Value.GetProperty("token").GetString(),
        };
        OperationResponse first = await engine.ExecuteAsync(approved, CancellationToken.None);
        OperationResponse sameYes = await engine.ExecuteAsync(
            approved with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(first.EffectMayHaveOccurred, Is.True);
            Assert.That(sameYes.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(sameYes.Result!.Value.GetProperty("reconciliationRequired").GetBoolean(), Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    // Auditoría del núcleo 2026-10-23: a success the handler could not verify did act, so it ends failed with its effect
    // possibly standing, in the response and in the facts the model reads, and its replay says the same.
    [Test]
    public async Task AnUnverifiedSuccessEndsFailedWithItsEffectPossiblyStanding()
    {
        var handler = new UnverifiedSuccessHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{}");

        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        using JsonDocument facts = JsonDocument.Parse(first.Message);
        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(first.Verified, Is.False);
            Assert.That(first.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(first.EffectMayHaveOccurred, Is.True);
            Assert.That(facts.RootElement.GetProperty("effectUncertain").GetBoolean(), Is.True);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.EffectMayHaveOccurred, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    // D3 2026-09-20: External asks only for message/email operations; note.create as
    // Irreversible keeps the confirmation-before-effect check.
    [TestCase(OperationRisk.Irreversible, "confirmation_required")]
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

    private sealed class CountingHandler(OperationRisk risk, string operation = "note.create") : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new(operation, risk, "Create a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private sealed class UnverifiedSuccessHandler : IOperationHandler
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
            return ValueTask.FromResult(new OperationOutcome(true, false, null, null));
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

    private sealed class RetryableOnceHandler(
        OperationRisk risk = OperationRisk.Reversible,
        bool effectMayHaveOccurred = false) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", risk, "Resolve a recoverable operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(ExecutionCount == 1
                ? OperationOutcome.RetryableFailure(
                    "reconciliation_required",
                    effectMayHaveOccurred: effectMayHaveOccurred)
                : OperationOutcome.Success());
        }
    }

    private sealed class ManualTime(DateTimeOffset now) : TimeProvider
    {
        private DateTimeOffset _now = now;

        public void Advance(TimeSpan by) => _now += by;

        public override DateTimeOffset GetUtcNow() => _now;
    }
}
