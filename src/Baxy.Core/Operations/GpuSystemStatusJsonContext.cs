using System.Text.Json.Serialization;

namespace Baxy.Core.Operations;

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(GpuSystemStatusAdapterResult))]
[JsonSerializable(typeof(GpuSystemStatusAdapterResult[]))]
[JsonSerializable(typeof(GpuSystemStatusFailureResult))]
[JsonSerializable(typeof(GpuSystemStatusFailureResult[]))]
[JsonSerializable(typeof(GpuSystemStatusResult))]
internal sealed partial class GpuSystemStatusJsonContext : JsonSerializerContext;
