using System.Runtime.InteropServices;

namespace Baxy.Installer;

/// <summary>
/// INS2 (MIN1): whether Windows declares an adapter integrated, by DXCore's own property, not by its maker: an AMD Radeon
/// in a Ryzen with 512 MB set aside by the firmware was told as a small card, and its memory is the PC's RAM.
/// DXCoreAdapterProperty::IsIntegrated, «whether the adapter is reported to be an integrated graphics processor (iGPU)»
/// (learn.microsoft.com, DXCoreAdapterProperty enumeration, updated 2024-09-30, read 2026-11-15); its value 12, the
/// interface ids and the vtable order are the Windows SDK 10.0.26100 dxcore_interface.h's. The adapter is found by the LUID DXGI gave (GetAdapterByLuid), so it is
/// the same one the installer read.
/// </summary>
internal static partial class IntegratedGraphics
{
    private const uint IsIntegratedProperty = 12;
    private static readonly Guid FactoryId = new(0x78ee5945, 0xc36e, 0x4b13, 0xa6, 0x69, 0x00, 0x5d, 0xd1, 0x1c, 0x0f, 0x06);
    private static readonly Guid AdapterId = new(0xf0db4c7f, 0xfe5a, 0x42a2, 0xbd, 0x62, 0xf2, 0xa6, 0xcf, 0x6f, 0xc8, 0x3e);

    /// <summary>True or false as Windows declares it; null where it cannot say (no dxcore.dll before Windows 10 2004,
    /// an adapter gone, a driver without the property).</summary>
    internal static bool? Declared(uint luidLow, int luidHigh)
    {
        try
        {
            return Read(luidLow, luidHigh);
        }
        catch (Exception unread) when (unread is DllNotFoundException or EntryPointNotFoundException or COMException)
        {
            return null;
        }
    }

    private static unsafe bool? Read(uint luidLow, int luidHigh)
    {
        Guid adapterId = AdapterId;
        if (DXCoreCreateAdapterFactory(in FactoryId, out nint factory) < 0 || factory == 0)
        {
            return null;
        }

        nint adapter = 0;
        try
        {
            // IDXCoreAdapterFactory: IUnknown (0-2), CreateAdapterList (3), GetAdapterByLuid (4).
            long luid = ((long)luidHigh << 32) | luidLow;
            nint* factoryTable = *(nint**)factory;
            var byLuid = (delegate* unmanaged[Stdcall]<nint, long*, Guid*, nint*, int>)factoryTable[4];
            if (byLuid(factory, &luid, &adapterId, &adapter) < 0 || adapter == 0)
            {
                return null;
            }

            // IDXCoreAdapter: IUnknown (0-2), IsValid (3), IsAttributeSupported (4), IsPropertySupported (5), GetProperty (6).
            nint* adapterTable = *(nint**)adapter;
            var supported = (delegate* unmanaged[Stdcall]<nint, uint, byte>)adapterTable[5];
            if (supported(adapter, IsIntegratedProperty) == 0)
            {
                return null;
            }

            byte integrated = 0;
            var property = (delegate* unmanaged[Stdcall]<nint, uint, nuint, byte*, int>)adapterTable[6];
            return property(adapter, IsIntegratedProperty, 1, &integrated) < 0 ? null : integrated != 0;
        }
        finally
        {
            Release(adapter);
            Release(factory);
        }
    }

    private static unsafe void Release(nint pointer)
    {
        if (pointer != 0)
        {
            _ = ((delegate* unmanaged[Stdcall]<nint, uint>)(*(nint**)pointer)[2])(pointer);
        }
    }

    [LibraryImport("dxcore.dll")]
    private static partial int DXCoreCreateAdapterFactory(in Guid interfaceId, out nint factory);
}
