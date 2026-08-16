using System.Text.Json.Serialization;

namespace Baxy.Providers.Windows.Notes;

[JsonSourceGenerationOptions(
    GenerationMode = JsonSourceGenerationMode.Default,
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    WriteIndented = true)]
[JsonSerializable(typeof(NoteDocument))]
internal sealed partial class NotesJsonContext : JsonSerializerContext
{
}

internal sealed class NoteDocument
{
    public int SchemaVersion { get; init; }

    public Guid Id { get; init; }

    public string Title { get; init; } = string.Empty;

    public string Content { get; init; } = string.Empty;

    public DateTimeOffset CreatedAtUtc { get; init; }

    public DateTimeOffset UpdatedAtUtc { get; init; }

    public DateTimeOffset? TrashedAtUtc { get; init; }

    public long Revision { get; init; }

    public string? IdempotencyKey { get; init; }

    public string IntegritySha256 { get; init; } = string.Empty;
}
