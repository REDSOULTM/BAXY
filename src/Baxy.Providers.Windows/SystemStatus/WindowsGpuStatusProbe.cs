using System.ComponentModel;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.SystemStatus;

internal readonly record struct GpuAdapterKey(uint LowPart, int HighPart);

internal sealed record GpuAdapterReading(
    GpuAdapterKey Key,
    string Name,
    uint VendorId,
    uint DeviceId,
    ulong DedicatedVideoMemoryBytes,
    ulong DedicatedSystemMemoryBytes,
    ulong SharedSystemMemoryLimitBytes);

internal sealed record GpuUsageReading(
    GpuAdapterKey Key,
    double UsagePercent,
    ulong DedicatedMemoryUsageBytes,
    ulong SharedMemoryUsageBytes);

internal sealed class GpuInvalidMeasurementException : InvalidOperationException
{
    public GpuInvalidMeasurementException(string message)
        : base(message)
    {
    }

    public GpuInvalidMeasurementException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal interface IGpuStatusProbe
{
    IGpuStatusProbeSession OpenSession();
}

internal interface IGpuStatusProbeSession : IDisposable
{
    IReadOnlyList<GpuAdapterReading> ReadAdapters();

    ValueTask<IReadOnlyList<GpuUsageReading>> ReadUsageAsync(
        IReadOnlyList<GpuAdapterKey> adapters,
        TimeSpan samplingInterval,
        CancellationToken cancellationToken);

    bool IsCurrent();
}

internal sealed partial class WindowsGpuStatusProbe : IGpuStatusProbe
{
    private const int MaximumAdapters = 64;
    private const uint DxgiAdapterFlagRemote = 1;
    private const uint DxgiAdapterFlagSoftware = 2;
    private const int DxgiErrorNotFound = unchecked((int)0x887A0002);
    private const uint ErrorSuccess = 0;
    private const uint PdhMoreData = 0x800007D2;
    private const uint PdhFormatDouble = 0x00000200;
    private const uint PdhFormatLarge = 0x00000400;
    private const uint PdhStatusValidData = 0;
    private const uint PdhStatusNewData = 1;
    private const uint PdhStatusNoObject = 0xC0000BB8;
    private const uint PdhStatusNoCounter = 0xC0000BB9;
    private const uint PdhFunctionNotFound = 0xC0000BBE;
    private const uint PdhStatusNoCounterName = 0xC0000BBF;
    private const uint PdhStatusBadCounterName = 0xC0000BC0;
    private const uint PdhNoCounters = 0xC0000BDF;
    private const int MaximumPdhBufferBytes = 4 * 1024 * 1024;
    private const int MaximumPdhItems = 65_536;
    private const int MaximumPdhInstanceNameCharacters = 1_024;
    private const double MaximumEngineSumWithTolerance = 100.5d;
    private const string GpuEngineCounterPath =
        @"\GPU Engine(*)\Utilization Percentage";
    private const string DedicatedUsageCounterPath =
        @"\GPU Adapter Memory(*)\Dedicated Usage";
    private const string SharedUsageCounterPath =
        @"\GPU Adapter Memory(*)\Shared Usage";

    private static readonly Guid IidDxgiFactory1 =
        new("770aae78-f26f-4dba-a829-253c83d1b387");

    public IGpuStatusProbeSession OpenSession()
    {
        int result = CreateDXGIFactory1(in IidDxgiFactory1, out nint factory);
        ReleaseOnFailure(result, factory);
        ThrowForHResult(result);
        if (factory == 0)
        {
            throw new InvalidOperationException("DXGI did not return a factory.");
        }

        return new GpuStatusProbeSession(factory);
    }

