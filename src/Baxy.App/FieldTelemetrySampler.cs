using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

/// <summary>The rail's readings (design v4); each is null when the PC did not give it, and the view shows «—».</summary>
internal sealed record FieldMetricSnapshot(
    double? Cpu,
    double? Gpu,
    double? GpuTemperature,
    double? ModelVramGb,
    double? ModelRamGb);

/// <summary>
/// Reads the PC's processor and graphics use, the graphics card's temperature and what BAXY's model takes (llama-server
/// and the mind: video memory and RAM), at most once per 900 ms however often the view asks (it asks every 1.5 s).
/// </summary>
internal sealed class FieldTelemetrySampler : IAsyncDisposable
{
    private static readonly TimeSpan CacheLifetime = TimeSpan.FromMilliseconds(900);
    private const double Gibibyte = 1_073_741_824d;

    private readonly WindowsSystemStatusProvider _system = new();
    private readonly WindowsGpuStatusProvider _gpu = new();
    private readonly Func<int?> _mindProcess;
    private readonly ModelProcessTracker _processes;
    private readonly Action<string> _report;
    private readonly Func<CancellationToken, Task<FieldMetricSnapshot>> _measure;
    private readonly SemaphoreSlim _sampleLock = new(1, 1);
    private DateTimeOffset _cachedAt;
    private FieldMetricSnapshot? _cachedMetrics;
    private bool _disposed;

    /// <param name="mindProcess">The mind's process id while it runs (its llama-server is found by its executable).</param>
    /// <param name="measure">Tests measure with a double instead of the PC.</param>
    /// <param name="processes">Tests give the tracker a double instead of the PC's process table.</param>
    /// <param name="report">Where a skipped reading is recorded (the trace listeners by default).</param>
    internal FieldTelemetrySampler(
        Func<int?> mindProcess,
        Func<CancellationToken, Task<FieldMetricSnapshot>>? measure = null,
        ModelProcessTracker? processes = null,
        Action<string>? report = null)
    {
        _mindProcess = mindProcess ?? throw new ArgumentNullException(nameof(mindProcess));
        _processes = processes ?? new ModelProcessTracker();
        _report = report ?? (static message => System.Diagnostics.Trace.TraceWarning(message));
        _measure = measure ?? MeasureAsync;
    }

    internal async Task<FieldMetricSnapshot> SampleAsync(CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_cachedMetrics is not null && DateTimeOffset.UtcNow - _cachedAt <= CacheLifetime)
        {
            return _cachedMetrics;
        }

        await _sampleLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_cachedMetrics is not null && DateTimeOffset.UtcNow - _cachedAt <= CacheLifetime)
            {
                return _cachedMetrics;
            }

            _cachedMetrics = await _measure(cancellationToken).ConfigureAwait(false);
            _cachedAt = DateTimeOffset.UtcNow;
            return _cachedMetrics;
        }
        finally
        {
            _sampleLock.Release();
        }
    }

    private async Task<FieldMetricSnapshot> MeasureAsync(CancellationToken cancellationToken)
    {
        Task<SystemStatusSnapshot> systemTask = _system.GetStatusAsync(SystemStatusScope.Cpu, cancellationToken).AsTask();
        Task<GpuStatusSnapshot> gpuTask = _gpu.GetStatusAsync(GpuStatusScope.Usage, cancellationToken).AsTask();
        Task<(double? Temperature, double? Vram, double? Ram)> modelTask = Task.Run(ReadModel, cancellationToken);
        await Task.WhenAll(systemTask, gpuTask, modelTask).ConfigureAwait(false);

        SystemStatusSnapshot system = await systemTask.ConfigureAwait(false);
        GpuStatusSnapshot gpu = await gpuTask.ConfigureAwait(false);
        (double? temperature, double? vram, double? ram) = await modelTask.ConfigureAwait(false);
        double? gpuPercent = gpu.Adapters
            .Where(static adapter => adapter.UsagePercent.HasValue)
            .Select(static adapter => (double?)adapter.UsagePercent!.Value)
            .Max();
        return new FieldMetricSnapshot(Percent(system.Cpu?.UsagePercent), Percent(gpuPercent), temperature, vram, ram);
    }

    // The model's processes: the mind (a virtual environment's python.exe starts the real interpreter as its child) and
    // the llama-server it started. Only BAXY's own: a bench's llama-server runs the same executable.
    internal (double? Temperature, double? Vram, double? Ram) ReadModel()
    {
        double? temperature = WindowsModelResourceReader.GpuTemperatureCelsius();
        if (_mindProcess() is not { } mind)
        {
            return (temperature, null, null);
        }

        try
        {
            List<int> processes = _processes.ProcessesOf(mind);
            long? vram = WindowsModelResourceReader.DedicatedVideoBytes(processes);
            long? ram = WindowsModelResourceReader.WorkingSetBytes(processes);
            return (temperature, vram / Gibibyte, ram / Gibibyte);
        }
        catch (OutOfMemoryException exception)
        {
            // A PC short of RAM cannot even list or read the processes (a large model loading, seen 2026-11-05): this sample leaves
            // out the model's readings (the view shows «—») and the next one tries again. Any other failure still propagates.
            _report("Telemetry: the model's processes could not be read (out of memory); this sample is skipped. " + exception.Message);
            return (temperature, null, null);
        }
    }

    private static double? Percent(double? value) =>
        value is { } measured && double.IsFinite(measured) ? Math.Clamp(measured, 0, 100) : null;

    public ValueTask DisposeAsync()
    {
        // The lock is not disposed: a reading under way at shutdown still releases it in its finally (it used to throw
        // ObjectDisposedException there). A SemaphoreSlim whose wait handle nobody asked for holds nothing to free.
        _disposed = true;

        return ValueTask.CompletedTask;
    }
}
