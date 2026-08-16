namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// Selects the bounded local GPU snapshot requested from Windows.
/// </summary>
public enum GpuStatusScope
{
    Identity = 0,
    Usage = 1,
}

public sealed record GpuAdapterStatus(
    string Name,
    uint VendorId,
    uint DeviceId,
    ulong DedicatedVideoMemoryBytes,
    ulong DedicatedSystemMemoryBytes,
    ulong SharedSystemMemoryLimitBytes,
    double? UsagePercent,
    ulong? DedicatedMemoryUsageBytes,
    ulong? SharedMemoryUsageBytes);

/// <param name="AdapterIndex">
/// Zero-based adapter position in the accompanying snapshot, or <see langword="null"/>
/// when the failure applies to the complete scope.
/// </param>
public sealed record GpuStatusFailure(
    GpuStatusScope Scope,
    string ErrorCode,
    int? AdapterIndex = null);

/// <summary>
/// A point-in-time GPU result. Identity is always required; usage fields are
/// present together only for a successful usage measurement.
/// </summary>
public sealed record GpuStatusSnapshot(
    IReadOnlyList<GpuAdapterStatus> Adapters,
    IReadOnlyList<GpuStatusFailure> Failures);

public interface IGpuStatusProvider
{
    ValueTask<GpuStatusSnapshot> GetStatusAsync(
        GpuStatusScope scope,
        CancellationToken cancellationToken);
}
