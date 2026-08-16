namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// Selects the local, read-only measurements requested from Windows.
/// </summary>
[Flags]
public enum SystemStatusScope
{
    None = 0,
    Cpu = 1 << 0,
    Memory = 1 << 1,
    SystemDisk = 1 << 2,
    Battery = 1 << 3,
    OperatingSystem = 1 << 4,
    Uptime = 1 << 5,
    All = Cpu | Memory | SystemDisk | Battery | OperatingSystem | Uptime,
}

public static class SystemStatusErrorCodes
{
    public const string MeasurementFailed = "measurement_failed";
    public const string InvalidMeasurement = "invalid_measurement";
    public const string Unsupported = "unsupported";
}

public sealed record CpuStatus(
    double UsagePercent,
    int LogicalProcessorCount,
    string? Model);

public sealed record MemoryStatus(
    ulong TotalBytes,
    ulong AvailableBytes);

public sealed record SystemDiskStatus(
    long TotalBytes,
    long AvailableBytes);

public sealed record BatteryStatus(
    bool? IsPresent,
    int? ChargePercent,
    bool? IsCharging,
    bool? IsAcOnline);

public sealed record OperatingSystemStatus(
    int MajorVersion,
    int MinorVersion,
    int BuildNumber,
    string Architecture,
    bool IsWorkstation);

public sealed record SystemStatusFailure(
    SystemStatusScope Scope,
    string ErrorCode);

/// <summary>
/// A point-in-time status result. Every requested scope is represented by either
/// a value or one sanitized failure; unrequested scopes are omitted.
/// </summary>
public sealed record SystemStatusSnapshot(
    CpuStatus? Cpu,
    MemoryStatus? Memory,
    SystemDiskStatus? SystemDisk,
    BatteryStatus? Battery,
    OperatingSystemStatus? OperatingSystem,
    long? UptimeSeconds,
    IReadOnlyList<SystemStatusFailure> Failures);

public interface ISystemStatusProvider
{
    ValueTask<SystemStatusSnapshot> GetStatusAsync(
        SystemStatusScope scope,
        CancellationToken cancellationToken);
}
