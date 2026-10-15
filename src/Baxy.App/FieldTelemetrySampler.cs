using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

/// <summary>What the PC reported; <see cref="Gpu"/> is null when no adapter gives a usage counter.</summary>
internal sealed record FieldMetricSnapshot(
    double Cpu,
    double Mem,
    double MemUsedGb,
    double? Gpu,
    double Dsk,
    string Uptime);

internal sealed class FieldTelemetrySampler : IAsyncDisposable
{
    private static readonly TimeSpan CacheLifetime = TimeSpan.FromMilliseconds(900);
    private readonly WindowsSystemStatusProvider _system = new();
    private readonly WindowsGpuStatusProvider _gpu = new();
    private readonly SemaphoreSlim _sampleLock = new(1, 1);
    private DateTimeOffset _cachedAt;
    private FieldMetricSnapshot? _cachedMetrics;
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
            _cachedAt = DateTimeOffset.UtcNow;
            return _cachedMetrics;
        }
        finally
        {
            _sampleLock.Release();
        }
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

        double? gpuPercent = gpu.Adapters
            .Where(static adapter => adapter.UsagePercent.HasValue)
            .Select(static adapter => (double?)adapter.UsagePercent!.Value)
            .Max();

        long uptimeSeconds = Math.Max(0, system.UptimeSeconds ?? 0);
        TimeSpan uptime = TimeSpan.FromSeconds(uptimeSeconds);
        string uptimeText = $"{(long)uptime.TotalHours:00}:{uptime.Minutes:00}:{uptime.Seconds:00}";
        return new FieldMetricSnapshot(
            Clamp(system.Cpu?.UsagePercent ?? 0),
            Clamp(memoryPercent),
            Math.Max(0, memoryUsedGb),
            gpuPercent is { } measured ? Clamp(measured) : null,
            Clamp(diskPercent),
            uptimeText);
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