    private static ReadOnlyCollection<GpuAdapterReading> ReadAdapters(nint factory)
    {
        var adapters = new List<GpuAdapterReading>();
        for (uint index = 0; index <= MaximumAdapters; index++)
        {
            int result = EnumAdapters1(factory, index, out nint adapter);
            if (result == DxgiErrorNotFound)
            {
                if (adapters.Count == 0)
                {
                    throw new PlatformNotSupportedException(
                        "Windows did not expose a hardware graphics adapter.");
                }

                return adapters.AsReadOnly();
            }

            ReleaseOnFailure(result, adapter);
            ThrowForHResult(result);
            if (adapter == 0)
            {
                throw new InvalidOperationException("DXGI returned an empty adapter.");
            }

            if (index == MaximumAdapters)
            {
                ReleaseIUnknown(adapter);
                throw new InvalidOperationException(
                    "Windows exposed more graphics adapters than the bounded contract allows.");
            }

            try
            {
                NativeDxgiAdapterDescription description = GetAdapterDescription(adapter);
                if ((description.Flags & (DxgiAdapterFlagRemote | DxgiAdapterFlagSoftware)) != 0)
                {
                    continue;
                }

                adapters.Add(new GpuAdapterReading(
                    new GpuAdapterKey(
                        description.AdapterLuid.LowPart,
                        description.AdapterLuid.HighPart),
                    description.ReadDescription(),
                    description.VendorId,
                    description.DeviceId,
                    checked((ulong)description.DedicatedVideoMemory),
                    checked((ulong)description.DedicatedSystemMemory),
                    checked((ulong)description.SharedSystemMemory)));
            }
            finally
            {
                ReleaseIUnknown(adapter);
            }
        }

        throw new InvalidOperationException("DXGI adapter enumeration did not terminate.");
    }

    private static async ValueTask<IReadOnlyList<GpuUsageReading>> ReadUsageAsync(
        IReadOnlyList<GpuAdapterKey> adapters,
        TimeSpan samplingInterval,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(adapters);
        if (adapters.Count is < 1 or > MaximumAdapters)
        {
            throw new ArgumentOutOfRangeException(nameof(adapters));
        }

        cancellationToken.ThrowIfCancellationRequested();
        ThrowIfDuplicateAdapterKeys(adapters);

        nint query = 0;
        uint status = PdhOpenQuery(null, 0, out query);
        if (status != ErrorSuccess)
        {
            if (query != 0)
            {
                _ = PdhCloseQuery(query);
            }

            throw CreatePdhException(status, "PDH could not open a local query.");
        }

        if (query == 0)
        {
            throw new GpuInvalidMeasurementException(
                "PDH returned an empty local query handle.");
        }

        try
        {
            nint engineCounter = AddCounter(query, GpuEngineCounterPath);
            nint dedicatedCounter = AddCounter(query, DedicatedUsageCounterPath);
            nint sharedCounter = AddCounter(query, SharedUsageCounterPath);

            Collect(query);
            await Task.Delay(samplingInterval, cancellationToken).ConfigureAwait(false);
            Collect(query);
            cancellationToken.ThrowIfCancellationRequested();

            PdhValue[] engines = ReadCounterArray(engineCounter, PdhFormatDouble);
            PdhValue[] dedicated = ReadCounterArray(dedicatedCounter, PdhFormatLarge);
            PdhValue[] shared = ReadCounterArray(sharedCounter, PdhFormatLarge);
            return AggregateUsage(adapters, engines, dedicated, shared);
        }
        finally
        {
            _ = PdhCloseQuery(query);
        }
    }

    private sealed class GpuStatusProbeSession(nint factory) : IGpuStatusProbeSession
    {
        private nint _factory = factory;

        public IReadOnlyList<GpuAdapterReading> ReadAdapters()
        {
            ObjectDisposedException.ThrowIf(_factory == 0, this);
            return WindowsGpuStatusProbe.ReadAdapters(_factory);
        }

        public ValueTask<IReadOnlyList<GpuUsageReading>> ReadUsageAsync(
            IReadOnlyList<GpuAdapterKey> adapters,
            TimeSpan samplingInterval,
            CancellationToken cancellationToken)
        {
            ObjectDisposedException.ThrowIf(_factory == 0, this);
            return WindowsGpuStatusProbe.ReadUsageAsync(
                adapters,
                samplingInterval,
                cancellationToken);
        }

