using System.Text.Json.Serialization;

namespace Baxy.Contracts;

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    WriteIndented = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(ProtocolHello))]
[JsonSerializable(typeof(ApplicationCatalogSnapshot))]
[JsonSerializable(typeof(GameCatalogSnapshot))]
[JsonSerializable(typeof(GameCatalogEntry))]
[JsonSerializable(typeof(GameCatalogEntry[]))]
[JsonSerializable(typeof(OperationDescriptor))]
[JsonSerializable(typeof(OperationDescriptor[]))]
[JsonSerializable(typeof(OperationRequest))]
[JsonSerializable(typeof(OperationResponse))]
[JsonSerializable(typeof(HonestyCorrectionTrace))]
[JsonSerializable(typeof(ProtocolError))]
public sealed partial class BaxyJsonContext : JsonSerializerContext;
