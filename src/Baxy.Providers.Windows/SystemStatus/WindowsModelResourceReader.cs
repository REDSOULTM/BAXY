using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// The readings of the view's rail (design v4) that the system status does not give: the graphics card's temperature
/// and the memory BAXY's model takes. A reading Windows does not give is null, never 0.
/// <list type="bullet">
/// <item>Temperature: D3DKMTQueryAdapterInfo with KMTQAITYPE_ADAPTERPERFDATA (d3dkmthk.h, WDDM 2.4+), the source Task
/// Manager reads, in tenths of a degree; an adapter that reports 0 has no sensor.</item>
/// <item>Video memory: the «GPU Process Memory(pid_*)\Dedicated Usage» counter of the given processes.</item>
/// <item>RAM: the processes' working set (the physical memory they hold now, not their commit).</item>
/// </list>
/// </summary>
public static partial class WindowsModelResourceReader
{
    private const int AdapterPerfData = 62;               // KMTQAITYPE_ADAPTERPERFDATA
    private const int MaximumAdapters = 16;               // MAX_ENUM_ADAPTERS
    private const uint PdhMoreData = 0x800007D2;
    private const uint PdhFormatLarge = 0x00000400;
    private const uint PdhStatusValidData = 0x00000000;
    private const uint PdhStatusNewData = 0x00000001;
    private const int MaximumPdhBufferBytes = 4 * 1024 * 1024;
    private const string ProcessMemoryCounter = @"\GPU Process Memory(*)\Dedicated Usage";

    /// <summary>The hottest graphics adapter's temperature in °C, or null when none reports one.</summary>
    public static unsafe double? GpuTemperatureCelsius()
    {
        var adapters = new AdapterInfo[MaximumAdapters];
        fixed (AdapterInfo* buffer = adapters)
        {
            var enumeration = new EnumAdapters2 { NumAdapters = MaximumAdapters, Adapters = (nint)buffer };
            if (D3DKMTEnumAdapters2(ref enumeration) != 0)
            {
                return null;
            }

            double? hottest = null;
            for (int i = 0; i < Math.Min(enumeration.NumAdapters, MaximumAdapters); i++)
            {
                var perf = new AdapterPerfDataNative();
                var query = new QueryAdapterInfo
                {
                    Adapter = adapters[i].Adapter,
                    Type = AdapterPerfData,
                    Data = (nint)(&perf),
                    DataSize = (uint)sizeof(AdapterPerfDataNative),
                };
                if (D3DKMTQueryAdapterInfo(ref query) == 0 && perf.Temperature is > 0 and < 2_000)
                {
                    double celsius = perf.Temperature / 10.0;
                    hottest = hottest is { } known ? Math.Max(known, celsius) : celsius;
                }

                var close = new CloseAdapter { Adapter = adapters[i].Adapter };
                _ = D3DKMTCloseAdapter(ref close);
            }

            return hottest;
        }
    }

    /// <summary>Dedicated video memory the processes hold, in bytes, or null when the counter could not be read.</summary>
    public static unsafe long? DedicatedVideoBytes(IReadOnlyCollection<int> processIds)
    {
        if (processIds.Count == 0 || PdhOpenQuery(null, 0, out nint query) != 0)
        {
            return null;
        }

        try
        {
            if (PdhAddEnglishCounter(query, ProcessMemoryCounter, 0, out nint counter) != 0 || PdhCollectQueryData(query) != 0)
            {
                return null;
            }

            uint size = 0;
            if (PdhGetFormattedCounterArray(counter, PdhFormatLarge, ref size, out _, 0) != PdhMoreData
                || size == 0 || size > MaximumPdhBufferBytes)
            {
                return null;
            }

            nint buffer = Marshal.AllocHGlobal((int)size);
            try
            {
                if (PdhGetFormattedCounterArray(counter, PdhFormatLarge, ref size, out uint count, buffer) != 0)
                {
                    return null;
                }

                string[] prefixes = [.. processIds.Select(static id => "pid_" + id + "_")];
                long total = 0;
                var items = (CounterValueItem*)buffer;
                for (int i = 0; i < count; i++)
                {
                    if (items[i].Status is not (PdhStatusValidData or PdhStatusNewData))
                    {
                        continue;
                    }

                    string name = Marshal.PtrToStringUni(items[i].Name) ?? string.Empty;
                    if (prefixes.Any(prefix => name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)))
                    {
                        total += Math.Max(0, items[i].Large);
                    }
                }

                return total;
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        finally
        {
            _ = PdhCloseQuery(query);
        }
    }

    /// <summary>The processes' working set in bytes, or null when none of them could be read.</summary>
    public static long? WorkingSetBytes(IReadOnlyCollection<int> processIds)
    {
        long total = 0;
        bool read = false;
        foreach (int id in processIds)
        {
            try
            {
                using Process process = Process.GetProcessById(id);
                total += process.WorkingSet64;
                read = true;
            }
            catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                // The process ended between the list and the read.
            }
        }

        return read ? total : null;
    }

