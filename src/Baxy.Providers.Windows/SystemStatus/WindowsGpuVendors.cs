using System.ComponentModel;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// The PCI vendor ids of the GPUs Windows has with a driver (DXGI, as <see cref="WindowsGpuStatusProbe"/> reads them, in any
/// session and with no WMI). A GPU without its driver shows as Microsoft's basic display adapter, not as its maker.
/// </summary>
public static class WindowsGpuVendors
{
    /// <summary>The vendors of this machine's hardware adapters; none when Windows exposes none or cannot say.</summary>
    public static IReadOnlyList<uint> Read()
    {
        try
        {
            using IGpuStatusProbeSession session = new WindowsGpuStatusProbe().OpenSession();
            return [.. session.ReadAdapters().Select(static adapter => adapter.VendorId)];
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
