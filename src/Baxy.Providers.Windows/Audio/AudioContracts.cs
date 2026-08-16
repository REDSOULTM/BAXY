namespace Baxy.Providers.Windows.Audio;

public static class AudioTargetIds
{
    public const string DefaultOutput = "default_output";
}

public static class AudioOperationIds
{
    public const string Mute = "audio.mute";
    public const string Status = "audio.status";
    public const string Volume = "audio.volume";
}

public static class AudioControlErrorCodes
{
    public const string InvalidInvocation = "invalid_invocation";
    public const string InvalidLevel = "invalid_level";
    public const string AudioBusy = "audio_busy";
    public const string NoDefaultOutput = "no_default_output";
    public const string NoDefaultInput = "no_default_input";
    public const string AudioServiceUnavailable = "audio_service_unavailable";
    public const string EndpointUnavailable = "endpoint_unavailable";
    public const string EndpointChanged = "endpoint_changed";
    public const string OperationFailed = "operation_failed";
    public const string VerificationFailed = "verification_failed";
    public const string EffectUncertain = "effect_uncertain";
    public const string ReconciliationRequired = "audio_reconciliation_required";
    public const string StateCorrupt = "state_corrupt";
    public const string StateCapacityReached = "state_capacity_reached";
    public const string StateUnavailable = "state_unavailable";
}

public sealed record AudioVolumeCommand(string InvocationId, int Level);

public sealed record AudioMuteCommand(string InvocationId, bool State);

public sealed record AudioStatusQuery(string InvocationId);

public sealed record AudioEndpointState(int VolumePercent, bool Muted);

public sealed record AudioStatusReceipt(
    string InvocationId,
    string Operation,
    string TargetId,
    string? EndpointIdHash,
    AudioEndpointState? State,
    bool Verified,
    string? ErrorCode);

/// <summary>
/// Durable, sanitized evidence for one audio mutation. The physical endpoint id is never
/// exposed or persisted; <see cref="EndpointIdHash"/> binds the intent to one endpoint.
/// </summary>
public sealed record AudioControlReceipt(
    string InvocationId,
    string Operation,
    string TargetId,
    string? EndpointIdHash,
    int? RequestedLevel,
    bool? RequestedState,
    AudioEndpointState? Baseline,
    AudioEndpointState? Final,
    bool Applied,
    bool Reconciled,
    bool Verified,
    string? ErrorCode)
{
    /// <summary>
    /// True only while a durable intent still has no terminal receipt and the same
    /// invocation must re-enter the provider to reconcile without issuing a second effect.
    /// Retryable receipts are never persisted as terminal receipts.
    /// </summary>
    public bool Retryable { get; init; }
}

public interface IAudioControlProvider
{
    ValueTask<AudioStatusReceipt> GetStatusAsync(
        AudioStatusQuery query,
        CancellationToken cancellationToken);

    ValueTask<AudioControlReceipt> SetVolumeAsync(
        AudioVolumeCommand command,
        CancellationToken cancellationToken);

    ValueTask<AudioControlReceipt> SetMuteAsync(
        AudioMuteCommand command,
        CancellationToken cancellationToken);
}
