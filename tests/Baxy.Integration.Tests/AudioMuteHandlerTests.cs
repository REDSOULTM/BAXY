using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class AudioMuteHandlerTests
{
    private const string EndpointHash =
        "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789";

    [Test]
    public void DefinitionIsLowRiskAndReversible()
    {
        var handler = new AudioMuteHandler(new StubProvider());

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo(AudioOperationIds.Mute));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Reversible));
        });
    }

    [TestCase("null")]
    [TestCase("[]")]
    [TestCase("{}")]
    [TestCase("{\"state\":null}")]
    [TestCase("{\"state\":0}")]
    [TestCase("{\"state\":\"true\"}")]
    [TestCase("{\"State\":true}")]
    [TestCase("{\"state\":true,\"extra\":false}")]
    [TestCase("{\"state\":true,\"state\":false}")]
    public async Task InvalidOrNonExactArgumentsNeverReachProvider(string json)
    {
        var provider = new StubProvider();
        var handler = new AudioMuteHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
            Assert.That(provider.MuteCallCount, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task DurableIdentityAndExplicitStateCrossProviderBoundary(bool state)
    {
        OperationInvocation invocation = Invocation(
            state ? "{\"state\":true}" : "{\"state\":false}");
        var provider = new StubProvider(mute: command => SuccessMute(
            command.InvocationId,
            command.State));
        var handler = new AudioMuteHandler(provider);

        _ = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.LastMuteCommand?.InvocationId,
                Is.EqualTo(invocation.InvocationId));
            Assert.That(provider.LastMuteCommand?.State, Is.EqualTo(state));
            Assert.That(provider.VolumeCallCount, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task ExactVerifiedPostreadReturnsNaturalAndStructuredEvidence(
        bool state)
    {
        OperationInvocation invocation = Invocation(
            state ? "{\"state\":true}" : "{\"state\":false}");
        AudioControlReceipt receipt = SuccessMute(invocation.InvocationId, state);
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
            Assert.That(result.GetProperty("operation").GetString(),
                Is.EqualTo(AudioOperationIds.Mute));
            Assert.That(result.GetProperty("endpointIdHash").GetString(),
                Is.EqualTo(EndpointHash));
            Assert.That(result.GetProperty("baseline").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(55));
            Assert.That(result.GetProperty("final").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(55));
            Assert.That(result.GetProperty("final").GetProperty("muted").GetBoolean(),
                Is.EqualTo(state));
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task VerifiedNoOpReportsExistingState(
        bool state)
    {
        OperationInvocation invocation = Invocation(
            state ? "{\"state\":true}" : "{\"state\":false}");
        AudioControlReceipt receipt = SuccessMute(
            invocation.InvocationId,
            state) with
        {
            Baseline = new AudioEndpointState(55, state),
            Final = new AudioEndpointState(55, state),
            Applied = false,
        };
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
        Assert.That(outcome.Result?.GetProperty("final").GetProperty("muted").GetBoolean(), Is.EqualTo(state));
    }

    [TestCase("invocation")]
    [TestCase("operation")]
    [TestCase("target")]
    [TestCase("hash")]
    [TestCase("requested_level")]
    [TestCase("requested_state")]
    [TestCase("missing_postread")]
    [TestCase("mute_mismatch")]
    [TestCase("volume_changed")]
    [TestCase("unreported_effect")]
    [TestCase("flags_both")]
    [TestCase("unknown_error")]
    public async Task ContradictoryReceiptFailsClosed(string defect)
    {
        OperationInvocation invocation = Invocation("{\"state\":true}");
        AudioControlReceipt valid = SuccessMute(invocation.InvocationId, state: true);
        AudioControlReceipt contradicted = defect switch
        {
            "invocation" => valid with { InvocationId = NewId() },
            "operation" => valid with { Operation = AudioOperationIds.Volume },
            "target" => valid with { TargetId = "speaker" },
            "hash" => valid with { EndpointIdHash = new string('A', 64) },
            "requested_level" => valid with { RequestedLevel = 30 },
            "requested_state" => valid with { RequestedState = false },
            "missing_postread" => valid with { Final = null },
            "mute_mismatch" => valid with { Final = new AudioEndpointState(55, false) },
            "volume_changed" => valid with { Final = new AudioEndpointState(54, true) },
            "unreported_effect" => valid with
            {
                Applied = false,
                Baseline = new AudioEndpointState(55, false),
                Final = new AudioEndpointState(55, true),
            },
            "flags_both" => valid with { Reconciled = true },
            "unknown_error" => valid with
            {
                Verified = false,
                ErrorCode = "invented_error",
            },
            _ => throw new AssertionException($"Unknown defect: {defect}"),
        };
        var handler = new AudioMuteHandler(
            new StubProvider(mute: _ => contradicted));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False, defect);
            Assert.That(outcome.ErrorCode,
                Is.EqualTo(AudioControlErrorCodes.VerificationFailed), defect);
            Assert.That(outcome.Result, Is.Null, defect);
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"), defect);
        });
    }

    [Test]
    public async Task KnownPreEffectFailureIsPassedThroughWithoutSuccessClaim()
    {
        OperationInvocation invocation = Invocation("{\"state\":true}");
        AudioControlReceipt failure = new(
            invocation.InvocationId,
            AudioOperationIds.Mute,
            AudioTargetIds.DefaultOutput,
            EndpointIdHash: null,
            RequestedLevel: null,
            RequestedState: true,
            Baseline: null,
            Final: null,
            Applied: false,
            Reconciled: false,
            Verified: false,
            AudioControlErrorCodes.NoDefaultOutput);
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => failure));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.NoDefaultOutput));
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
        });
    }

    [Test]
    public async Task OpenMuteIntentUsesDedicatedRetryableOutcome()
    {
        OperationInvocation invocation = Invocation("{\"state\":true}");
        AudioControlReceipt pending = new(
            invocation.InvocationId,
            AudioOperationIds.Mute,
            AudioTargetIds.DefaultOutput,
            EndpointHash,
            RequestedLevel: null,
            RequestedState: true,
            new AudioEndpointState(55, false),
            Final: null,
            Applied: true,
            Reconciled: false,
            Verified: false,
            AudioControlErrorCodes.EffectUncertain)
        {
            Retryable = true,
        };
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => pending));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Retryable, Is.True);
            Assert.That(outcome.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.ReconciliationRequired));
            Assert.That(Facts(outcome)["pending"]?.GetValue<bool>(), Is.True);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task ReconciledOrphanCanSucceedOnlyWithExactVerifiedPostread(
        bool requested)
    {
        OperationInvocation invocation = Invocation(
            $"{{\"state\":{requested.ToString().ToLowerInvariant()}}}");
        AudioControlReceipt reconciled = SuccessMute(
            invocation.InvocationId,
            requested) with
        {
            Applied = false,
            Reconciled = true,
        };
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => reconciled));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result?.GetProperty("reconciled").GetBoolean(), Is.True);
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
        });
    }

    [Test]
    public async Task OrphanedMuteIntentWithChangedEndpointDisclosesPossiblePriorChange()
    {
        OperationInvocation invocation = Invocation("{\"state\":true}");
        AudioControlReceipt failure = new(
            invocation.InvocationId,
            AudioOperationIds.Mute,
            AudioTargetIds.DefaultOutput,
            EndpointHash,
            RequestedLevel: null,
            RequestedState: true,
            new AudioEndpointState(55, false),
            Final: null,
            Applied: false,
            Reconciled: false,
            Verified: false,
            AudioControlErrorCodes.EndpointChanged);
        var handler = new AudioMuteHandler(new StubProvider(mute: _ => failure));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.EndpointChanged));
            Assert.That(Facts(outcome)["effectUncertain"]?.GetValue<bool>(), Is.True);
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
        });
    }

    [Test]
    public void CancellationIsNotConvertedIntoAnAudioResponse()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var provider = new StubProvider();
        var handler = new AudioMuteHandler(provider);

        Assert.That(
            async () => await handler.ExecuteAsync(
                Invocation("{\"state\":true}"),
                cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(provider.MuteCallCount, Is.Zero);
    }

    private static AudioControlReceipt SuccessMute(
        string? invocationId = null,
        bool state = true) => new(
        invocationId ?? NewId(),
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

    private static OperationInvocation Invocation(string json) => new(
        NewId(),
        NewId(),
        NewId(),
        JsonDocument.Parse(json).RootElement.Clone());

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For(AudioOperationIds.Mute, outcome);

    private static JsonObject Facts(OperationOutcome outcome) =>
        OperationOutcomeNarration.Facts(AudioOperationIds.Mute, outcome);

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

        public AudioMuteCommand? LastMuteCommand { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (_status is not null)
            {
                return ValueTask.FromResult(_status(query));
            }

            AudioEndpointState state = _lastMute?.Final
                ?? _lastVolume?.Final
                ?? new AudioEndpointState(55, false);
            string? endpointHash = _lastMute?.EndpointIdHash
                ?? _lastVolume?.EndpointIdHash
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
            LastMuteCommand = command;
            AudioControlReceipt receipt = _mute(command);
            _lastMute = receipt;
            return ValueTask.FromResult(receipt);
        }

        private static AudioControlReceipt SuccessVolume(
            string invocationId,
            int level) => new(
            invocationId,
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
    }
}
