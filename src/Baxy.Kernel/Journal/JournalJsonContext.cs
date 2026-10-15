using System.Text.Json.Serialization;
using Baxy.Contracts;

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
[JsonSerializable(typeof(HonestyCorrectionTrace))]
[JsonSerializable(typeof(JournalAnchorPosition))]
[JsonSerializable(typeof(JournalArchiveLink))]
[JsonSerializable(typeof(JournalAnchorPayload))]
[JsonSerializable(typeof(JournalAnchorEnvelope))]
[JsonSerializable(typeof(JournalRetiredState))]
[JsonSerializable(typeof(JournalRotationIntent))]
[JsonSerializable(typeof(JournalSegmentManifest))]
[JsonSerializable(typeof(JournalSegmentManifestEnvelope))]
[JsonSerializable(typeof(JournalSegmentIndex))]
[JsonSerializable(typeof(JournalSegmentIndexEnvelope))]
internal sealed partial class JournalJsonContext : JsonSerializerContext;
