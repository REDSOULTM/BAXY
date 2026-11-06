using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace Baxy.Installer;

internal enum GpuSupport
{
    Measured,
    NotMeasured,
    TooLittleMemory,
    None,
}

internal sealed record GpuAdapter(string DeviceId, long? MemoryBytes);

/// <summary>
/// What the person is told before downloading gigabytes, by PCI vendor id, the way BAXY itself picks its server at every
/// start (MindRuntimeDiscovery). BAXY has been measured on NVIDIA and AMD; Intel graphics have not been; with none of the
/// three it does not start (no_supported_gpu).
/// </summary>
internal static partial class MachineGpu
{
    private const long MinimumMemoryBytes = 3_800_000_000;
    private const string Nvidia = "10de";
    private const string Amd = "1002";
    private const string Intel = "8086";
    private const uint MirroringDriver = 0x8;

    internal static GpuSupport Choose(IReadOnlyList<GpuAdapter> adapters)
    {
        GpuAdapter? nvidia = adapters.FirstOrDefault(adapter => Vendor(adapter.DeviceId) == Nvidia);
        GpuAdapter? amd = adapters.FirstOrDefault(adapter => Vendor(adapter.DeviceId) == Amd);
        if (nvidia is not null)
        {
            return Sized(nvidia);
        }

        if (amd is not null)
        {
            return Sized(amd);
        }

        return adapters.Any(adapter => Vendor(adapter.DeviceId) == Intel) ? GpuSupport.NotMeasured : GpuSupport.None;
    }

    internal static IReadOnlyList<GpuAdapter> Installed()
    {
        List<GpuAdapter> adapters = [];
        for (uint index = 0; ; index++)
        {
            DisplayDevice device = new() { Size = (uint)Marshal.SizeOf<DisplayDevice>() };
            if (!EnumDisplayDevicesW(null, index, ref device, 0))
            {
                return adapters;
            }

            if ((device.StateFlags & MirroringDriver) == 0)
            {
                adapters.Add(new GpuAdapter(device.DeviceIdText, MemoryOf(device.DeviceKeyText)));
            }
        }
    }

    private static GpuSupport Sized(GpuAdapter adapter) =>
        adapter.MemoryBytes < MinimumMemoryBytes ? GpuSupport.TooLittleMemory : GpuSupport.Measured;

    internal static string? Vendor(string deviceId)
    {
        const string prefix = "pci\\ven_";
        string id = deviceId.Trim().ToLowerInvariant();
        return id.StartsWith(prefix, StringComparison.Ordinal) && id.Length >= prefix.Length + 4
            ? id.Substring(prefix.Length, 4)
            : null;
    }

    private static long? MemoryOf(string deviceKey)
    {
        const string machine = @"\Registry\Machine\";
        if (!deviceKey.StartsWith(machine, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        using RegistryKey? key = Registry.LocalMachine.OpenSubKey(deviceKey[machine.Length..]);
        return key?.GetValue("HardwareInformation.qwMemorySize") switch
        {
            long bytes => bytes,
            _ => null,
        };
    }

    [LibraryImport("user32.dll", EntryPoint = "EnumDisplayDevicesW", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumDisplayDevicesW(string? device, uint index, ref DisplayDevice output, uint flags);

    [StructLayout(LayoutKind.Sequential)]
    private unsafe struct DisplayDevice
    {
        internal uint Size;
        private fixed char deviceName[32];
        private fixed char deviceString[128];
        internal uint StateFlags;
        private fixed char deviceId[128];
        private fixed char deviceKey[128];

        internal readonly string DeviceIdText
        {
            get
            {
                fixed (char* text = deviceId)
                {
                    return new string(text);
                }
            }
        }

        internal readonly string DeviceKeyText
        {
            get
            {
                fixed (char* text = deviceKey)
                {
                    return new string(text);
                }
            }
        }
    }
}
