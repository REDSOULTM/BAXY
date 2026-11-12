using System.ComponentModel;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// The PCI vendor ids of the GPUs Windows has with a driver (DXGI, as <see cref="WindowsGpuStatusProbe"/> reads them, in any
/// session and with no WMI). A GPU without its driver shows as Microsoft's basic display adapter, not as its maker.
/// The installer compiles this same file (INS-2): what it downloads for a machine is decided on the list BAXY reads at
/// every start, adapters with no screen plugged included (IDXGIFactory1::EnumAdapters1 «enumerates both adapters (video
/// cards) with or without outputs»).
/// </summary>
public static class WindowsGpuVendors
{
    /// <summary>The vendors of this machine's hardware adapters; none when Windows exposes none or cannot say.</summary>
    public static IReadOnlyList<uint> Read() => Read(new WindowsGpuStatusProbe());

    internal static IReadOnlyList<uint> Read(IGpuStatusProbe probe) =>
        [.. Adapters(probe).Select(static adapter => adapter.VendorId)];

    /// <summary>The hardware adapters themselves, in DXGI's order; none when Windows exposes none or cannot say.</summary>
    internal static IReadOnlyList<GpuAdapterReading> Adapters(IGpuStatusProbe probe)
    {
        ArgumentNullException.ThrowIfNull(probe);
        try
        {
            using IGpuStatusProbeSession session = probe.OpenSession();
            return session.ReadAdapters();
        }
        catch (Exception exception) when (exception is PlatformNotSupportedException
            or InvalidOperationException
            or COMException
            or Win32Exception
            or DllNotFoundException
            or EntryPointNotFoundException)
        {
            return [];
        }
    }
}
