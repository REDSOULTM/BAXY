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
    int? LogicalProcessorCount = null,
    // Ronda final 8 (regla 3): false when a read stopped before every process (out of memory, the cap).
    bool ObservationComplete = true,
    // Renew al máximo (w8): processes left out because Windows denied reading them (another user's, protected ones).
    int UnmeasuredProcessCount = 0);

public interface IProcessStatusProvider
{
    ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
        ProcessStatusSort sort,
        int limit,
        CancellationToken cancellationToken);
}
