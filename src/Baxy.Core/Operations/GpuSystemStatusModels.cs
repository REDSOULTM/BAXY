using Baxy.Providers.Windows.Infrastructure;

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
    ulong? SharedMemoryUsageBytes)
{
    // Holdout v4 (falsedad, «69 % de CPU» for 0.69 %): the readings with their unit (ReadingUnits).
    public string? Usage => ReadingUnits.Percent(UsagePercent);

    public string DedicatedVideoMemory => ReadingUnits.Size(DedicatedVideoMemoryBytes);

    public string? DedicatedMemoryUsage => ReadingUnits.Size(DedicatedMemoryUsageBytes);

    public string? SharedMemoryUsage => ReadingUnits.Size(SharedMemoryUsageBytes);
}

internal sealed record GpuSystemStatusFailureResult(
    string Scope,
    int? AdapterIndex,
    string ErrorCode);

internal sealed record GpuSystemStatusResult(
    string Scope,
    IReadOnlyList<GpuSystemStatusAdapterResult> Adapters,
    IReadOnlyList<GpuSystemStatusFailureResult> Failures);
