using System.Text.Json.Serialization;

namespace Baxy.Kernel.Journal;

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Metadata,
    WriteIndented = false)]
[JsonSerializable(typeof(JournalEnvelope))]
[JsonSerializable(typeof(JournalUnsignedEnvelope))]
[JsonSerializable(typeof(JournalPayload))]
[JsonSerializable(typeof(JournalAnchorPosition))]
[JsonSerializable(typeof(JournalAnchorPayload))]
[JsonSerializable(typeof(JournalAnchorEnvelope))]
internal sealed partial class JournalJsonContext : JsonSerializerContext;
