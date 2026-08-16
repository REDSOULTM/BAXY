using System.ComponentModel;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security;
using System.Text;

namespace Baxy.Providers.Windows.SystemStatus;

public sealed class WindowsGpuStatusProvider : IGpuStatusProvider
{
    internal static readonly TimeSpan DefaultSamplingInterval = TimeSpan.FromSeconds(1);
    private const int MaximumAdapters = 64;
    private const int MaximumAdapterNameUtf8Bytes = 512;

    private readonly IGpuStatusProbe _probe;
    private readonly TimeSpan _samplingInterval;

    public WindowsGpuStatusProvider()
        : this(new WindowsGpuStatusProbe(), DefaultSamplingInterval)
    {
    }

    internal WindowsGpuStatusProvider(
        IGpuStatusProbe probe,
        TimeSpan samplingInterval)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        if (samplingInterval < TimeSpan.FromMilliseconds(10)
            || samplingInterval > TimeSpan.FromSeconds(5))
        {
            throw new ArgumentOutOfRangeException(nameof(samplingInterval));
        }

        _samplingInterval = samplingInterval;
    }

    public async ValueTask<GpuStatusSnapshot> GetStatusAsync(
        GpuStatusScope scope,
        CancellationToken cancellationToken)
    {
        ValidateScope(scope);
        cancellationToken.ThrowIfCancellationRequested();

        for (int attempt = 0; attempt < 2; attempt++)
        {
            IGpuStatusProbeSession session;
            try
            {
                session = _probe.OpenSession();
            }
            catch (Exception exception) when (IsExpectedProbeFailure(exception))
            {
                return FailedIdentity(exception);
            }

            using (session)
            {
                IReadOnlyList<GpuAdapterReading> readings;
                try
                {
                    readings = session.ReadAdapters();
                }
                catch (Exception exception) when (IsExpectedProbeFailure(exception))
                {
                    return FailedIdentity(exception);
                }

                if (!TryCreateIdentity(readings, out GpuAdapterStatus[] adapters))
                {
                    return InvalidIdentity();
                }

                IReadOnlyList<GpuUsageReading>? usage = null;
                Exception? usageFailure = null;
                if (scope == GpuStatusScope.Usage)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        usage = await session.ReadUsageAsync(
                            readings.Select(static adapter => adapter.Key).ToArray(),
                            _samplingInterval,
                            cancellationToken).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                    {
                        throw;
                    }
                    catch (Exception exception) when (IsExpectedProbeFailure(exception))
                    {
                        usageFailure = exception;
                    }
                }

                bool isCurrent;
                try
                {
                    isCurrent = session.IsCurrent();
                }
                catch (Exception exception) when (IsExpectedProbeFailure(exception))
                {
                    return FailedIdentity(exception);
                }

                if (!isCurrent)
                {
                    if (attempt == 0)
                    {
                        continue;
                    }

                    return MeasurementFailedIdentity();
                }

                if (scope == GpuStatusScope.Identity)
                {
                    return new GpuStatusSnapshot(
                        adapters,
                        Array.Empty<GpuStatusFailure>());
                }

                if (usageFailure is not null)
                {
                    return FailedUsage(adapters, usageFailure);
                }

                if (!TryApplyUsage(
                        readings,
                        adapters,
                        usage,
                        out GpuAdapterStatus[] measured,
                        out GpuStatusFailure[] measurementFailures))
                {
                    return InvalidUsage(adapters);
                }

                return new GpuStatusSnapshot(
                    measured,
                    measurementFailures);
            }
        }

        return MeasurementFailedIdentity();
    }

    private static bool TryCreateIdentity(
        IReadOnlyList<GpuAdapterReading>? readings,
        out GpuAdapterStatus[] adapters)
    {
        adapters = [];
        if (readings is null
            || readings.Count is < 1 or > MaximumAdapters)
        {
            return false;
        }

        var keys = new HashSet<GpuAdapterKey>();
        foreach (GpuAdapterReading? reading in readings)
        {
            if (reading is null || !keys.Add(reading.Key))
            {
                return false;
            }
        }

        var result = new GpuAdapterStatus[readings.Count];
        for (int index = 0; index < readings.Count; index++)
        {
            GpuAdapterReading reading = readings[index];
            string? name = NormalizeAdapterName(reading.Name);
            if (name is null)
            {
                return false;
            }

            try
            {
                _ = checked(
                    reading.DedicatedVideoMemoryBytes
                    + reading.DedicatedSystemMemoryBytes);
            }
            catch (OverflowException)
            {
                return false;
            }

            result[index] = new GpuAdapterStatus(
                name,
                reading.VendorId,
                reading.DeviceId,
                reading.DedicatedVideoMemoryBytes,
                reading.DedicatedSystemMemoryBytes,
                reading.SharedSystemMemoryLimitBytes,
                null,
                null,
                null);
        }

        adapters = result;
        return true;
    }

    private static bool TryApplyUsage(
        IReadOnlyList<GpuAdapterReading> identity,
        GpuAdapterStatus[] adapters,
        IReadOnlyList<GpuUsageReading>? usage,
        out GpuAdapterStatus[] measured,
        out GpuStatusFailure[] failures)
    {
        measured = [];
        failures = [];
        if (usage is null
            || identity.Count != adapters.Length
            || usage.Count > adapters.Length)
        {
            return false;
        }

        var knownKeys = identity.Select(static value => value.Key).ToHashSet();
        var byKey = new Dictionary<GpuAdapterKey, GpuUsageReading>();
        foreach (GpuUsageReading? reading in usage)
        {
            if (reading is null
                || !knownKeys.Contains(reading.Key)
                || !byKey.TryAdd(reading.Key, reading))
            {
                return false;
            }
        }

        GpuAdapterStatus[] result = adapters.ToArray();
        var missing = new List<GpuStatusFailure>(adapters.Length - byKey.Count);
        for (int index = 0; index < adapters.Length; index++)
        {
            if (!byKey.TryGetValue(identity[index].Key, out GpuUsageReading? reading))
            {
                missing.Add(new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.Unsupported,
                    index));
                continue;
            }

            if (!double.IsFinite(reading.UsagePercent)
                || reading.UsagePercent is < 0d or > 100d)
            {
                return false;
            }

            ulong dedicatedCapacity;
            try
            {
                dedicatedCapacity = checked(
                    adapters[index].DedicatedVideoMemoryBytes
                    + adapters[index].DedicatedSystemMemoryBytes);
            }
            catch (OverflowException)
            {
                return false;
            }

            if (reading.DedicatedMemoryUsageBytes > dedicatedCapacity
                || reading.SharedMemoryUsageBytes
                    > adapters[index].SharedSystemMemoryLimitBytes)
            {
                return false;
            }

            result[index] = adapters[index] with
            {
                UsagePercent = reading.UsagePercent,
                DedicatedMemoryUsageBytes = reading.DedicatedMemoryUsageBytes,
                SharedMemoryUsageBytes = reading.SharedMemoryUsageBytes,
            };
        }

        measured = result;
        if (byKey.Count == 0)
        {
            failures =
            [
                new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.Unsupported),
            ];
        }
        else
        {
            failures = missing.ToArray();
        }

        return true;
    }

    private static string? NormalizeAdapterName(string? value)
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
            && Encoding.UTF8.GetByteCount(normalized) <= MaximumAdapterNameUtf8Bytes
            && normalized.EnumerateRunes().All(static rune =>
                Rune.GetUnicodeCategory(rune) is not (
                    UnicodeCategory.Control
                    or UnicodeCategory.Format
                    or UnicodeCategory.LineSeparator
                    or UnicodeCategory.ParagraphSeparator))
                ? normalized
                : null;
    }

    private static GpuStatusSnapshot FailedIdentity(Exception exception) => new(
        Array.Empty<GpuAdapterStatus>(),
        new[] { Failure(GpuStatusScope.Identity, exception) });

    private static GpuStatusSnapshot InvalidIdentity() => new(
        Array.Empty<GpuAdapterStatus>(),
        new[]
        {
            new GpuStatusFailure(
                GpuStatusScope.Identity,
                SystemStatusErrorCodes.InvalidMeasurement),
        });

    private static GpuStatusSnapshot MeasurementFailedIdentity() => new(
        Array.Empty<GpuAdapterStatus>(),
        new[]
        {
            new GpuStatusFailure(
                GpuStatusScope.Identity,
                SystemStatusErrorCodes.MeasurementFailed),
        });

    private static GpuStatusSnapshot FailedUsage(
        IReadOnlyList<GpuAdapterStatus> adapters,
        Exception exception) => new(
            adapters,
            new[] { Failure(GpuStatusScope.Usage, exception) });

    private static GpuStatusSnapshot InvalidUsage(
        IReadOnlyList<GpuAdapterStatus> adapters) => new(
            adapters,
            new[]
            {
                new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.InvalidMeasurement),
            });

    private static GpuStatusFailure Failure(GpuStatusScope scope, Exception exception) => new(
        scope,
        exception switch
        {
            GpuInvalidMeasurementException => SystemStatusErrorCodes.InvalidMeasurement,
            DllNotFoundException or EntryPointNotFoundException
                or PlatformNotSupportedException or NotSupportedException =>
                SystemStatusErrorCodes.Unsupported,
            _ => SystemStatusErrorCodes.MeasurementFailed,
        });

    private static bool IsExpectedProbeFailure(Exception exception) => exception is
        ArgumentException
        or BadImageFormatException
        or DllNotFoundException
        or EntryPointNotFoundException
        or IOException
        or InvalidOperationException
        or NotSupportedException
        or OverflowException
        or PlatformNotSupportedException
        or SecurityException
        or UnauthorizedAccessException
        or Win32Exception
        or COMException;

    private static void ValidateScope(GpuStatusScope scope)
    {
        if (scope is not (GpuStatusScope.Identity or GpuStatusScope.Usage))
        {
            throw new ArgumentOutOfRangeException(nameof(scope));
        }
    }
}
