using System.Text.Json.Serialization;

namespace Baxy.Core.Operations;

internal sealed class EmptyArguments;

internal sealed record CreateNoteArguments(
    [property: JsonRequired] string Title,
    [property: JsonRequired] string Content);

internal sealed record NoteSelectorArguments(
    string? NoteId,
    string? Title,
    string? ExpectedTitle,
    long? ExpectedRevision,
    bool? ExpectedIsTrashed);

internal sealed record ListNotesArguments(
    string? Scope,
    int? Limit,
    int? Offset);

internal sealed record OpenApplicationArguments(
    [property: JsonRequired] string AppId);

internal sealed record OpenApplicationResult(
    string AppId,
    string DisplayName,
    bool AlreadyRunning,
    int ProcessId,
    long WindowHandle);

internal sealed record AudioVolumeArguments(
    [property: JsonRequired] int Level);

internal sealed record AudioMuteArguments(
    [property: JsonRequired] bool State);

internal sealed record AudioEndpointStateResult(
    int VolumePercent,
    bool Muted);

internal sealed record AudioControlResult(
    string Operation,
    string TargetId,
    string EndpointIdHash,
    AudioEndpointStateResult Baseline,
    AudioEndpointStateResult Final,
    bool Applied,
    bool Reconciled);

internal sealed record AudioStatusResult(
    string Operation,
    string TargetId,
    string EndpointIdHash,
    AudioEndpointStateResult State)
{
    public string? EndpointName { get; init; }
}

internal sealed record NoteResult(
    string NoteId,
    string Title,
    string Content,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteSummaryResult(
    string NoteId,
    string Title,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteAmbiguityCandidateResult(
    string NoteId,
    string ContentPreview,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteAmbiguityResult(
    IReadOnlyList<NoteAmbiguityCandidateResult> Candidates);

internal sealed record NoteListResult(
    IReadOnlyList<NoteSummaryResult> Notes,
    int Count,
    int TotalCount,
    string Scope,
    int Limit,
    int Offset,
    int? NextOffset);

internal sealed record AppStatusResult(
    bool Ready,
    string Protocol,
    IReadOnlyList<string> Operations);

internal sealed record SystemStatusArguments(string? Scope);

internal sealed record ProcessListArguments(string? Sort, int? Limit);

internal sealed record ProcessListItemResult(
    int ProcessId,
    string Name,
    long WorkingSetBytes,
    double TotalProcessorSeconds,
    double? CpuUsagePercent,
    double? SampleDurationSeconds);

internal sealed record ProcessListResult(
    int Version,
    string Sort,
    int ObservedProcessCount,
    IReadOnlyList<ProcessListItemResult> Processes,
    int ReturnedProcessCount,
    string ObservationScope,
    int? LogicalProcessorCount);

internal sealed record SystemStatusCpuResult(
    double UsagePercent,
    int LogicalProcessorCount,
    string? Model,
    int? PhysicalCoreCount);

internal sealed record SystemStatusMemoryResult(
    ulong TotalBytes,
    ulong AvailableBytes,
    ulong? InstalledBytes);

internal sealed record SystemStatusDiskResult(
    long TotalBytes,
    long AvailableBytes);

internal sealed record SystemStatusBatteryResult(
    bool? IsPresent,
    int? ChargePercent,
    bool? IsCharging,
    bool? IsAcOnline);

internal sealed record SystemStatusOperatingSystemResult(
    int MajorVersion,
    int MinorVersion,
    int BuildNumber,
    string Architecture,
    bool IsWorkstation,
    string Caption);

internal sealed record SystemStatusFailureResult(
    string Scope,
    string ErrorCode);

internal sealed record SystemStatusResult(
    string Scope,
    SystemStatusCpuResult? Cpu,
    SystemStatusMemoryResult? Memory,
    SystemStatusDiskResult? Disk,
    SystemStatusBatteryResult? Battery,
    SystemStatusOperatingSystemResult? Os,
    long? UptimeSeconds,
    IReadOnlyList<SystemStatusFailureResult> Failures);