        public bool IsCurrent()
        {
            ObjectDisposedException.ThrowIf(_factory == 0, this);
            return IsFactoryCurrent(_factory);
        }

        public void Dispose()
        {
            nint current = Interlocked.Exchange(ref _factory, 0);
            ReleaseIUnknown(current);
        }
    }

    internal static IReadOnlyList<GpuUsageReading> AggregateUsage(
        IReadOnlyList<GpuAdapterKey> adapters,
        IReadOnlyList<PdhValue> engineValues,
        IReadOnlyList<PdhValue> dedicatedValues,
        IReadOnlyList<PdhValue> sharedValues)
    {
        ArgumentNullException.ThrowIfNull(adapters);
        ArgumentNullException.ThrowIfNull(engineValues);
        ArgumentNullException.ThrowIfNull(dedicatedValues);
        ArgumentNullException.ThrowIfNull(sharedValues);
        if (adapters.Count is < 1 or > MaximumAdapters)
        {
            throw new ArgumentOutOfRangeException(nameof(adapters));
        }

        ThrowIfDuplicateAdapterKeys(adapters);
        var knownAdapters = adapters.ToHashSet();
        var engineSums = new Dictionary<GpuEngineKey, double>();
        foreach (PdhValue value in engineValues)
        {
            if (!TryParseEngineInstance(value.InstanceName, out GpuEngineKey engine))
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned malformed GPU engine metadata.");
            }

            if (!knownAdapters.Contains(engine.Adapter))
            {
                continue;
            }

            double reading = value.DoubleValue;
            if (!double.IsFinite(reading) || reading is < 0d or > 100d)
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned invalid GPU utilization.");
            }

            double sum = engineSums.GetValueOrDefault(engine) + reading;
            if (!double.IsFinite(sum) || sum > MaximumEngineSumWithTolerance)
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned inconsistent GPU utilization.");
            }

