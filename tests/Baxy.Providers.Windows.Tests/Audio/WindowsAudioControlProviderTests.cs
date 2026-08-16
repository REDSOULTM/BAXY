using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Audio;

[TestFixture]
public sealed class WindowsAudioControlProviderTests
{
    [TestCase(0.3749f, 37, false)]
    [TestCase(1f, 100, true)]
    public async Task StatusReadsOneVerifiedSnapshotWithoutMutationOrDurableIntent(
        float scalar,
        int expectedPercent,
        bool muted)
    {
        using TestEnvironment environment = new(volumeScalar: scalar, muted);
        string invocationId = InvocationId();

        AudioStatusReceipt result = await environment.Provider().GetStatusAsync(
            new AudioStatusQuery(invocationId),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.InvocationId, Is.EqualTo(invocationId));
            Assert.That(result.Operation, Is.EqualTo(AudioOperationIds.Status));
            Assert.That(result.TargetId, Is.EqualTo(AudioTargetIds.DefaultOutput));
            Assert.That(result.EndpointIdHash, Has.Length.EqualTo(64));
            Assert.That(result.State,
                Is.EqualTo(new AudioEndpointState(expectedPercent, muted)));
            Assert.That(result.Verified, Is.True);
            Assert.That(result.ErrorCode, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
            Assert.That(File.Exists(environment.StatePath(invocationId)), Is.False);
        });
    }

    [Test]
    public async Task StatusRejectsInvalidInvocationBeforeLockOrEndpointAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);

        AudioStatusReceipt result = await environment.Provider().GetStatusAsync(
            new AudioStatusQuery("not-a-canonical-guid"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode,
                Is.EqualTo(AudioControlErrorCodes.InvalidInvocation));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(result.State, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
        });
    }

    [TestCase(AudioControlErrorCodes.NoDefaultOutput)]
    [TestCase(AudioControlErrorCodes.AudioServiceUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointUnavailable)]
    public async Task StatusSanitizesPlatformReadFailures(string errorCode)
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.OpenErrorCode = errorCode;

        AudioStatusReceipt result = await environment.Provider().GetStatusAsync(
            new AudioStatusQuery(InvocationId()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(result.State, Is.Null);
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task StatusBusyLockFailsWithoutEndpointAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);

        AudioStatusReceipt result = await environment.Provider(
                operationLock: new BusyOperationLock())
            .GetStatusAsync(new AudioStatusQuery(InvocationId()), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(AudioControlErrorCodes.AudioBusy));
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
        });
    }

    [Test]
    public async Task VolumeAcceptsHardwareQuantizationWithinTwoPointsAndPreservesMute()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: true);
        environment.Platform.VolumeQuantizer = _ => 0.24f;

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 25),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.ErrorCode, Is.Null);
            Assert.That(result.Applied, Is.True);
            Assert.That(result.Reconciled, Is.False);
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(24, true)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task VolumeOutsideToleranceFailsVerificationWithoutChangingMuteAgain()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.VolumeQuantizer = _ => 0.27f;

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.VerificationFailed));
            Assert.That(result.Applied, Is.True);
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(27, false)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task MuteUsesExplicitStateAndPreservesExactVolumeScalar(bool requested)
    {
        using TestEnvironment environment = new(volumeScalar: 0.3749f, muted: !requested);

        AudioControlReceipt result = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(InvocationId(), requested),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.RequestedState, Is.EqualTo(requested));
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(37, requested)));
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.3749f));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
        });
    }

    [Test]
    public async Task ExistingTargetIsVerifiedNoOpAfterIndependentPreflight()
    {
        using TestEnvironment environment = new(volumeScalar: 0.30f, muted: false);

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Applied, Is.False);
            Assert.That(result.Reconciled, Is.False);
            Assert.That(result.Baseline, Is.EqualTo(result.Final));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(2));
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
        });
    }

    [Test]
    public async Task AbsoluteVolumeWithinPostreadToleranceStillExecutesSetterWhenNotExact()
    {
        using TestEnvironment environment = new(volumeScalar: 0.05f, muted: false);

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 3),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Applied, Is.True);
            Assert.That(result.Reconciled, Is.False);
            Assert.That(result.Baseline, Is.EqualTo(new AudioEndpointState(5, false)));
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(3, false)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.03f).Within(0.0001f));
        });
    }

    [Test]
    public async Task EndpointSwitchBetweenIntentAndPreflightFailsWithoutSet()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.AddDevice("endpoint-b", 0.20f, muted: false);
        WindowsAudioControlProvider provider = environment.Provider(
            afterIntentPersisted: () => environment.Platform.DefaultEndpointId = "endpoint-b");

        AudioControlReceipt result = await provider.SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EndpointChanged));
            Assert.That(result.Retryable, Is.False);
            Assert.That(result.Final, Is.Null);
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.50f));
            Assert.That(environment.Platform.Device("endpoint-b").VolumeScalar,
                Is.EqualTo(0.20f));
        });
    }

    [Test]
    public async Task NonTargetChangeBetweenIntentAndPreflightFailsWithoutSet()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        WindowsAudioControlProvider provider = environment.Provider(
            afterIntentPersisted: () =>
                environment.Platform.Device("endpoint-a").Muted = true);

        AudioControlReceipt result = await provider.SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EffectUncertain));
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(50, true)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
        });
    }

    [Test]
    public async Task EndpointSwitchAfterSetFailsVerificationWithoutTouchingNewDefault()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.AddDevice("endpoint-b", 0.20f, muted: false);
        environment.Platform.AfterVolumeSet = () =>
            environment.Platform.DefaultEndpointId = "endpoint-b";

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EndpointChanged));
            Assert.That(result.Applied, Is.True);
            Assert.That(result.Final, Is.Null);
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.30f));
            Assert.That(environment.Platform.Device("endpoint-b").VolumeScalar,
                Is.EqualTo(0.20f));
        });
    }

    [Test]
    public async Task VolumeSetterChangingMuteFailsIndependentVerification()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.AfterVolumeSet = () =>
            environment.Platform.Device("endpoint-a").Muted = true;

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), 30),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.VerificationFailed));
            Assert.That(result.Final, Is.EqualTo(new AudioEndpointState(30, true)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task CancellationAfterEffectDoesNotAbandonCriticalReceiptTail()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        using CancellationTokenSource cancellation = new();
        WindowsAudioControlProvider provider = environment.Provider(
            afterEffectIssued: cancellation.Cancel);
        string invocationId = InvocationId();

        AudioControlReceipt result = await provider.SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            cancellation.Token);
        AudioControlReceipt replayed = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(cancellation.IsCancellationRequested, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(replayed, Is.EqualTo(result));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void CrashAfterIntentBeforeSetLeavesIntentAndReplayNeverApplies()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider crashing = environment.Provider(
            afterIntentPersisted: static () => throw new SyntheticCrashException());

        Assert.ThrowsAsync<SyntheticCrashException>(async () =>
            await crashing.SetVolumeAsync(
                new AudioVolumeCommand(invocationId, 30),
                CancellationToken.None));

        AudioControlReceipt replayed = environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(invocationId, 30),
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(replayed.Verified, Is.False);
            Assert.That(replayed.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EffectUncertain));
            Assert.That(replayed.Retryable, Is.False);
            Assert.That(replayed.Applied, Is.False);
            Assert.That(replayed.Reconciled, Is.False);
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.50f));
        });
    }

    [Test]
    public void CrashAfterSetBeforeReceiptReconcilesTargetWithoutSecondSet()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider crashing = environment.Provider(
            afterEffectIssued: static () => throw new SyntheticCrashException());

        Assert.ThrowsAsync<SyntheticCrashException>(async () =>
            await crashing.SetVolumeAsync(
                new AudioVolumeCommand(invocationId, 30),
                CancellationToken.None));

        AudioControlReceipt replayed = environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(invocationId, 30),
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(replayed.Verified, Is.True);
            Assert.That(replayed.Applied, Is.False);
            Assert.That(replayed.Reconciled, Is.True);
            Assert.That(replayed.Final, Is.EqualTo(new AudioEndpointState(30, false)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void CrashAfterSetWithManualTargetDimensionChangeFailsWithoutSecondSetOrRollback()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider crashing = environment.Provider(
            afterEffectIssued: static () => throw new SyntheticCrashException());
        Assert.ThrowsAsync<SyntheticCrashException>(async () =>
            await crashing.SetVolumeAsync(
                new AudioVolumeCommand(invocationId, 30),
                CancellationToken.None));
        environment.Platform.Device("endpoint-a").VolumeScalar = 0.10f;

        AudioControlReceipt replayed = environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(invocationId, 30),
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(replayed.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EffectUncertain));
            Assert.That(replayed.Final, Is.EqualTo(new AudioEndpointState(10, false)));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.10f));
        });
    }

    [Test]
    public void CrashAfterSetWithNonTargetChangeDoesNotInferSuccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider crashing = environment.Provider(
            afterEffectIssued: static () => throw new SyntheticCrashException());
        Assert.ThrowsAsync<SyntheticCrashException>(async () =>
            await crashing.SetVolumeAsync(
                new AudioVolumeCommand(invocationId, 30),
                CancellationToken.None));
        environment.Platform.Device("endpoint-a").Muted = true;

        AudioControlReceipt replayed = environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(invocationId, 30),
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(replayed.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EffectUncertain));
            Assert.That(replayed.Reconciled, Is.False);
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void OrphanedIntentBoundToAnotherDefaultEndpointNeverSetsEitherEndpoint()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.AddDevice("endpoint-b", 0.20f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider crashing = environment.Provider(
            afterIntentPersisted: static () => throw new SyntheticCrashException());
        Assert.ThrowsAsync<SyntheticCrashException>(async () =>
            await crashing.SetMuteAsync(
                new AudioMuteCommand(invocationId, true),
                CancellationToken.None));
        environment.Platform.DefaultEndpointId = "endpoint-b";

        AudioControlReceipt replayed = environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(replayed.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EndpointChanged));
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
            Assert.That(environment.Platform.Device("endpoint-a").Muted, Is.False);
            Assert.That(environment.Platform.Device("endpoint-b").Muted, Is.False);
        });
    }

    [Test]
    public async Task CompletedReceiptReplaysWithoutOperatingSystemAccessOrSecondSet()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        WindowsAudioControlProvider provider = environment.Provider();
        AudioMuteCommand command = new(invocationId, true);
        AudioControlReceipt first = await provider.SetMuteAsync(command, CancellationToken.None);
        int opens = environment.Platform.OpenCalls;

        AudioControlReceipt replayed = await environment.Provider().SetMuteAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(replayed, Is.EqualTo(first));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task CorruptReceiptFailsClosedWithoutOperatingSystemAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        AudioMuteCommand command = new(invocationId, true);
        _ = await environment.Provider().SetMuteAsync(command, CancellationToken.None);
        int opens = environment.Platform.OpenCalls;
        string path = environment.StatePath(invocationId);
        string json = File.ReadAllText(path);
        int checksumIndex = json.IndexOf("\"checksum\":\"", StringComparison.Ordinal)
            + "\"checksum\":\"".Length;
        char[] corrupted = json.ToCharArray();
        corrupted[checksumIndex] = corrupted[checksumIndex] == '0' ? '1' : '0';
        File.WriteAllText(path, new string(corrupted));

        AudioControlReceipt replayed = await environment.Provider().SetMuteAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(replayed.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.StateCorrupt));
            Assert.That(replayed.Baseline, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void RetryableReceiptCannotBePersistedAsTerminalState()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        var store = new AudioInvocationStore(environment.StateDirectory);
        var intent = new AudioInvocationState(
            invocationId,
            AudioOperationIds.Volume,
            AudioTargetIds.DefaultOutput,
            new string('a', 64),
            RequestedLevel: 30,
            RequestedState: null,
            new AudioEndpointState(50, false),
            BaselineVolumeScalar: 0.50f,
            DateTimeOffset.UtcNow.UtcTicks,
            Receipt: null,
            FinalVolumeScalar: null);
        store.Save(intent);
        var retryable = new AudioControlReceipt(
            invocationId,
            AudioOperationIds.Volume,
            AudioTargetIds.DefaultOutput,
            intent.EndpointIdHash,
            RequestedLevel: 30,
            RequestedState: null,
            intent.Baseline,
            Final: null,
            Applied: true,
            Reconciled: false,
            Verified: false,
            AudioControlErrorCodes.EffectUncertain)
        {
            Retryable = true,
        };

        Assert.That(
            () => store.Save(intent with { Receipt = retryable }),
            Throws.TypeOf<AudioStateCorruptException>());
        AudioInvocationState? preserved = store.Load(invocationId);
        Assert.That(preserved, Is.Not.Null);
        Assert.That(preserved!.Receipt, Is.Null);
    }

    [TestCase("null-state")]
    [TestCase("null-evidence")]
    public async Task NullOrStructurallyCorruptStateFailsClosedWithoutPlatformAccess(
        string corruption)
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        string json = corruption == "null-state"
            ? "{\"version\":1,\"state\":null,\"checksum\":\"00\"}"
            : $"{{\"version\":1,\"state\":{{\"invocationId\":\"{invocationId}\",\"operation\":\"audio.mute\",\"targetId\":\"default_output\",\"endpointIdHash\":null,\"requestedLevel\":null,\"requestedState\":true,\"baseline\":null,\"baselineVolumeScalar\":0.5,\"intentCreatedUtcTicks\":1,\"receipt\":null,\"finalVolumeScalar\":null}},\"checksum\":\"00\"}}";
        File.WriteAllText(environment.StatePath(invocationId), json);

        AudioControlReceipt result = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.StateCorrupt));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task DurableStateContainsOnlyEndpointHashNotRawDeviceId()
    {
        const string rawEndpointId = "private-physical-endpoint-id";
        using TestEnvironment environment = new(
            volumeScalar: 0.50f,
            muted: false,
            endpointId: rawEndpointId);
        string invocationId = InvocationId();

        AudioControlReceipt result = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            CancellationToken.None);
        string json = File.ReadAllText(environment.StatePath(invocationId));

        Assert.Multiple(() =>
        {
            Assert.That(result.EndpointIdHash, Has.Length.EqualTo(64));
            Assert.That(json, Does.Contain(result.EndpointIdHash!));
            Assert.That(json, Does.Not.Contain(rawEndpointId));
        });
    }

    [TestCase(-1)]
    [TestCase(101)]
    public async Task InvalidLevelIsRejectedBeforeStateOrEndpointAccess(int level)
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);

        AudioControlReceipt result = await environment.Provider().SetVolumeAsync(
            new AudioVolumeCommand(InvocationId(), level),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.InvalidLevel));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
        });
    }

    [Test]
    public async Task InvalidInvocationIsRejectedBeforeStateOrEndpointAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);

        AudioControlReceipt result = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand("not-a-canonical-guid", true),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.InvalidInvocation));
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public void CancellationBeforeIntentDoesNotCreateStateOrAccessEndpoint()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        using CancellationTokenSource cancellation = new();
        cancellation.Cancel();

        Assert.ThrowsAsync<OperationCanceledException>(async () =>
            await environment.Provider().SetMuteAsync(
                new AudioMuteCommand(invocationId, true),
                cancellation.Token));

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(environment.StatePath(invocationId)), Is.False);
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [TestCase(AudioControlErrorCodes.NoDefaultOutput)]
    [TestCase(AudioControlErrorCodes.AudioServiceUnavailable)]
    [TestCase(AudioControlErrorCodes.EndpointUnavailable)]
    public async Task PlatformOpenFailuresAreSanitizedBeforeIntent(
        string platformErrorCode)
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.OpenErrorCode = platformErrorCode;

        AudioControlReceipt result = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(InvocationId(), true),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(platformErrorCode));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(result.Baseline, Is.Null);
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task SetterFailureIsPostReadPersistedAndNeverRetried()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.VolumeSetErrorCode =
            AudioControlErrorCodes.OperationFailed;
        string invocationId = InvocationId();
        AudioVolumeCommand command = new(invocationId, 30);

        AudioControlReceipt first = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);
        int opens = environment.Platform.OpenCalls;
        AudioControlReceipt replayed = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.OperationFailed));
            Assert.That(first.Applied, Is.True);
            Assert.That(first.Final, Is.EqualTo(new AudioEndpointState(50, false)));
            Assert.That(replayed, Is.EqualTo(first));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VolumeSetterErrorWithVerifiedTargetIsObservedAsReconciledAndNeverRetried()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.AfterVolumeSet = static () =>
            throw new AudioPlatformException(AudioControlErrorCodes.OperationFailed);
        string invocationId = InvocationId();
        AudioVolumeCommand command = new(invocationId, 30);

        AudioControlReceipt first = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);
        int opens = environment.Platform.OpenCalls;
        AudioControlReceipt replayed = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(first.ErrorCode, Is.Null);
            Assert.That(first.Applied, Is.False);
            Assert.That(first.Reconciled, Is.True);
            Assert.That(first.Retryable, Is.False);
            Assert.That(first.Baseline, Is.EqualTo(new AudioEndpointState(50, false)));
            Assert.That(first.Final, Is.EqualTo(new AudioEndpointState(30, false)));
            Assert.That(replayed, Is.EqualTo(first));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task MuteSetterErrorWithVerifiedTargetIsObservedAsReconciledAndNeverRetried(
        bool requested)
    {
        using TestEnvironment environment = new(volumeScalar: 0.3749f, muted: !requested);
        environment.Platform.AfterMuteSet = static () =>
            throw new AudioPlatformException(AudioControlErrorCodes.OperationFailed);
        string invocationId = InvocationId();
        AudioMuteCommand command = new(invocationId, requested);

        AudioControlReceipt first = await environment.Provider().SetMuteAsync(
            command,
            CancellationToken.None);
        int opens = environment.Platform.OpenCalls;
        AudioControlReceipt replayed = await environment.Provider().SetMuteAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(first.ErrorCode, Is.Null);
            Assert.That(first.Applied, Is.False);
            Assert.That(first.Reconciled, Is.True);
            Assert.That(first.Retryable, Is.False);
            Assert.That(first.Baseline, Is.EqualTo(new AudioEndpointState(37, !requested)));
            Assert.That(first.Final, Is.EqualTo(new AudioEndpointState(37, requested)));
            Assert.That(replayed, Is.EqualTo(first));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetVolumeCalls, Is.Zero);
            Assert.That(environment.Platform.Device("endpoint-a").VolumeScalar,
                Is.EqualTo(0.3749f));
        });
    }

    [Test]
    public async Task PostReadFailureLeavesIntentForConservativeReconciliation()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.FailOpenOnCall = 3;
        environment.Platform.OpenErrorCode =
            AudioControlErrorCodes.AudioServiceUnavailable;
        string invocationId = InvocationId();
        AudioVolumeCommand command = new(invocationId, 30);

        AudioControlReceipt uncertain = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);
        AudioInvocationState? pendingIntent = new AudioInvocationStore(environment.StateDirectory)
            .Load(invocationId);
        environment.Platform.OpenErrorCode = null;
        AudioControlReceipt reconciled = await environment.Provider().SetVolumeAsync(
            command,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(uncertain.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.EffectUncertain));
            Assert.That(uncertain.Applied, Is.True);
            Assert.That(uncertain.Retryable, Is.True);
            Assert.That(pendingIntent, Is.Not.Null);
            Assert.That(pendingIntent!.Receipt, Is.Null);
            Assert.That(reconciled.Verified, Is.True);
            Assert.That(reconciled.Reconciled, Is.True);
            Assert.That(reconciled.Retryable, Is.False);
            Assert.That(reconciled.Applied, Is.False);
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task SameInvocationWithDifferentTargetFailsClosedWithoutEndpointAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        string invocationId = InvocationId();
        _ = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, true),
            CancellationToken.None);
        int opens = environment.Platform.OpenCalls;

        AudioControlReceipt conflict = await environment.Provider().SetMuteAsync(
            new AudioMuteCommand(invocationId, false),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(conflict.ErrorCode, Is.EqualTo(
                AudioControlErrorCodes.StateCorrupt));
            Assert.That(environment.Platform.OpenCalls, Is.EqualTo(opens));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NamedLockSerializesConcurrentMutations()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        environment.Platform.BlockFirstSet = true;
        string lockName = $@"Local\BAXY.Audio.Tests.{Guid.NewGuid():N}";
        WindowsAudioControlProvider firstProvider = environment.Provider(
            operationLock: new NamedAudioOperationLock(lockName));
        WindowsAudioControlProvider secondProvider = environment.Provider(
            operationLock: new NamedAudioOperationLock(lockName));

        Task<AudioControlReceipt> first = Task.Run(async () =>
            await firstProvider.SetVolumeAsync(
                new AudioVolumeCommand(InvocationId(), 30),
                CancellationToken.None));
        Assert.That(environment.Platform.FirstSetEntered.Wait(TimeSpan.FromSeconds(3)), Is.True);
        Task<AudioControlReceipt> second = Task.Run(async () =>
            await secondProvider.SetMuteAsync(
                new AudioMuteCommand(InvocationId(), true),
                CancellationToken.None));
        await Task.Delay(100);
        Assert.That(environment.Platform.SetMuteCalls, Is.Zero);
        environment.Platform.ReleaseFirstSet.Set();

        AudioControlReceipt[] receipts = await Task.WhenAll(first, second);

        Assert.Multiple(() =>
        {
            Assert.That(receipts, Has.All.Property(nameof(AudioControlReceipt.Verified)).True);
            Assert.That(environment.Platform.MaximumConcurrentSets, Is.EqualTo(1));
            Assert.That(environment.Platform.SetVolumeCalls, Is.EqualTo(1));
            Assert.That(environment.Platform.SetMuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task BusyLockReturnsSanitizedFailureWithoutEndpointAccess()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);
        WindowsAudioControlProvider provider = environment.Provider(
            operationLock: new BusyOperationLock());

        AudioControlReceipt result = await provider.SetMuteAsync(
            new AudioMuteCommand(InvocationId(), true),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(AudioControlErrorCodes.AudioBusy));
            Assert.That(result.EndpointIdHash, Is.Null);
            Assert.That(environment.Platform.OpenCalls, Is.Zero);
        });
    }

    [Test]
    public void AlternateDataStreamStateRootIsRejected()
    {
        using TestEnvironment environment = new(volumeScalar: 0.50f, muted: false);

        Assert.Throws<IOException>(() =>
            _ = new AudioInvocationStore($"{environment.StateDirectory}:stream"));
    }

    private static string InvocationId() => Guid.NewGuid().ToString("D");

    private sealed class TestEnvironment : IDisposable
    {
        private readonly string _root = Path.Combine(
            Path.GetTempPath(),
            $"baxy-audio-{Guid.NewGuid():N}");

        public TestEnvironment(
            float volumeScalar,
            bool muted,
            string endpointId = "endpoint-a")
        {
            StateDirectory = Path.Combine(_root, "state");
            Directory.CreateDirectory(StateDirectory);
            Platform = new FakeAudioPlatform(endpointId, volumeScalar, muted);
        }

        public string StateDirectory { get; }

        public FakeAudioPlatform Platform { get; }

        public WindowsAudioControlProvider Provider(
            Action? afterIntentPersisted = null,
            Action? afterEffectIssued = null,
            IAudioOperationLock? operationLock = null) => new(
                Platform,
                new AudioInvocationStore(StateDirectory),
                operationLock ?? new ImmediateOperationLock(),
                afterIntentPersisted,
                afterEffectIssued);

        public string StatePath(string invocationId) =>
            new AudioInvocationStore(StateDirectory).GetStatePath(invocationId);

        public void Dispose()
        {
            Platform.ReleaseFirstSet.Set();
            try
            {
                Directory.Delete(_root, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    private sealed class ImmediateOperationLock : IAudioOperationLock
    {
        public IDisposable TryAcquire(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return new EmptyLease();
        }
    }

    private sealed class BusyOperationLock : IAudioOperationLock
    {
        public IDisposable? TryAcquire(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return null;
        }
    }

    private sealed class EmptyLease : IDisposable
    {
        public void Dispose()
        {
        }
    }

    private sealed class FakeAudioPlatform : IWindowsAudioPlatform
    {
        private readonly Dictionary<string, FakeDevice> _devices =
            new(StringComparer.Ordinal);
        private int _activeSets;
        private int _maximumConcurrentSets;
        private int _setSequence;
        private int _openCalls;
        private int _setVolumeCalls;
        private int _setMuteCalls;

        public FakeAudioPlatform(
            string endpointId,
            float volumeScalar,
            bool muted)
        {
            AddDevice(endpointId, volumeScalar, muted);
            DefaultEndpointId = endpointId;
        }

        public DateTimeOffset UtcNow { get; } =
            new(2026, 7, 15, 12, 0, 0, TimeSpan.Zero);

        public string DefaultEndpointId { get; set; }

        public Func<float, float> VolumeQuantizer { get; set; } = static value => value;

        public Action? AfterVolumeSet { get; set; }

        public Action? AfterMuteSet { get; set; }

        public string? OpenErrorCode { get; set; }

        public int? FailOpenOnCall { get; set; }

        public string? VolumeSetErrorCode { get; set; }

        public bool BlockFirstSet { get; set; }

        public ManualResetEventSlim FirstSetEntered { get; } = new(false);

        public ManualResetEventSlim ReleaseFirstSet { get; } = new(false);

        public int OpenCalls => Volatile.Read(ref _openCalls);

        public int SetVolumeCalls => Volatile.Read(ref _setVolumeCalls);

        public int SetMuteCalls => Volatile.Read(ref _setMuteCalls);

        public int MaximumConcurrentSets => Volatile.Read(ref _maximumConcurrentSets);

        public void AddDevice(string id, float volumeScalar, bool muted) =>
            _devices.Add(id, new FakeDevice(volumeScalar, muted));

        public FakeDevice Device(string id) => _devices[id];

        public IWindowsAudioEndpoint OpenDefaultOutput()
        {
            int openCall = Interlocked.Increment(ref _openCalls);
            if (OpenErrorCode is not null
                && (FailOpenOnCall is null || FailOpenOnCall == openCall))
            {
                throw new AudioPlatformException(OpenErrorCode);
            }

            string id = DefaultEndpointId;
            if (!_devices.TryGetValue(id, out FakeDevice? device))
            {
                throw new AudioPlatformException(AudioControlErrorCodes.NoDefaultOutput);
            }

            return new FakeEndpoint(this, id, device);
        }

        private void EnterSet()
        {
            int active = Interlocked.Increment(ref _activeSets);
            int observed;
            while (active > (observed = Volatile.Read(ref _maximumConcurrentSets)))
            {
                if (Interlocked.CompareExchange(
                        ref _maximumConcurrentSets,
                        active,
                        observed) == observed)
                {
                    break;
                }
            }

            int sequence = Interlocked.Increment(ref _setSequence);
            if (BlockFirstSet && sequence == 1)
            {
                FirstSetEntered.Set();
                if (!ReleaseFirstSet.Wait(TimeSpan.FromSeconds(5)))
                {
                    throw new TimeoutException("Synthetic set gate timed out.");
                }
            }
        }

        private void ExitSet() => Interlocked.Decrement(ref _activeSets);

        private sealed class FakeEndpoint(
            FakeAudioPlatform owner,
            string endpointId,
            FakeDevice device) : IWindowsAudioEndpoint
        {
            private bool _disposed;

            public string EndpointId { get; } = endpointId;

            public float ReadVolumeScalar()
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                return device.VolumeScalar;
            }

            public bool ReadMuted()
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                return device.Muted;
            }

            public void SetVolumeScalar(float scalar, Guid eventContext)
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                Interlocked.Increment(ref owner._setVolumeCalls);
                owner.EnterSet();
                try
                {
                    if (owner.VolumeSetErrorCode is not null)
                    {
                        throw new AudioPlatformException(owner.VolumeSetErrorCode);
                    }

                    device.VolumeScalar = owner.VolumeQuantizer(scalar);
                    owner.AfterVolumeSet?.Invoke();
                }
                finally
                {
                    owner.ExitSet();
                }
            }

            public void SetMuted(bool muted, Guid eventContext)
            {
                ObjectDisposedException.ThrowIf(_disposed, this);
                Interlocked.Increment(ref owner._setMuteCalls);
                owner.EnterSet();
                try
                {
                    device.Muted = muted;
                    owner.AfterMuteSet?.Invoke();
                }
                finally
                {
                    owner.ExitSet();
                }
            }

            public void Dispose() => _disposed = true;
        }
    }

    private sealed class FakeDevice(float volumeScalar, bool muted)
    {
        public float VolumeScalar { get; set; } = volumeScalar;

        public bool Muted { get; set; } = muted;
    }

    private sealed class SyntheticCrashException : Exception;
}
