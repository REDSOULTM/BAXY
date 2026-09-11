namespace Baxy.Providers.Windows.SystemStatus;

public enum ProcessStatusSort
{
    Cpu,
    Memory,
    Name,
}

public sealed record ProcessStatusEntry(
    int ProcessId,
    long CreationTimeUtcTicks,
    string Name,
    long WorkingSetBytes,
    double TotalProcessorSeconds,
    double? CpuUsagePercent = null,
    double? SampleDurationSeconds = null);

public sealed record ProcessStatusSnapshot(
    int ObservedProcessCount,
    IReadOnlyList<ProcessStatusEntry> Processes,
    int? LogicalProcessorCount = null);

public interface IProcessStatusProvider
{
    ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
        ProcessStatusSort sort,
        int limit,
        CancellationToken cancellationToken);
}
