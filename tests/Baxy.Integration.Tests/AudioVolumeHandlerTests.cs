using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class AudioVolumeHandlerTests
{
    private const string EndpointHash =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    [Test]
    public void DefinitionIsLowRiskAndReversible()
    {
        var handler = new AudioVolumeHandler(new StubProvider());

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo(AudioOperationIds.Volume));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Reversible));
        });
    }

    [TestCase("null")]
    [TestCase("[]")]
    [TestCase("{}")]
    [TestCase("{\"level\":null}")]
    [TestCase("{\"level\":true}")]
    [TestCase("{\"level\":\"30\"}")]
    [TestCase("{\"level\":30.0}")]
    [TestCase("{\"level\":30.5}")]
    [TestCase("{\"level\":-1}")]
    [TestCase("{\"level\":101}")]
    [TestCase("{\"level\":2147483648}")]
    [TestCase("{\"Level\":30}")]
    [TestCase("{\"level\":30,\"extra\":true}")]
    [TestCase("{\"level\":30,\"level\":31}")]
    public async Task InvalidOrNonExactArgumentsNeverReachProvider(string json)
    {
        var provider = new StubProvider();
        var handler = new AudioVolumeHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            _ = Facts(outcome);
            Assert.That(provider.VolumeCallCount, Is.Zero);
        });
    }

    [Test]
    public async Task DurableIdentityAndExactLevelCrossProviderBoundary()
    {
        OperationInvocation invocation = Invocation("{\"level\":37}");
        var provider = new StubProvider(volume: command => SuccessVolume(
            command.InvocationId,
            command.Level));
        var handler = new AudioVolumeHandler(provider);

        _ = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.LastVolumeCommand?.InvocationId,
                Is.EqualTo(invocation.InvocationId));
            Assert.That(provider.LastVolumeCommand?.Level, Is.EqualTo(37));
            Assert.That(provider.MuteCallCount, Is.Zero);
        });
    }

    [TestCase(0, 0)]
    [TestCase(37, 35)]
    [TestCase(100, 98)]
    public async Task VerifiedPostreadWithinToleranceIsTheOnlySuccess(
        int requested,
        int observed)
    {
        OperationInvocation invocation = Invocation($"{{\"level\":{requested}}}");
        AudioControlReceipt receipt = SuccessVolume(
            invocation.InvocationId,
            requested) with
        {
            Final = new AudioEndpointState(observed, false),
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;
        JsonElement facts = Facts(outcome);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(
                facts.GetProperty("observed").GetProperty("final")
                    .GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(observed));
            Assert.That(facts.GetRawText(), Does.Not.Contain(EndpointHash));
            Assert.That(facts.GetProperty("observed").TryGetProperty("targetId", out _), Is.False);
            Assert.That(result.GetProperty("operation").GetString(),
                Is.EqualTo(AudioOperationIds.Volume));
            Assert.That(result.GetProperty("targetId").GetString(),
                Is.EqualTo(AudioTargetIds.DefaultOutput));
            Assert.That(result.GetProperty("endpointIdHash").GetString(),
                Is.EqualTo(EndpointHash));
            Assert.That(result.GetProperty("baseline").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(55));
            Assert.That(result.GetProperty("final").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(observed));
            Assert.That(result.GetProperty("final").GetProperty("muted").GetBoolean(),
                Is.False);
            Assert.That(result.GetProperty("applied").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("reconciled").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task VerifiedNoOpReportsAlreadyAtRequestedLevel()
    {
        OperationInvocation invocation = Invocation("{\"level\":55}");
        AudioControlReceipt receipt = SuccessVolume(
            invocation.InvocationId,
            55) with
        {
            Baseline = new AudioEndpointState(55, false),
            Final = new AudioEndpointState(55, false),
            Applied = false,
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.That(
            Facts(outcome).GetProperty("observed").GetProperty("applied").GetBoolean(),
            Is.False);
    }

    [Test]
    public async Task ReconciledIntentReportsObservationWithoutClaimingCausality()
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt receipt = SuccessVolume(
            invocation.InvocationId,
            30) with
        {
            Applied = false,
            Reconciled = true,
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.That(
            Facts(outcome).GetProperty("observed").GetProperty("reconciled").GetBoolean(),
            Is.True);
    }

    [TestCase("invocation")]
    [TestCase("operation")]
    [TestCase("target")]
    [TestCase("hash_missing")]
    [TestCase("hash_upper")]
    [TestCase("hash_short")]
    [TestCase("requested_level")]
    [TestCase("requested_state")]
    [TestCase("baseline_missing")]
    [TestCase("final_missing")]
    [TestCase("baseline_range")]
    [TestCase("final_range")]
    [TestCase("flags_both")]
    [TestCase("verified_error")]
    [TestCase("unverified_no_error")]
    [TestCase("outside_tolerance")]
    [TestCase("mute_changed")]
    [TestCase("unreported_effect")]
    public async Task ContradictoryOrUnboundReceiptFailsClosed(string defect)
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt contradicted = ContradictedVolume(
            invocation.InvocationId,
            defect);
        var handler = new AudioVolumeHandler(
            new StubProvider(volume: _ => contradicted));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False, defect);
            Assert.That(outcome.Verified, Is.False, defect);
            Assert.That(outcome.ErrorCode,
                Is.EqualTo(AudioControlErrorCodes.VerificationFailed), defect);
            Assert.That(outcome.Result, Is.Null, defect);
            _ = Facts(outcome);
        });
    }

    [TestCase(AudioControlErrorCodes.InvalidInvocation)]
    [TestCase(AudioControlErrorCodes.InvalidLevel)]
    [TestCase(AudioControlErrorCodes.AudioBusy)]
    [TestCase(AudioControlErrorCodes.NoDefaultOutput)]
    [TestCase(AudioControlErrorCodes.AudioServiceUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointChanged)]
    [TestCase(AudioControlErrorCodes.OperationFailed)]
    [TestCase(AudioControlErrorCodes.VerificationFailed)]
    [TestCase(AudioControlErrorCodes.EffectUncertain)]
    [TestCase(AudioControlErrorCodes.StateCorrupt)]
    [TestCase(AudioControlErrorCodes.StateCapacityReached)]
    [TestCase(AudioControlErrorCodes.StateUnavailable)]
    public async Task KnownProviderFailureRemainsExactAndNeverClaimsSuccess(string errorCode)
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt failure = FailedVolume(
            invocation.InvocationId,
            30,
            errorCode);
        var handler = new AudioVolumeHandler(
            new StubProvider(volume: _ => failure));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(outcome.Result, Is.Null);
            _ = Facts(outcome);
        });
    }

    [Test]
    public async Task EffectUncertainAfterSetDisclosesPossibleChange()
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt receipt = FailedVolume(
            invocation.InvocationId,
            30,
            AudioControlErrorCodes.EffectUncertain) with
        {
            EndpointIdHash = EndpointHash,
            Baseline = new AudioEndpointState(55, false),
            Applied = true,
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Retryable, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.EffectUncertain));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(Facts(outcome).GetProperty("effectUncertain").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task OpenIntentUsesDedicatedRetryableOutcomeUntilItCanReconcile()
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt receipt = FailedVolume(
            invocation.InvocationId,
            30,
            AudioControlErrorCodes.EffectUncertain) with
        {
            EndpointIdHash = EndpointHash,
            Baseline = new AudioEndpointState(55, false),
            Applied = true,
            Retryable = true,
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Retryable, Is.True);
            Assert.That(outcome.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.ReconciliationRequired));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(Facts(outcome).GetProperty("pending").GetBoolean(), Is.True);
        });
    }

    [TestCase(AudioControlErrorCodes.NoDefaultOutput)]
    [TestCase(AudioControlErrorCodes.AudioServiceUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointChanged)]
    public async Task OrphanedIntentWithLostEndpointDisclosesPossiblePriorChange(
        string errorCode)
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt receipt = FailedVolume(
            invocation.InvocationId,
            30,
            errorCode) with
        {
            EndpointIdHash = EndpointHash,
            Baseline = new AudioEndpointState(55, false),
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(Facts(outcome).GetProperty("effectUncertain").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task UnknownProviderErrorIsRejectedAsInvalidEvidence()
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt receipt = FailedVolume(
            invocation.InvocationId,
            30,
            "invented_error");
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.That(outcome.ErrorCode,
            Is.EqualTo(AudioControlErrorCodes.VerificationFailed));
    }

    [Test]
    public async Task TerminalProviderErrorCannotBePromotedToRetryableByItsFlag()
    {
        OperationInvocation invocation = Invocation("{\"level\":30}");
        AudioControlReceipt invalid = FailedVolume(
            invocation.InvocationId,
            30,
            AudioControlErrorCodes.EndpointChanged) with
        {
            EndpointIdHash = EndpointHash,
            Baseline = new AudioEndpointState(55, false),
            Retryable = true,
        };
        var handler = new AudioVolumeHandler(new StubProvider(volume: _ => invalid));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Retryable, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.VerificationFailed));
        });
    }

    [Test]
    public async Task MissionReplayDoesNotIssueASecondAudioMutation()
    {
        var provider = new StubProvider(volume: command => SuccessVolume(
            command.InvocationId,
            command.Level));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new AudioVolumeHandler(provider)]),
            journal);
        OperationRequest request = Request("{\"level\":30}");

        OperationResponse first = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.Result?.GetProperty("final").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(30));
            Assert.That(provider.VolumeCallCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task PendingAudioReentersProviderWithSameInvocationAndThenCompletes()
    {
        int receiptNumber = 0;
        var provider = new StubProvider(volume: command =>
        {
            receiptNumber++;
            return receiptNumber == 1
                ? FailedVolume(
                    command.InvocationId,
                    command.Level,
                    AudioControlErrorCodes.EffectUncertain) with
                {
                    EndpointIdHash = EndpointHash,
                    Baseline = new AudioEndpointState(55, false),
                    Applied = true,
                    Retryable = true,
                }
                : SuccessVolume(command.InvocationId, command.Level) with
                {
                    Applied = false,
                    Reconciled = true,
                };
        });
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new AudioVolumeHandler(provider)]),
            journal);
        OperationRequest request = Request("{\"level\":30}");

        OperationResponse pending = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        CompletedInvocation? beforeRecovery = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        OperationResponse recovered = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pending.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(pending.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.ReconciliationRequired));
            Assert.That(beforeRecovery, Is.Null);
            Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recovered.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(recovered.Replayed, Is.False);
            Assert.That(provider.VolumeCallCount, Is.EqualTo(2));
        });
    }

    [Test]
    public void CancellationIsNotConvertedIntoAnAudioResponse()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var provider = new StubProvider();
        var handler = new AudioVolumeHandler(provider);

        Assert.That(
            async () => await handler.ExecuteAsync(
                Invocation("{\"level\":30}"),
                cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(provider.VolumeCallCount, Is.Zero);
    }

    private static AudioControlReceipt ContradictedVolume(
        string invocationId,
        string defect)
    {
        AudioControlReceipt valid = SuccessVolume(invocationId, 30);
        return defect switch
        {
            "invocation" => valid with { InvocationId = NewId() },
            "operation" => valid with { Operation = AudioOperationIds.Mute },
            "target" => valid with { TargetId = "speakers" },
            "hash_missing" => valid with { EndpointIdHash = null },
            "hash_upper" => valid with { EndpointIdHash = EndpointHash.ToUpperInvariant() },
            "hash_short" => valid with { EndpointIdHash = "abc" },
            "requested_level" => valid with { RequestedLevel = 31 },
            "requested_state" => valid with { RequestedState = false },
            "baseline_missing" => valid with { Baseline = null },
            "final_missing" => valid with { Final = null },
            "baseline_range" => valid with { Baseline = new AudioEndpointState(-1, false) },
            "final_range" => valid with { Final = new AudioEndpointState(101, false) },
            "flags_both" => valid with { Reconciled = true },
            "verified_error" => valid with
            {
                ErrorCode = AudioControlErrorCodes.OperationFailed,
            },
            "unverified_no_error" => valid with { Verified = false },
            "outside_tolerance" => valid with { Final = new AudioEndpointState(33, false) },
            "mute_changed" => valid with { Final = new AudioEndpointState(30, true) },
            "unreported_effect" => valid with
            {
                Applied = false,
                Baseline = new AudioEndpointState(55, false),
                Final = new AudioEndpointState(30, false),
            },
            _ => throw new AssertionException($"Unknown defect: {defect}"),
        };
    }

    private static AudioControlReceipt SuccessVolume(
        string? invocationId = null,
        int level = 30) => new(
        invocationId ?? NewId(),
        AudioOperationIds.Volume,
        AudioTargetIds.DefaultOutput,
        EndpointHash,
        level,
        RequestedState: null,
        new AudioEndpointState(55, false),
        new AudioEndpointState(level, false),
        Applied: true,
        Reconciled: false,
        Verified: true,
        ErrorCode: null);

    private static AudioControlReceipt FailedVolume(
        string invocationId,
        int level,
        string errorCode) => new(
        invocationId,
        AudioOperationIds.Volume,
        AudioTargetIds.DefaultOutput,
        EndpointIdHash: null,
        level,
        RequestedState: null,
        Baseline: null,
        Final: null,
        Applied: false,
        Reconciled: false,
        Verified: false,
        errorCode);

    private static OperationInvocation Invocation(string json) => new(
        NewId(),
        NewId(),
        NewId(),
        Parse(json));

    private static OperationRequest Request(string json) => new(
        ProtocolTypes.OperationRequest,
        NewId(),
        NewId(),
        NewId(),
        AudioOperationIds.Volume,
        Parse(json));

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static JsonElement Facts(OperationOutcome outcome) =>
        OperationOutcomeNarration.AssertFacts(AudioOperationIds.Volume, outcome);

    private sealed class StubProvider : IAudioControlProvider
    {
        private readonly Func<AudioVolumeCommand, AudioControlReceipt> _volume;
        private readonly Func<AudioMuteCommand, AudioControlReceipt> _mute;
        private readonly Func<AudioStatusQuery, AudioStatusReceipt>? _status;
        private AudioControlReceipt? _lastVolume;
        private AudioControlReceipt? _lastMute;

        public StubProvider(
            Func<AudioVolumeCommand, AudioControlReceipt>? volume = null,
            Func<AudioMuteCommand, AudioControlReceipt>? mute = null,
            Func<AudioStatusQuery, AudioStatusReceipt>? status = null)
        {
            _volume = volume ?? (command => SuccessVolume(
                command.InvocationId,
                command.Level));
            _mute = mute ?? (command => SuccessMute(
                command.InvocationId,
                command.State));
            _status = status;
        }

        public int VolumeCallCount { get; private set; }

        public int MuteCallCount { get; private set; }

        public int StatusCallCount { get; private set; }

        public AudioVolumeCommand? LastVolumeCommand { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            StatusCallCount++;
            if (_status is not null)
            {
                return ValueTask.FromResult(_status(query));
            }

            AudioEndpointState state = _lastVolume?.Final
                ?? _lastMute?.Final
                ?? new AudioEndpointState(55, false);
            string? endpointHash = _lastVolume?.EndpointIdHash
                ?? _lastMute?.EndpointIdHash
                ?? EndpointHash;
            return ValueTask.FromResult(new AudioStatusReceipt(
                query.InvocationId,
                AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput,
                endpointHash,
                state,
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetVolumeAsync(
            AudioVolumeCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            VolumeCallCount++;
            LastVolumeCommand = command;
            AudioControlReceipt receipt = _volume(command);
            _lastVolume = receipt;
            return ValueTask.FromResult(receipt);
        }

        public ValueTask<AudioControlReceipt> SetMuteAsync(
            AudioMuteCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            MuteCallCount++;
            AudioControlReceipt receipt = _mute(command);
            _lastMute = receipt;
            return ValueTask.FromResult(receipt);
        }

        private static AudioControlReceipt SuccessMute(
            string invocationId,
            bool state) => new(
            invocationId,
            AudioOperationIds.Mute,
            AudioTargetIds.DefaultOutput,
            EndpointHash,
            RequestedLevel: null,
            state,
            new AudioEndpointState(55, !state),
            new AudioEndpointState(55, state),
            Applied: true,
            Reconciled: false,
            Verified: true,
            ErrorCode: null);
    }
}
