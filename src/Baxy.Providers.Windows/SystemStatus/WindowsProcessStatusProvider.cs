using System.Diagnostics;

namespace Baxy.Providers.Windows.SystemStatus;

public sealed class WindowsProcessStatusProvider : IProcessStatusProvider
{
    private const int MaximumObservedProcesses = 4_096;

    public ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
        ProcessStatusSort sort,
        int limit,
        CancellationToken cancellationToken)
    {
        if (limit is < 1 or > 50)
        {
            throw new ArgumentOutOfRangeException(nameof(limit));
        }

        cancellationToken.ThrowIfCancellationRequested();
        Dictionary<ProcessIdentity, ProcessStatusEntry> first = Observe(
            cancellationToken);
        Dictionary<ProcessIdentity, ProcessStatusEntry> second = Observe(
            cancellationToken);
        IEnumerable<ProcessStatusEntry> stable = second
            .Where(pair => first.ContainsKey(pair.Key))
            .Select(static pair => pair.Value);
        stable = sort switch
        {
            ProcessStatusSort.Cpu => stable
                .OrderByDescending(static item => item.TotalProcessorSeconds)
                .ThenBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            ProcessStatusSort.Memory => stable
                .OrderByDescending(static item => item.WorkingSetBytes)
                .ThenBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            ProcessStatusSort.Name => stable
                .OrderBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            _ => throw new ArgumentOutOfRangeException(nameof(sort)),
        };
        return ValueTask.FromResult(new ProcessStatusSnapshot(
            second.Count,
            stable.Take(limit).ToArray()));
    }

    private static Dictionary<ProcessIdentity, ProcessStatusEntry> Observe(
        CancellationToken cancellationToken)
    {
        Process[] processes = Process.GetProcesses();
        try
        {
            var result = new Dictionary<ProcessIdentity, ProcessStatusEntry>();
            foreach (Process process in processes.Take(MaximumObservedProcesses))
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    string name = process.ProcessName;
                    long created = process.StartTime.ToUniversalTime().Ticks;
                    var identity = new ProcessIdentity(process.Id, created, name);
                    result[identity] = new ProcessStatusEntry(
                        process.Id,
                        created,
                        name,
                        Math.Max(0, process.WorkingSet64),
                        Math.Max(0, process.TotalProcessorTime.TotalSeconds));
                }
                catch (Exception error) when (error is
                    InvalidOperationException or NotSupportedException or
                    System.ComponentModel.Win32Exception)
                {
                    // A process can exit or deny observation between enumeration
                    // and measurement. It is omitted instead of guessed.
                }
                catch (OutOfMemoryException)
                {
                    // Windows can temporarily refuse another process snapshot
                    // while the local model is consuming most committed memory.
                    // Preserve the already observed, verified subset instead of
                    // failing the whole status request or repeatedly allocating.
                    break;
                }
            }
            return result;
        }
        finally
        {
            foreach (Process process in processes)
            {
                process.Dispose();
            }
        }
    }

    private sealed record ProcessIdentity(
        int ProcessId,
        long CreationTimeUtcTicks,
        string Name);
}
