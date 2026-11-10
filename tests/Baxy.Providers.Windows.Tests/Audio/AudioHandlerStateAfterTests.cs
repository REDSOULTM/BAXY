using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Audio;

/// <summary>
/// Auditoría del Core (w8): a set the provider verified but whose final reading, or the independent read after it, is
/// not what was asked failed bare («could not», without the level it left), while the provider's own unverified set
/// already carried stateAfter. Both now carry it, in audio.volume.adjust's shape, with requestedStateReached (what the
/// mind reads as «releído después»). Still failures, with their code and uncertainty.
/// </summary>
[TestFixture]
public sealed class AudioHandlerStateAfterTests
{
    private static readonly string Hash = new('a', 64);

    // The provider says it set 30 and verified it, but its final reading is 45: the core refuses it and says 45.
    [Test]
    public async Task AVolumeWhoseFinalReadingMissesTheLevelSaysTheLevelItLeft()
    {
        var provider = new ScriptedAudio
        {
            Set = command => Receipt(command.InvocationId, AudioOperationIds.Volume, level: 30, state: null,
                baseline: new(20, false), final: new(45, false)),
        };

        OperationOutcome outcome = await Volume(provider, 30);

        JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.VerificationFailed));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(state.GetProperty("level").GetInt32(), Is.EqualTo(45));
            Assert.That(state.GetProperty("muted").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("requestedLevel").GetInt32(), Is.EqualTo(30));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("authority").GetString(),
                Is.EqualTo("windows_core_audio_output_endpoint_postread"));
        });
    }

    // The provider's final reading holds 30, the independent read right after it says 10 (someone moved it): the read
    // after is the independent one.
    [Test]
    public async Task AVolumeTheIndependentReadContradictsSaysThatRead()
    {
        var provider = new ScriptedAudio
        {
            Set = command => Receipt(command.InvocationId, AudioOperationIds.Volume, level: 30, state: null,
                baseline: new(20, false), final: new(30, false)),
            Status = query => new AudioStatusReceipt(query.InvocationId, AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput, Hash, new(10, false), true, null),
        };

        OperationOutcome outcome = await Volume(provider, 30);

        JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.VerificationFailed));
            Assert.That(state.GetProperty("level").GetInt32(), Is.EqualTo(10));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
        });
    }

    // Contracase: an independent read that failed is no read after; the provider's own final reading is said, and it
    // does show the level asked.
    [Test]
    public async Task AFailedIndependentReadLeavesTheProvidersFinalReading()
    {
        var provider = new ScriptedAudio
        {
            Set = command => Receipt(command.InvocationId, AudioOperationIds.Volume, level: 30, state: null,
                baseline: new(20, false), final: new(30, false)),
            Status = query => new AudioStatusReceipt(query.InvocationId, AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput, null, null, false, AudioControlErrorCodes.AudioBusy),
        };

        OperationOutcome outcome = await Volume(provider, 30);

        JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
        Assert.Multiple(() =>
        {
            Assert.That(state.GetProperty("level").GetInt32(), Is.EqualTo(30));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.True);
        });
    }

    // A mute the provider verified but whose final reading also moved the level: the mute is as asked, the level not.
    [Test]
    public async Task AMuteThatAlsoMovedTheLevelSaysBoth()
    {
        var provider = new ScriptedAudio
        {
            Set = command => Receipt(command.InvocationId, AudioOperationIds.Mute, level: null, state: true,
                baseline: new(40, false), final: new(0, true)),
        };

        OperationOutcome outcome = await new AudioMuteHandler(provider, static (_, _) => throw new InvalidOperationException())
            .ExecuteAsync(Invocation(new { scope = "pc", state = true }), CancellationToken.None);

        JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.VerificationFailed));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(state.GetProperty("level").GetInt32(), Is.Zero);
            Assert.That(state.GetProperty("muted").GetBoolean(), Is.True);
            Assert.That(state.TryGetProperty("requestedLevel", out _), Is.False);
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
        });
    }

    // Contracase: a set that held reads back as asked and succeeds, with no stateAfter.
    [Test]
    public async Task AVolumeThatHeldSucceeds()
    {
        var provider = new ScriptedAudio
        {
            Set = command => Receipt(command.InvocationId, AudioOperationIds.Volume, level: 30, state: null,
                baseline: new(20, false), final: new(30, false)),
        };

        OperationOutcome outcome = await Volume(provider, 30);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("stateAfter", out _), Is.False);
        });
    }

    private static ValueTask<OperationOutcome> Volume(IAudioControlProvider provider, int level) =>
        new AudioVolumeHandler(provider).ExecuteAsync(Invocation(new { level }), CancellationToken.None);

    private static OperationInvocation Invocation(object arguments) =>
        new("request", "mission", "invocation", JsonSerializer.SerializeToElement(arguments));

    private static AudioControlReceipt Receipt(
        string invocationId, string operation, int? level, bool? state, AudioEndpointState baseline,
        AudioEndpointState final) =>
        new(invocationId, operation, AudioTargetIds.DefaultOutput, Hash, level, state, baseline, final,
            Applied: true, Reconciled: false, Verified: true, ErrorCode: null);

    private sealed class ScriptedAudio : IAudioControlProvider
    {
        internal Func<AudioCommandView, AudioControlReceipt> Set { get; init; } = _ => throw new InvalidOperationException();

        // By default the independent read agrees with the set's final reading.
        internal Func<AudioStatusQuery, AudioStatusReceipt>? Status { get; init; }

        private AudioControlReceipt? _last;

        public ValueTask<AudioStatusReceipt> GetStatusAsync(AudioStatusQuery query, CancellationToken cancellationToken) =>
            ValueTask.FromResult(Status?.Invoke(query) ?? new AudioStatusReceipt(query.InvocationId,
                AudioOperationIds.Status, AudioTargetIds.DefaultOutput, Hash, _last!.Final, true, null));

        public ValueTask<AudioControlReceipt> SetVolumeAsync(AudioVolumeCommand command, CancellationToken cancellationToken) =>
            ValueTask.FromResult(_last = Set(new AudioCommandView(command.InvocationId)));

        public ValueTask<AudioControlReceipt> SetMuteAsync(AudioMuteCommand command, CancellationToken cancellationToken) =>
            ValueTask.FromResult(_last = Set(new AudioCommandView(command.InvocationId)));
    }

    private sealed record AudioCommandView(string InvocationId);
}
