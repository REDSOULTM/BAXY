using System.Text.Json.Serialization;

namespace Baxy.Providers.Windows.Memory;

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(MemoryStateDocument))]
[JsonSerializable(typeof(MemoryWatermarkDocument))]
[JsonSerializable(typeof(MemoryIntentDocument))]
internal sealed partial class MemoryJsonContext : JsonSerializerContext;

internal sealed class MemoryStateDocument
{
    public int SchemaVersion { get; set; }

    public long Generation { get; set; }

    public bool Enabled { get; set; }

    public DateTimeOffset MaxObservedUtc { get; set; }

    public string ProtectionMode { get; set; } = string.Empty;

    public string? ActiveSessionId { get; set; }

    public List<MemoryRecordDocument> Records { get; set; } = [];

    public List<MemoryReceiptDocument> Receipts { get; set; } = [];

    public MemoryReceiptDocument? EmergencyPrivacyReceipt { get; set; }
}

internal sealed class MemoryRecordDocument
{
    public Guid Id { get; set; }

    public int Revision { get; set; }

    public string Selector { get; set; } = string.Empty;

    public string Label { get; set; } = string.Empty;

    public string Value { get; set; } = string.Empty;

    public MemoryKind Kind { get; set; }

    public MemoryOrigin Origin { get; set; }

    public MemorySensitivity Sensitivity { get; set; }

    public MemoryRetention Retention { get; set; }

    public List<string> Tags { get; set; } = [];

    public DateTimeOffset CreatedAtUtc { get; set; }

    public DateTimeOffset UpdatedAtUtc { get; set; }

    public DateTimeOffset? ExpiresAtUtc { get; set; }

    public string? SourceMissionId { get; set; }

    public DateTimeOffset CapturedAtUtc { get; set; }

    public string? SessionId { get; set; }
}

internal sealed class MemoryReceiptDocument
{
    public string InvocationId { get; set; } = string.Empty;

    public string RequestDigest { get; set; } = string.Empty;

    public string Operation { get; set; } = string.Empty;

    public bool? Enabled { get; set; }

    public Guid? RecordId { get; set; }

    public int? Revision { get; set; }

    public string? Selector { get; set; }

    public int? DeletedCount { get; set; }
}

internal sealed class MemoryWatermarkDocument
{
    public int SchemaVersion { get; set; }

    public long Generation { get; set; }

    public string SnapshotDigest { get; set; } = string.Empty;

    public string ProtectionMode { get; set; } = string.Empty;
}

internal sealed class MemoryIntentDocument
{
    public int SchemaVersion { get; set; }

    public long Generation { get; set; }

    public string SnapshotDigest { get; set; } = string.Empty;

    public string ProtectionMode { get; set; } = string.Empty;

    public byte[] SnapshotEnvelope { get; set; } = [];
}
