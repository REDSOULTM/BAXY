using System.ComponentModel;
using System.Security;
using System.Text;

namespace Baxy.Providers.Windows.SystemStatus;

public sealed class WindowsSystemStatusProvider : ISystemStatusProvider
{
    internal static readonly TimeSpan DefaultCpuSamplingInterval = TimeSpan.FromMilliseconds(150);
    private const int MaximumCpuModelUtf8Bytes = 512;

    private readonly ISystemStatusProbe _probe;
    private readonly TimeSpan _cpuSamplingInterval;

    public WindowsSystemStatusProvider()
        : this(new WindowsSystemStatusProbe(), DefaultCpuSamplingInterval)
    {
    }

    internal WindowsSystemStatusProvider(
        ISystemStatusProbe probe,
        TimeSpan cpuSamplingInterval)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        if (cpuSamplingInterval <= TimeSpan.Zero
            || cpuSamplingInterval > TimeSpan.FromSeconds(5))
        {
            throw new ArgumentOutOfRangeException(nameof(cpuSamplingInterval));
        }

        _cpuSamplingInterval = cpuSamplingInterval;
    }

    public async ValueTask<SystemStatusSnapshot> GetStatusAsync(
        SystemStatusScope scope,
        CancellationToken cancellationToken)
    {
        ValidateScope(scope);
        cancellationToken.ThrowIfCancellationRequested();

        CpuStatus? cpu = null;
        MemoryStatus? memory = null;
        SystemDiskStatus? systemDisk = null;
        BatteryStatus? battery = null;
        OperatingSystemStatus? operatingSystem = null;
        long? uptimeSeconds = null;
        var failures = new List<SystemStatusFailure>();

        if (scope.HasFlag(SystemStatusScope.Cpu))
        {
            try
            {
                cpu = await ReadCpuAsync(cancellationToken).ConfigureAwait(false);
                if (cpu is null)
                {
                    failures.Add(Invalid(SystemStatusScope.Cpu));
                }
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception exception) when (IsExpectedProbeFailure(exception))
            {
                failures.Add(Failed(SystemStatusScope.Cpu, exception));
            }
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (scope.HasFlag(SystemStatusScope.Memory))
        {
            TryRead(
                SystemStatusScope.Memory,
                () => CreateMemoryStatus(_probe.ReadMemory()),
                value => memory = value,
                failures);
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (scope.HasFlag(SystemStatusScope.SystemDisk))
        {
            TryRead(
                SystemStatusScope.SystemDisk,
                () => CreateDiskStatus(_probe.ReadSystemDisk()),
                value => systemDisk = value,
                failures);
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (scope.HasFlag(SystemStatusScope.Battery))
        {
            TryRead(
                SystemStatusScope.Battery,
                () => CreateBatteryStatus(_probe.ReadPowerStatus()),
                value => battery = value,
                failures);
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (scope.HasFlag(SystemStatusScope.OperatingSystem))
        {
            TryRead(
                SystemStatusScope.OperatingSystem,
                () => CreateOperatingSystemStatus(_probe.ReadOperatingSystem()),
                value => operatingSystem = value,
                failures);
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (scope.HasFlag(SystemStatusScope.Uptime))
        {
            TryRead(
                SystemStatusScope.Uptime,
                () => CreateUptimeSeconds(_probe.ReadUptimeMilliseconds()),
                value => uptimeSeconds = value,
                failures);
        }

        return new SystemStatusSnapshot(
            cpu,
            memory,
            systemDisk,
            battery,
            operatingSystem,
            uptimeSeconds,
            failures.AsReadOnly());
    }

    private async ValueTask<CpuStatus?> ReadCpuAsync(CancellationToken cancellationToken)
    {
        CpuTimeSample first = _probe.ReadCpuTimes();
        int logicalProcessorCount = _probe.ReadLogicalProcessorCount();
        string? model = NormalizeCpuModel(_probe.ReadCpuModel());
        await _probe.DelayAsync(_cpuSamplingInterval, cancellationToken).ConfigureAwait(false);
        CpuTimeSample second = _probe.ReadCpuTimes();

        if (logicalProcessorCount < 1
            || !TryCalculateCpuUsage(first, second, out double usagePercent))
        {
            return null;
        }

        return new CpuStatus(usagePercent, logicalProcessorCount, model);
    }

    private static bool TryCalculateCpuUsage(
        CpuTimeSample first,
        CpuTimeSample second,
        out double usagePercent)
    {
        usagePercent = default;
        if (second.Idle < first.Idle
            || second.Kernel < first.Kernel
            || second.User < first.User)
        {
            return false;
        }

        ulong idleDelta = second.Idle - first.Idle;
        ulong kernelDelta = second.Kernel - first.Kernel;
        ulong userDelta = second.User - first.User;
        if (ulong.MaxValue - kernelDelta < userDelta)
        {
            return false;
        }

        ulong totalDelta = kernelDelta + userDelta;
        if (totalDelta == 0 || idleDelta > totalDelta)
        {
            return false;
        }

        usagePercent = 100d * (totalDelta - idleDelta) / totalDelta;
        return double.IsFinite(usagePercent) && usagePercent is >= 0d and <= 100d;
    }

    private static string? NormalizeCpuModel(string? value)
    {
        if (value is null)
        {
            return null;
        }

        string normalized;
        try
        {
            normalized = value.Trim().Normalize(NormalizationForm.FormC);
        }
        catch (ArgumentException)
        {
            return null;
        }

        return normalized.Length > 0
            && Encoding.UTF8.GetByteCount(normalized) <= MaximumCpuModelUtf8Bytes
            && normalized.All(static character => !char.IsControl(character))
                ? normalized
                : null;
    }

    private static MemoryStatus? CreateMemoryStatus(MemoryReading reading) =>
        reading.TotalBytes > 0 && reading.AvailableBytes <= reading.TotalBytes
            ? new MemoryStatus(reading.TotalBytes, reading.AvailableBytes)
            : null;

    private static SystemDiskStatus? CreateDiskStatus(DiskReading reading) =>
        reading.TotalBytes > 0
            && reading.AvailableBytes >= 0
            && reading.AvailableBytes <= reading.TotalBytes
                ? new SystemDiskStatus(reading.TotalBytes, reading.AvailableBytes)
                : null;

    private static BatteryStatus? CreateBatteryStatus(PowerReading reading)
    {
        bool? acOnline = reading.AcLineStatus switch
        {
            0 => false,
            1 => true,
            byte.MaxValue => null,
            _ => null,
        };
        if (reading.AcLineStatus is not (0 or 1 or byte.MaxValue))
        {
            return null;
        }

        bool explicitlyAbsent = reading.BatteryFlag != byte.MaxValue
            && (reading.BatteryFlag & 0x80) != 0;
        if (explicitlyAbsent)
        {
            return reading.BatteryLifePercent == byte.MaxValue
                ? new BatteryStatus(false, null, null, acOnline)
                : null;
        }

        int? percentage = reading.BatteryLifePercent switch
        {
            <= 100 => reading.BatteryLifePercent,
            byte.MaxValue => null,
            _ => null,
        };
        if (reading.BatteryLifePercent is > 100 and < byte.MaxValue)
        {
            return null;
        }

        bool? isPresent = reading.BatteryFlag == byte.MaxValue && percentage is null
            ? null
            : true;
        bool? charging = isPresent == true && reading.BatteryFlag != byte.MaxValue
            ? (reading.BatteryFlag & 0x08) != 0
            : null;
        return isPresent.HasValue || percentage.HasValue || charging.HasValue || acOnline.HasValue
            ? new BatteryStatus(isPresent, percentage, charging, acOnline)
            : null;
    }

    private static OperatingSystemStatus? CreateOperatingSystemStatus(
        OperatingSystemReading reading) =>
        reading.MajorVersion > 0
            && reading.MinorVersion >= 0
            && reading.BuildNumber > 0
            && reading.Architecture is "x64" or "x86" or "arm64" or "arm"
                ? new OperatingSystemStatus(
                    reading.MajorVersion,
                    reading.MinorVersion,
                    reading.BuildNumber,
                    reading.Architecture,
                    reading.IsWorkstation)
                : null;

    private static long? CreateUptimeSeconds(ulong milliseconds)
    {
        ulong seconds = milliseconds / 1000;
        return seconds <= long.MaxValue ? (long)seconds : null;
    }

    private static void TryRead<T>(
        SystemStatusScope scope,
        Func<T?> reader,
        Action<T> assign,
        List<SystemStatusFailure> failures)
        where T : class
    {
        try
        {
            T? value = reader();
            if (value is null)
            {
                failures.Add(Invalid(scope));
            }
            else
            {
                assign(value);
            }
        }
        catch (Exception exception) when (IsExpectedProbeFailure(exception))
        {
            failures.Add(Failed(scope, exception));
        }
    }

    private static void TryRead(
        SystemStatusScope scope,
        Func<long?> reader,
        Action<long> assign,
        List<SystemStatusFailure> failures)
    {
        try
        {
            long? value = reader();
            if (!value.HasValue)
            {
                failures.Add(Invalid(scope));
            }
            else
            {
                assign(value.Value);
            }
        }
        catch (Exception exception) when (IsExpectedProbeFailure(exception))
        {
            failures.Add(Failed(scope, exception));
        }
    }

    private static SystemStatusFailure Invalid(SystemStatusScope scope) =>
        new(scope, SystemStatusErrorCodes.InvalidMeasurement);

    private static SystemStatusFailure Failed(SystemStatusScope scope, Exception exception) =>
        new(
            scope,
            exception is PlatformNotSupportedException or NotSupportedException
                ? SystemStatusErrorCodes.Unsupported
                : SystemStatusErrorCodes.MeasurementFailed);

    private static bool IsExpectedProbeFailure(Exception exception) => exception is
        ArgumentException
        or IOException
        or InvalidOperationException
        or NotSupportedException
        or OverflowException
        or PlatformNotSupportedException
        or SecurityException
        or UnauthorizedAccessException
        or Win32Exception;

    private static void ValidateScope(SystemStatusScope scope)
    {
        if (scope == SystemStatusScope.None || (scope & ~SystemStatusScope.All) != 0)
        {
            throw new ArgumentOutOfRangeException(nameof(scope));
        }
    }
}
