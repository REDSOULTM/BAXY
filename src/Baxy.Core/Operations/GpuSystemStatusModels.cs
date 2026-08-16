namespace Baxy.Core.Operations;

internal sealed record GpuSystemStatusAdapterResult(
    int AdapterIndex,
    string Name,
    uint VendorId,
    uint DeviceId,
    ulong DedicatedVideoMemoryBytes,
    ulong DedicatedSystemMemoryBytes,
    ulong SharedSystemMemoryLimitBytes,
    double? UsagePercent,
    ulong? DedicatedMemoryUsageBytes,
    ulong? SharedMemoryUsageBytes);

internal sealed record GpuSystemStatusFailureResult(
    string Scope,
    int? AdapterIndex,
    string ErrorCode);

internal sealed record GpuSystemStatusResult(
    string Scope,
    IReadOnlyList<GpuSystemStatusAdapterResult> Adapters,
    IReadOnlyList<GpuSystemStatusFailureResult> Failures);
