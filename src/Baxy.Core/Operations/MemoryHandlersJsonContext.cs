using System.Text.Json.Serialization;

namespace Baxy.Core.Operations;

internal sealed record MemoryConfigurationWireResult(
    int Version,
    bool Enabled,
    bool Replayed,
    bool Changed);

internal sealed record MemoryMutationWireResult(
    int Version,
    string RecordId,
    int Revision,
    string Selector,
    bool Replayed,
    bool Changed);

internal sealed record MemoryForgetWireResult(
    int Version,
    int DeletedCount,
    bool Replayed);

internal sealed record MemoryExportWireResult(
    int Version,
    string Path,
    int RecordCount,
    string Sha256,
    bool Replayed);

internal sealed record MemoryRecordWireResult(
    string RecordId,
    int Revision,
    string Selector,
    string Label,
    string Value,
    string Kind,
    string Origin,
    string Sensitivity,
    string Retention,
    IReadOnlyList<string> Tags,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? ExpiresAtUtc,
    string? SourceMissionId,
    DateTimeOffset CapturedAtUtc,
    string? SessionId);

// ExactMatch: only an exact recall's, whether its records are the ones it named (al máximo 11.2).
internal sealed record MemoryRecordsWireResult(
    int Version,
    IReadOnlyList<MemoryRecordWireResult> Records,
    int Count,
    int TotalCount,
    int Offset,
    int Limit,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] bool? ExactMatch = null);

internal sealed record MemoryStatusWireResult(
    int Version,
    bool Enabled,
    int TotalRecords,
    int PersistentRecords,
    int SessionRecords,
    int TemporaryRecords,
    int MaximumRecords);

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(MemoryConfigurationWireResult))]
[JsonSerializable(typeof(MemoryMutationWireResult))]
[JsonSerializable(typeof(MemoryForgetWireResult))]
[JsonSerializable(typeof(MemoryExportWireResult))]
[JsonSerializable(typeof(MemoryRecordWireResult))]
[JsonSerializable(typeof(MemoryRecordWireResult[]))]
[JsonSerializable(typeof(MemoryRecordsWireResult))]
[JsonSerializable(typeof(MemoryStatusWireResult))]
internal sealed partial class MemoryHandlersJsonContext : JsonSerializerContext;