    /// <summary>
    /// The processes of the given name that any of the given parents started (NtQueryInformationProcess,
    /// ProcessBasicInformation), with the parent of each. It lists every process of that name once
    /// (Process.GetProcessesByName reads the whole process table, and each Process it returns holds native state), so the
    /// rail calls it rarely and asks <see cref="IsChildOf"/> about the ones it already knows.
    /// </summary>
    public static IReadOnlyList<(int Id, int Parent)> ChildrenOf(IReadOnlyCollection<int> parentIds, string processName)
    {
        var children = new List<(int Id, int Parent)>();
        foreach (Process process in Process.GetProcessesByName(processName))
        {
            using (process)
            {
                try
                {
                    int parent = ParentOf(process.Handle);
                    if (parentIds.Contains(parent))
                    {
                        children.Add((process.Id, parent));
                    }
                }
                catch (Exception exception) when (exception is System.ComponentModel.Win32Exception or InvalidOperationException)
                {
                    // Ended, or not ours to read.
                }
            }
        }

        return children;
    }

    /// <summary>
    /// Whether the process is alive and was started by the given parent. It opens that one process by id: it does not read
    /// the process table, so it is cheap enough to ask on every sample. False when it ended or is not ours to read.
    /// </summary>
    public static bool IsChildOf(int processId, int parentId)
    {
        try
        {
            using Process process = Process.GetProcessById(processId);
            return !process.HasExited && ParentOf(process.Handle) == parentId;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }

    private static int ParentOf(nint handle)
    {
        var info = new ProcessBasicInformation();
        return NtQueryInformationProcess(handle, 0, ref info, Marshal.SizeOf<ProcessBasicInformation>(), out _) == 0
            ? (int)info.InheritedFromUniqueProcessId
            : -1;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessBasicInformation
    {
        public nint ExitStatus;
        public nint PebBaseAddress;
        public nint AffinityMask;
        public nint BasePriority;
        public nint UniqueProcessId;
        public nint InheritedFromUniqueProcessId;
    }

    [LibraryImport("ntdll.dll")]
    private static partial int NtQueryInformationProcess(nint process, int informationClass, ref ProcessBasicInformation information,
        int length, out int returned);

    [StructLayout(LayoutKind.Sequential)]
    private struct AdapterInfo
    {
        public uint Adapter;
        public uint LuidLow;
        public int LuidHigh;
        public uint NumOfSources;
        public int PrecisePresentRegionsPreferred;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct EnumAdapters2
    {
        public int NumAdapters;
        public nint Adapters;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct QueryAdapterInfo
    {
        public uint Adapter;
        public int Type;
        public nint Data;
        public uint DataSize;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct CloseAdapter
    {
        public uint Adapter;
    }

    // D3DKMT_ADAPTER_PERFDATA: the 64-bit members are aligned to 8 (D3DKMT_ALIGN64).
    [StructLayout(LayoutKind.Explicit, Size = 64)]
    private struct AdapterPerfDataNative
    {
        [FieldOffset(0)] public uint PhysicalAdapterIndex;
        [FieldOffset(48)] public uint FanRpm;
        [FieldOffset(52)] public uint Power;
        [FieldOffset(56)] public uint Temperature;
    }

    // PDH_FMT_COUNTERVALUE_ITEM_W with a LONGLONG value.
    [StructLayout(LayoutKind.Sequential)]
    private struct CounterValueItem
    {
        public nint Name;
        public uint Status;
        public long Large;
    }

    [LibraryImport("gdi32.dll")]
    private static partial int D3DKMTEnumAdapters2(ref EnumAdapters2 enumeration);

    [LibraryImport("gdi32.dll")]
    private static partial int D3DKMTQueryAdapterInfo(ref QueryAdapterInfo query);

    [LibraryImport("gdi32.dll")]
    private static partial int D3DKMTCloseAdapter(ref CloseAdapter close);

    [LibraryImport("pdh.dll", EntryPoint = "PdhOpenQueryW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint PdhOpenQuery(string? dataSource, nuint userData, out nint query);

    [LibraryImport("pdh.dll", EntryPoint = "PdhAddEnglishCounterW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint PdhAddEnglishCounter(nint query, string fullCounterPath, nuint userData, out nint counter);

    [LibraryImport("pdh.dll", EntryPoint = "PdhCollectQueryData")]
    private static partial uint PdhCollectQueryData(nint query);

    [LibraryImport("pdh.dll", EntryPoint = "PdhGetFormattedCounterArrayW")]
    private static partial uint PdhGetFormattedCounterArray(nint counter, uint format, ref uint bufferSize, out uint itemCount,
        nint itemBuffer);

    [LibraryImport("pdh.dll", EntryPoint = "PdhCloseQuery")]
    private static partial uint PdhCloseQuery(nint query);
}
