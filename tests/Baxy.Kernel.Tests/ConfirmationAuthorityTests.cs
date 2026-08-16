using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class ConfirmationAuthorityTests
{
    private static readonly DateTimeOffset InitialTime =
        new(2026, 7, 15, 12, 0, 0, TimeSpan.Zero);

    [Test]
    public void Confirmation_debug_strings_never_expose_the_bearer()
    {
        var authority = new InMemoryConfirmationAuthority(
            new ManualTimeProvider(InitialTime));
        var binding = new ConfirmationBinding(NewId(), NewId(), new string('a', 64));
        ConfirmationAuthorization authorization = authority.AuthorizeOrIssue(binding, null);
        string token = authorization.Challenge!.Token;

        Assert.Multiple(() =>
        {
            Assert.That(authorization.Challenge.ToString(), Does.Not.Contain(token));
            Assert.That(authorization.ToString(), Does.Not.Contain(token));
        });
    }

    [Test]
    public async Task Missing_or_invalid_grant_returns_reusable_public_challenge_without_journaling()
    {
        var clock = new ManualTimeProvider(InitialTime);
        using var journal = new InMemoryInvocationJournal();
        var handler = new CountingHandler(OperationRisk.External);
        var authority = new InMemoryConfirmationAuthority(clock);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal,
                               new MissionEngineOptions { ConfirmationAuthority = authority });
        OperationRequest request = CreateRequest("{\"destination\":\"equipo\"}");

        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse repeated = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);
        OperationResponse invalid = await engine.ExecuteAsync(
            request with { RequestId = NewId(), ConfirmationToken = RandomToken() },
            CancellationToken.None);
        string? started = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);

        string token = RequiredToken(first);
        string expires = RequiredResult(first).GetProperty("expiresAtUtc").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(first.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(first.Verified, Is.False);
            Assert.That(first.Replayed, Is.False);
            Assert.That(RequiredResult(first).GetProperty("version").GetInt32(), Is.EqualTo(1));
            Assert.That(
                RequiredResult(first).GetProperty("reconciliationRequired").GetBoolean(),
                Is.False);
            Assert.That(RequiredToken(repeated), Is.EqualTo(token));
            Assert.That(RequiredToken(invalid), Is.EqualTo(token));
            Assert.That(
                RequiredResult(repeated).GetProperty("expiresAtUtc").GetString(),
                Is.EqualTo(expires));
            Assert.That(
                DateTimeOffset.Parse(expires, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind),
                Is.EqualTo(InitialTime.Add(InMemoryConfirmationAuthority.DefaultLifetime)));
            Assert.That(DecodeToken(token), Has.Length.GreaterThanOrEqualTo(32));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(1));
            Assert.That(started, Is.Null);
            Assert.That(completed, Is.Null);
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(
                () => ProtocolJson.SerializeToUtf8Bytes(first),
                Throws.Nothing);
        });
    }

    [Test]
    public async Task Grant_is_bound_to_arguments_mission_invocation_and_operation()
    {
        using var journal = new InMemoryInvocationJournal();
        var primary = new CountingHandler(OperationRisk.External);
        var secondary = new CountingHandler(OperationRisk.External, "message.send");
        using var engine = new MissionEngine(new OperationRegistry([primary, secondary]), journal);
        OperationRequest request = CreateRequest("{\"destination\":\"equipo\"}");
        string token = RequiredToken(await engine.ExecuteAsync(request, CancellationToken.None));
        OperationRequest[] otherBindings =
        [
            request with
            {
                RequestId = NewId(),
                Arguments = Parse("{\"destination\":\"otra-persona\"}"),
                ConfirmationToken = token,
            },
            request with
            {
                RequestId = NewId(),
                MissionId = NewId(),
                ConfirmationToken = token,
            },
            request with
            {
                RequestId = NewId(),
                InvocationId = NewId(),
                ConfirmationToken = token,
            },
            request with
            {
                RequestId = NewId(),
                Operation = "message.send",
                ConfirmationToken = token,
            },
        ];

        var rejectedGrants = new List<OperationResponse>();
        foreach (OperationRequest otherBinding in otherBindings)
        {
            rejectedGrants.Add(await engine.ExecuteAsync(otherBinding, CancellationToken.None));
        }

        OperationResponse original = await engine.ExecuteAsync(
            request with { RequestId = NewId(), ConfirmationToken = token },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(
                rejectedGrants,
                Has.All.Matches<OperationResponse>(response =>
                    response.Status == OperationStatuses.Pending
                    && response.ErrorCode == "confirmation_required"));
            Assert.That(original.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(primary.ExecutionCount, Is.EqualTo(1));
            Assert.That(secondary.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task Expired_grant_is_rejected_and_replaced_without_reserving_the_journal()
    {
        var clock = new ManualTimeProvider(InitialTime);
        using var journal = new InMemoryInvocationJournal();
        var handler = new CountingHandler(OperationRisk.Irreversible);
        var authority = new InMemoryConfirmationAuthority(
            clock,
            TimeSpan.FromSeconds(30));
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal,
                               new MissionEngineOptions { ConfirmationAuthority = authority });
        OperationRequest request = CreateRequest("{}");
        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        string expiredToken = RequiredToken(first);
        clock.Advance(TimeSpan.FromSeconds(30));

        OperationResponse expired = await engine.ExecuteAsync(
            request with { RequestId = NewId(), ConfirmationToken = expiredToken },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(expired.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(expired.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(RequiredToken(expired), Is.Not.EqualTo(expiredToken));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(1));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
        Assert.That(
            await journal.FindStartedFingerprintAsync(request.InvocationId, CancellationToken.None),
            Is.Null);
    }

    [Test]
    public async Task Capacity_is_hard_bounded_and_evicts_oldest_challenge_fail_closed()
    {
        Assert.That(
            () => new InMemoryConfirmationAuthority(capacity: 65),
            Throws.TypeOf<ArgumentOutOfRangeException>());

        using var journal = new InMemoryInvocationJournal();
        var handler = new CountingHandler(OperationRisk.External);
        var authority = new InMemoryConfirmationAuthority(capacity: 2);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal,
                               new MissionEngineOptions { ConfirmationAuthority = authority });
        OperationRequest firstRequest = CreateRequest("{\"slot\":1}");
        OperationResponse first = await engine.ExecuteAsync(firstRequest, CancellationToken.None);
        OperationResponse second = await engine.ExecuteAsync(
            CreateRequest("{\"slot\":2}"),
            CancellationToken.None);
        OperationRequest overflowRequest = CreateRequest("{\"slot\":3}");
        OperationResponse overflow = await engine.ExecuteAsync(
            overflowRequest,
            CancellationToken.None);
        OperationResponse evictedGrant = await engine.ExecuteAsync(
            firstRequest with
            {
                RequestId = NewId(),
                ConfirmationToken = RequiredToken(first),
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(second.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(overflow.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(overflow.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(overflow.Result, Is.Not.Null);
            Assert.That(evictedGrant.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(RequiredToken(evictedGrant), Is.Not.EqualTo(RequiredToken(first)));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(2));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
        Assert.That(
            await journal.FindStartedFingerprintAsync(
                overflowRequest.InvocationId,
                CancellationToken.None),
            Is.Null);

        OperationResponse completed = await engine.ExecuteAsync(
            firstRequest with
            {
                RequestId = NewId(),
                ConfirmationToken = RequiredToken(evictedGrant),
            },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(completed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(1));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task Retryable_outcome_keeps_grant_and_terminal_outcome_revokes_it()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new RetryableOnceExternalHandler();
        var authority = new InMemoryConfirmationAuthority();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal,
                               new MissionEngineOptions { ConfirmationAuthority = authority });
        OperationRequest request = CreateRequest("{\"destination\":\"equipo\"}");
        string token = RequiredToken(await engine.ExecuteAsync(request, CancellationToken.None));
        OperationRequest confirmed = request with
        {
            RequestId = NewId(),
            ConfirmationToken = token,
        };

        OperationResponse retryable = await engine.ExecuteAsync(confirmed, CancellationToken.None);
        string? started = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        OperationResponse terminal = await engine.ExecuteAsync(
            confirmed with { RequestId = NewId() },
            CancellationToken.None);
        ConfirmationBinding binding = ConfirmationBinding.Create(
            request,
            RequestFingerprint.Compute(request));
        ConfirmationAuthorization oldGrantAfterTerminal = authority.AuthorizeOrIssue(binding, token);

        Assert.Multiple(() =>
        {
            Assert.That(retryable.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(retryable.ErrorCode, Is.EqualTo("reconciliation_required"));
            Assert.That(started, Is.EqualTo(RequestFingerprint.Compute(request)));
            Assert.That(terminal.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(2));
            Assert.That(oldGrantAfterTerminal.Status, Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired));
            Assert.That(oldGrantAfterTerminal.Challenge!.Token, Is.Not.EqualTo(token));
        });
    }

    [Test]
    public async Task Restart_requires_a_fresh_grant_for_started_retryable_work()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new RetryableOnceExternalHandler();
        OperationRequest request = CreateRequest("{\"destination\":\"equipo\"}");
        string oldToken;
        using (var firstEngine = new MissionEngine(new OperationRegistry([handler]), journal))
        {
            oldToken = RequiredToken(await firstEngine.ExecuteAsync(request, CancellationToken.None));
            OperationResponse retryable = await firstEngine.ExecuteAsync(
                request with { RequestId = NewId(), ConfirmationToken = oldToken },
                CancellationToken.None);
            Assert.That(retryable.ErrorCode, Is.EqualTo("reconciliation_required"));
        }

        using var restartedEngine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationResponse reconfirm = await restartedEngine.ExecuteAsync(
            request with { RequestId = NewId(), ConfirmationToken = oldToken },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(reconfirm.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(reconfirm.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(RequiredToken(reconfirm), Is.Not.EqualTo(oldToken));
            Assert.That(
                RequiredResult(reconfirm).GetProperty("reconciliationRequired").GetBoolean(),
                Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });

        OperationResponse recovered = await restartedEngine.ExecuteAsync(
            request with
            {
                RequestId = NewId(),
                ConfirmationToken = RequiredToken(reconfirm),
            },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.ExecutionCount, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task Completed_replay_precedes_confirmation_and_fingerprint_ignores_token()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new CountingHandler(OperationRisk.External);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest("{\"destination\":\"equipo\"}");
        string token = RequiredToken(await engine.ExecuteAsync(request, CancellationToken.None));
        OperationRequest confirmed = request with
        {
            RequestId = NewId(),
            ConfirmationToken = token,
        };
        OperationResponse completed = await engine.ExecuteAsync(confirmed, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = NewId(), ConfirmationToken = RandomToken() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(RequestFingerprint.Compute(request), Is.EqualTo(RequestFingerprint.Compute(confirmed)));
            Assert.That(completed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task Forbidden_operation_preserves_terminal_journaled_semantics_without_a_challenge()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new CountingHandler(OperationRisk.Forbidden);
        var authority = new InMemoryConfirmationAuthority();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal,
                               new MissionEngineOptions { ConfirmationAuthority = authority });
        OperationRequest request = CreateRequest("{}");

        OperationResponse first = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);
        string? started = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(first.ErrorCode, Is.EqualTo("operation_forbidden"));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(started, Is.EqualTo(RequestFingerprint.Compute(request)));
            Assert.That(completed, Is.Not.Null);
            Assert.That(authority.ActiveChallengeCount, Is.Zero);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    private static OperationRequest CreateRequest(string json) => new(
        ProtocolTypes.OperationRequest,
        NewId(),
        NewId(),
        NewId(),
        "note.create",
        Parse(json));

    private static string RequiredToken(OperationResponse response) =>
        RequiredResult(response).GetProperty("token").GetString()
        ?? throw new InvalidOperationException("The challenge token is required.");

    private static JsonElement RequiredResult(OperationResponse response) =>
        response.Result
        ?? throw new InvalidOperationException("The challenge result is required.");

    private static byte[] DecodeToken(string token)
    {
        string padded = token + new string('=', (4 - (token.Length % 4)) % 4);
        return Convert.FromBase64String(padded.Replace('-', '+').Replace('_', '/'));
    }

    private static string RandomToken() =>
        Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static JsonElement Parse(string json) => JsonDocument.Parse(json).RootElement.Clone();

    private sealed class CountingHandler(
        OperationRisk risk,
        string operationName = "note.create") : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new(operationName, risk, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success());
        }
    }

    private sealed class RetryableOnceExternalHandler : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.External, "Test external operation.");

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

    private sealed class ManualTimeProvider(DateTimeOffset initialTime) : TimeProvider
    {
        private DateTimeOffset _utcNow = initialTime;

        public override DateTimeOffset GetUtcNow() => _utcNow;

        internal void Advance(TimeSpan interval) => _utcNow = _utcNow.Add(interval);
    }
}
