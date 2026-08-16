using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

internal sealed record FieldMetricSnapshot(
    double Cpu,
    double Mem,
    double MemUsedGb,
    double Gpu,
    double Net,
    double Dsk,
    double Tmp,
    string Uptime,
    IReadOnlyDictionary<string, bool> Placeholder);

internal sealed record FieldHardwareSnapshot(
    string Cpu,
    int CpuCores,
    string Mem,
    double MemTotalGb,
    string Gpu,
    double GpuVramGb);

internal sealed class FieldTelemetrySampler : IAsyncDisposable
{
    private static readonly TimeSpan CacheLifetime = TimeSpan.FromMilliseconds(900);
    private readonly WindowsSystemStatusProvider _system = new();
    private readonly WindowsGpuStatusProvider _gpu = new();
    private readonly SemaphoreSlim _sampleLock = new(1, 1);
    private DateTimeOffset _cachedAt;
    private FieldMetricSnapshot? _cachedMetrics;
    private FieldHardwareSnapshot? _cachedHardware;
    private bool _disposed;

    internal async Task<FieldMetricSnapshot> SampleAsync(CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_cachedMetrics is not null
            && DateTimeOffset.UtcNow - _cachedAt <= CacheLifetime)
        {
            return _cachedMetrics;
        }

        await _sampleLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_cachedMetrics is not null
                && DateTimeOffset.UtcNow - _cachedAt <= CacheLifetime)
            {
                return _cachedMetrics;
            }

            Task<SystemStatusSnapshot> systemTask = _system
                .GetStatusAsync(SystemStatusScope.All, cancellationToken)
                .AsTask();
            Task<GpuStatusSnapshot> gpuTask = _gpu
                .GetStatusAsync(GpuStatusScope.Usage, cancellationToken)
                .AsTask();
            await Task.WhenAll(systemTask, gpuTask).ConfigureAwait(false);

            SystemStatusSnapshot system = await systemTask.ConfigureAwait(false);
            GpuStatusSnapshot gpu = await gpuTask.ConfigureAwait(false);
            _cachedMetrics = CreateMetrics(system, gpu);
            _cachedHardware = CreateHardware(system, gpu);
            _cachedAt = DateTimeOffset.UtcNow;
            return _cachedMetrics;
        }
        finally
        {
            _sampleLock.Release();
        }
    }

    internal async Task<FieldHardwareSnapshot> HardwareAsync(
        CancellationToken cancellationToken)
    {
        _ = await SampleAsync(cancellationToken).ConfigureAwait(false);
        return _cachedHardware
            ?? new FieldHardwareSnapshot("unknown", 0, "unknown", 0, "unknown", 0);
    }

    private static FieldMetricSnapshot CreateMetrics(
        SystemStatusSnapshot system,
        GpuStatusSnapshot gpu)
    {
        double memoryPercent = 0;
        double memoryUsedGb = 0;
        if (system.Memory is { TotalBytes: > 0 } memory)
        {
            ulong usedBytes = memory.TotalBytes - memory.AvailableBytes;
            memoryPercent = 100d * usedBytes / memory.TotalBytes;
            memoryUsedGb = usedBytes / 1_073_741_824d;
        }

        double diskPercent = 0;
        if (system.SystemDisk is { TotalBytes: > 0 } disk)
        {
            diskPercent = 100d * (disk.TotalBytes - disk.AvailableBytes) / disk.TotalBytes;
        }

        double gpuPercent = gpu.Adapters
            .Where(static adapter => adapter.UsagePercent.HasValue)
            .Select(static adapter => adapter.UsagePercent!.Value)
            .DefaultIfEmpty(0)
            .Max();

        long uptimeSeconds = Math.Max(0, system.UptimeSeconds ?? 0);
        TimeSpan uptime = TimeSpan.FromSeconds(uptimeSeconds);
        string uptimeText = $"{(long)uptime.TotalHours:00}:{uptime.Minutes:00}:{uptime.Seconds:00}";
        var placeholder = new Dictionary<string, bool>(StringComparer.Ordinal)
        {
            ["net"] = true,
            ["tmp"] = true,
        };
        if (gpu.Adapters.All(static adapter => !adapter.UsagePercent.HasValue))
        {
            placeholder["gpu"] = true;
        }

        return new FieldMetricSnapshot(
            Clamp(system.Cpu?.UsagePercent ?? 0),
            Clamp(memoryPercent),
            Math.Max(0, memoryUsedGb),
            Clamp(gpuPercent),
            0,
            Clamp(diskPercent),
            0,
            uptimeText,
            placeholder);
    }

    private static FieldHardwareSnapshot CreateHardware(
        SystemStatusSnapshot system,
        GpuStatusSnapshot gpu)
    {
        int cores = system.Cpu?.LogicalProcessorCount ?? 0;
        string cpu = string.IsNullOrWhiteSpace(system.Cpu?.Model)
            ? cores > 0 ? $"unknown · {cores}c" : "unknown"
            : $"{system.Cpu.Model} · {cores}c";
        double memoryGb = (system.Memory?.TotalBytes ?? 0) / 1_073_741_824d;
        string memory = memoryGb > 0 ? $"{memoryGb:0.#} gb" : "unknown";

        GpuAdapterStatus? primaryGpu = gpu.Adapters
            .OrderByDescending(static adapter =>
                adapter.DedicatedVideoMemoryBytes + adapter.DedicatedSystemMemoryBytes)
            .FirstOrDefault();
        ulong vramBytes = primaryGpu is null
            ? 0
            : primaryGpu.DedicatedVideoMemoryBytes + primaryGpu.DedicatedSystemMemoryBytes;
        double vramGb = vramBytes / 1_073_741_824d;
        string gpuText = primaryGpu is null
            ? "unknown"
            : vramGb > 0 ? $"{primaryGpu.Name} · {vramGb:0.#} gb" : primaryGpu.Name;

        return new FieldHardwareSnapshot(cpu, cores, memory, memoryGb, gpuText, vramGb);
    }

    private static double Clamp(double value) =>
        double.IsFinite(value) ? Math.Clamp(value, 0, 100) : 0;

    public ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            _disposed = true;
            _sampleLock.Dispose();
        }

        return ValueTask.CompletedTask;
    }
}