            engineSums[engine] = Math.Min(100d, sum);
        }

        if (engineSums.Count == 0)
        {
            throw new PlatformNotSupportedException(
                "Windows did not expose GPU engine utilization counters.");
        }

        Dictionary<GpuAdapterKey, ulong> dedicatedByAdapter = AggregateMemory(
            knownAdapters,
            dedicatedValues);
        Dictionary<GpuAdapterKey, ulong> sharedByAdapter = AggregateMemory(
            knownAdapters,
            sharedValues);
        var result = new List<GpuUsageReading>(adapters.Count);
        for (int index = 0; index < adapters.Count; index++)
        {
            GpuAdapterKey adapter = adapters[index];
            if (!dedicatedByAdapter.TryGetValue(adapter, out ulong dedicatedUsage)
                || !sharedByAdapter.TryGetValue(adapter, out ulong sharedUsage))
            {
                continue;
            }

            double utilization = engineSums
                .Where(pair => pair.Key.Adapter == adapter)
                .Select(static pair => pair.Value)
                .DefaultIfEmpty(0d)
                .Max();
            result.Add(new GpuUsageReading(
                adapter,
                utilization,
                dedicatedUsage,
                sharedUsage));
        }

        if (result.Count == 0)
        {
            throw new PlatformNotSupportedException(
                "Windows did not expose a complete GPU memory counter pair for any adapter.");
        }

        return result;
    }

    private static Dictionary<GpuAdapterKey, ulong> AggregateMemory(
        HashSet<GpuAdapterKey> knownAdapters,
        IReadOnlyList<PdhValue> values)
    {
        var totals = new Dictionary<GpuAdapterKey, ulong>();
        foreach (PdhValue value in values)
        {
            if (!TryParseMemoryInstance(value.InstanceName, out GpuAdapterKey adapter))
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned malformed GPU memory metadata.");
            }

            if (!knownAdapters.Contains(adapter))
            {
                continue;
            }

            if (value.LargeValue < 0)
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned invalid GPU memory usage.");
            }

            try
            {
                ulong reading = checked((ulong)value.LargeValue);
                totals[adapter] = checked(totals.GetValueOrDefault(adapter) + reading);
            }
            catch (OverflowException exception)
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned overflowing GPU memory usage.",
                    exception);
            }
        }

        return totals;
    }

    private static void ThrowIfDuplicateAdapterKeys(IReadOnlyList<GpuAdapterKey> adapters)
    {
        if (adapters.Distinct().Count() != adapters.Count)
        {
            throw new GpuInvalidMeasurementException(
                "GPU adapter identifiers must be unique within one snapshot.");
        }
    }

    private static nint AddCounter(nint query, string path)
    {
        uint status = PdhAddEnglishCounter(query, path, 0, out nint counter);
        return ValidateCounterHandle(status, counter);
    }

    internal static nint ValidateCounterHandle(uint status, nint counter)
    {
        if (status == ErrorSuccess)
        {
            if (counter == 0)
            {
                throw new GpuInvalidMeasurementException(
                    "PDH returned an empty GPU performance counter handle.");
            }

            return counter;
        }

        if (status is PdhStatusNoObject
            or PdhStatusNoCounter
            or PdhFunctionNotFound
            or PdhStatusNoCounterName
            or PdhStatusBadCounterName
            or PdhNoCounters)
        {
            throw new PlatformNotSupportedException(
                "Windows does not expose the required GPU performance counter.");
        }

        throw CreatePdhException(status, "PDH could not add a GPU performance counter.");
    }

    private static void Collect(nint query)
    {
        uint status = PdhCollectQueryData(query);
        if (status != ErrorSuccess)
        {
            throw CreatePdhException(status, "PDH could not collect GPU counters.");
        }
    }

    private static unsafe PdhValue[] ReadCounterArray(nint counter, uint format)
    {
        for (int attempt = 0; attempt < 3; attempt++)
        {
            uint bufferSize = 0;
            uint itemCount = 0;
            uint status = PdhGetFormattedCounterArray(
                counter,
                format,
                ref bufferSize,
                out itemCount,
                0);
            if (status != PdhMoreData)
            {
                throw CreatePdhException(status, "PDH could not size a GPU counter array.");
            }

            if (bufferSize == 0 || bufferSize > MaximumPdhBufferBytes)
            {
                throw new InvalidOperationException("PDH returned an invalid GPU counter buffer size.");
            }

            uint allocatedBufferSize = bufferSize;
            nint buffer = Marshal.AllocHGlobal(checked((int)allocatedBufferSize));
            try
            {
                status = PdhGetFormattedCounterArray(
                    counter,
                    format,
                    ref bufferSize,
                    out itemCount,
                    buffer);
                if (status == PdhMoreData)
                {
                    continue;
                }

                if (status != ErrorSuccess)
                {
                    throw CreatePdhException(status, "PDH could not read a GPU counter array.");
                }

                int nativeItemSize = sizeof(NativePdhFormattedCounterValueItem);
                ValidateCounterArrayBounds(
                    allocatedBufferSize,
                    bufferSize,
                    itemCount,
                    checked((uint)nativeItemSize));

                var values = new List<PdhValue>(checked((int)itemCount));
                var items = (NativePdhFormattedCounterValueItem*)buffer;
                for (uint index = 0; index < itemCount; index++)
                {
                    NativePdhFormattedCounterValueItem item = items[index];
                    if (item.Value.Status is not (PdhStatusValidData or PdhStatusNewData))
                    {
                        continue;
                    }

                    string instanceName = ReadBoundedString(
                        item.Name,
                        buffer,
                        bufferSize);
                    values.Add(new PdhValue(
                        instanceName,
                        item.Value.Value.Double,
                        item.Value.Value.Large));
                }

                return values.ToArray();
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }

        throw new InvalidOperationException("PDH GPU counters changed too quickly to read safely.");
    }

    internal static void ValidateCounterArrayBounds(
        uint allocatedBufferSize,
        uint reportedBufferSize,
        uint itemCount,
        uint nativeItemSize)
    {
        if (allocatedBufferSize == 0
            || reportedBufferSize > allocatedBufferSize
            || reportedBufferSize == 0 && itemCount != 0
            || nativeItemSize == 0
            || itemCount > MaximumPdhItems
            || checked((ulong)itemCount * nativeItemSize) > reportedBufferSize)
        {
            throw new InvalidOperationException("PDH returned an invalid GPU counter array.");
        }
    }

    private static unsafe string ReadBoundedString(
        nint value,
        nint buffer,
        uint bufferSize)
    {
        if (value == 0)
        {
            throw new InvalidOperationException("PDH returned an empty GPU counter name.");
        }

        nuint start = checked((nuint)buffer);
        nuint end = checked(start + bufferSize);
        nuint pointer = checked((nuint)value);
        if (pointer < start || pointer >= end)
        {
            throw new InvalidOperationException("PDH returned a GPU counter name outside its buffer.");
        }

        nuint remainingBytes = end - pointer;
        int maximumCharacters = checked((int)Math.Min(
            remainingBytes / sizeof(char),
            MaximumPdhInstanceNameCharacters + 1u));
        char* characters = (char*)value;
        for (int length = 0; length < maximumCharacters; length++)
        {
            if (characters[length] == '\0')
            {
                if (length == 0)
                {
                    throw new InvalidOperationException("PDH returned an empty GPU counter name.");
                }

                return new string(characters, 0, length);
            }
        }

        throw new InvalidOperationException("PDH returned an overlong GPU counter name.");
    }

    private static bool TryParseEngineInstance(string value, out GpuEngineKey key)
    {
        Match match = EngineInstancePattern().Match(value);
        if (!match.Success
            || !TryParseAdapterKey(match, out GpuAdapterKey adapter)
            || !uint.TryParse(
                match.Groups["physical"].ValueSpan,
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out uint physical)
            || !uint.TryParse(
                match.Groups["engine"].ValueSpan,
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out uint engine))
        {
            key = default;
            return false;
        }

        key = new GpuEngineKey(adapter, physical, engine);
        return true;
    }

    private static bool TryParseMemoryInstance(string value, out GpuAdapterKey key)
    {
        Match match = MemoryInstancePattern().Match(value);
        if (!match.Success)
        {
            key = default;
            return false;
        }

        return TryParseAdapterKey(match, out key);
    }

    private static bool TryParseAdapterKey(Match match, out GpuAdapterKey key)
    {
        if (!uint.TryParse(
                match.Groups["high"].ValueSpan,
                NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture,
                out uint high)
            || !uint.TryParse(
                match.Groups["low"].ValueSpan,
                NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture,
                out uint low))
        {
            key = default;
            return false;
        }

        key = new GpuAdapterKey(low, unchecked((int)high));
        return true;
    }

    private static unsafe int EnumAdapters1(nint factory, uint index, out nint adapter)
    {
        adapter = 0;
        nint* vtable = *(nint**)factory;
        var method = (delegate* unmanaged[Stdcall]<nint, uint, nint*, int>)vtable[12];
        nint local = 0;
        int result = method(factory, index, &local);
        adapter = local;
        return result;
    }

    private static unsafe bool IsFactoryCurrent(nint factory)
    {
        nint* vtable = *(nint**)factory;
        var method = (delegate* unmanaged[Stdcall]<nint, int>)vtable[13];
        return method(factory) != 0;
    }

    private static unsafe NativeDxgiAdapterDescription GetAdapterDescription(nint adapter)
    {
        nint* vtable = *(nint**)adapter;
        var method = (delegate* unmanaged[Stdcall]<
            nint,
            NativeDxgiAdapterDescription*,
            int>)vtable[10];
        NativeDxgiAdapterDescription description = default;
        int result = method(adapter, &description);
        ThrowForHResult(result);
        return description;
    }

    private static unsafe void ReleaseIUnknown(nint pointer)
    {
        if (pointer == 0)
        {
            return;
        }

        nint* vtable = *(nint**)pointer;
        var release = (delegate* unmanaged[Stdcall]<nint, uint>)vtable[2];
        _ = release(pointer);
    }

    private static void ReleaseOnFailure(int result, nint pointer)
    {
        if (result < 0 && pointer != 0)
        {
            ReleaseIUnknown(pointer);
        }
    }

    private static void ThrowForHResult(int result)
    {
        if (result < 0)
        {
            Marshal.ThrowExceptionForHR(result);
        }
    }

    private static Win32Exception CreatePdhException(uint status, string message) =>
        new Win32Exception(unchecked((int)status), message);

    [GeneratedRegex(
        "^pid_[0-9]+_luid_0x(?<high>[0-9a-f]{1,8})_0x(?<low>[0-9a-f]{1,8})_phys_(?<physical>[0-9]+)_eng_(?<engine>[0-9]+)_engtype_[^\\r\\n]{0,256}$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EngineInstancePattern();

    [GeneratedRegex(
        "^luid_0x(?<high>[0-9a-f]{1,8})_0x(?<low>[0-9a-f]{1,8})_phys_[0-9]+(?:_part_[0-9]+)?(?:#[0-9]+)?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryInstancePattern();

    [LibraryImport("dxgi.dll")]
    private static partial int CreateDXGIFactory1(
        in Guid interfaceId,
        out nint factory);

    [LibraryImport(
        "pdh.dll",
        EntryPoint = "PdhOpenQueryW",
        StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint PdhOpenQuery(
        string? dataSource,
        nuint userData,
        out nint query);

    [LibraryImport(
        "pdh.dll",
        EntryPoint = "PdhAddEnglishCounterW",
        StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint PdhAddEnglishCounter(
        nint query,
        string fullCounterPath,
        nuint userData,
        out nint counter);

    [LibraryImport("pdh.dll", EntryPoint = "PdhCollectQueryData")]
    private static partial uint PdhCollectQueryData(nint query);

    [LibraryImport("pdh.dll", EntryPoint = "PdhGetFormattedCounterArrayW")]
    private static partial uint PdhGetFormattedCounterArray(
        nint counter,
        uint format,
        ref uint bufferSize,
        out uint itemCount,
        nint itemBuffer);

    [LibraryImport("pdh.dll", EntryPoint = "PdhCloseQuery")]
    private static partial uint PdhCloseQuery(nint query);

    internal readonly record struct PdhValue(
        string InstanceName,
        double DoubleValue,
        long LargeValue);

    private readonly record struct GpuEngineKey(
        GpuAdapterKey Adapter,
        uint PhysicalIndex,
        uint EngineIndex);

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativeLuid
    {
        public readonly uint LowPart;
        public readonly int HighPart;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private unsafe struct NativeDxgiAdapterDescription
    {
        public fixed char Description[128];
        public uint VendorId;
        public uint DeviceId;
        public uint SubSystemId;
        public uint Revision;
        public nuint DedicatedVideoMemory;
        public nuint DedicatedSystemMemory;
        public nuint SharedSystemMemory;
        public NativeLuid AdapterLuid;
        public uint Flags;

        public string ReadDescription()
        {
            fixed (char* value = Description)
            {
                int length = 0;
                while (length < 128 && value[length] != '\0')
                {
                    length++;
                }

                return new string(value, 0, length);
            }
        }
    }

    [StructLayout(LayoutKind.Explicit)]
    private readonly struct NativePdhValueUnion
    {
        [FieldOffset(0)]
        public readonly double Double;

        [FieldOffset(0)]
        public readonly long Large;
    }

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativePdhFormattedCounterValue
    {
        public readonly uint Status;
        public readonly NativePdhValueUnion Value;
    }

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct NativePdhFormattedCounterValueItem
    {
        public readonly nint Name;
        public readonly NativePdhFormattedCounterValue Value;
    }
}
