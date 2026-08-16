namespace Baxy.Providers.Windows.Memory;

public enum MemoryKind
{
    Fact,
    Preference,
    Context,
    Rule,
}

public enum MemoryOrigin
{
    Explicit,
}

public enum MemorySensitivity
{
    Normal,
    Personal,
    Sensitive,
    Secret,
}

public enum MemoryRetention
{
    Persistent,
    Session,
    Temporary,
}

public enum MemoryForgetScope
{
    Exact,
    Kind,
    Topic,
    Session,
    All,
}

public sealed record MemoryRecord(
    Guid Id,
    int Revision,
    string Selector,
    string Label,
    string Value,
    MemoryKind Kind,
    MemoryOrigin Origin,
    MemorySensitivity Sensitivity,
    MemoryRetention Retention,
    IReadOnlyList<string> Tags,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? ExpiresAtUtc,
    string? SourceMissionId,
    DateTimeOffset CapturedAtUtc,
    string? SessionId);

public sealed record MemoryConfigureRequest(string InvocationId, bool Enabled);

public sealed record MemoryConfigurationResult(bool Enabled, bool Replayed);

public sealed record MemoryBeginSessionRequest(string SessionId);

public sealed record MemoryBeginSessionResult(int PurgedSessionRecords, bool Changed);

public sealed record MemoryStatusRequest(string? SessionId = null);

public sealed record MemoryStatusResult(
    bool Enabled,
    int TotalRecords,
    int PersistentRecords,
    int SessionRecords,
    int TemporaryRecords,
    int MaximumRecords);

public sealed record MemorySaveRequest(
    string InvocationId,
    string Selector,
    string Label,
    string Value,
    MemoryKind Kind = MemoryKind.Fact,
    MemorySensitivity Sensitivity = MemorySensitivity.Normal,
    MemoryRetention Retention = MemoryRetention.Persistent,
    IReadOnlyList<string>? Tags = null,
    DateTimeOffset? ExpiresAtUtc = null,
    string? SourceMissionId = null,
    DateTimeOffset? CapturedAtUtc = null,
    string? SessionId = null);

public sealed record MemorySaveResult(
    Guid RecordId,
    int Revision,
    string Selector,
    bool Replayed);

public sealed record MemoryRecallRequest(
    string Query,
    string? SessionId = null,
    int MaximumResults = LocalMemoryStore.MaximumRecallResults);

public sealed record MemoryRecallResult(IReadOnlyList<MemoryRecord> Records);

public sealed record MemoryListRequest(
    string? SessionId = null,
    MemoryKind? Kind = null,
    string? Topic = null,
    int MaximumResults = LocalMemoryStore.MaximumListResults);

public sealed record MemoryListResult(IReadOnlyList<MemoryRecord> Records);

public sealed record MemoryCorrectRequest(
    string InvocationId,
    string Selector,
    string NewValue,
    int? ExpectedRevision = null,
    string? ExpectedValue = null,
    string? SourceMissionId = null,
    DateTimeOffset? CapturedAtUtc = null,
    string? SessionId = null);

public sealed record MemoryCorrectResult(
    Guid RecordId,
    int Revision,
    string Selector,
    bool Replayed);

public sealed record MemoryForgetRequest(
    string InvocationId,
    MemoryForgetScope Scope,
    string? Selector = null,
    MemoryKind? Kind = null,
    string? Topic = null,
    string? SessionId = null);

public sealed record MemoryForgetResult(int DeletedCount, bool Replayed);
