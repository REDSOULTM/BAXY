using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    // PKEY_AppUserModel_ID: the package application a window belongs to, as the taskbar groups it.
    private static readonly Guid AppUserModelIdFormat = new("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
    private const uint AppUserModelIdProperty = 5;
    private static readonly Guid PropertyStoreInterface = new("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");
    private const ushort VariantWideString = 31; // VT_LPWSTR

    /// <summary>
    /// Renew al máximo (velocidad, E014 in pc-lote: «abre la configuración de sonido», six runs at 30-32 s each, all
    /// verification_failed): a frame of the packaged application <paramref name="appUserModelId"/> shown with nothing of
    /// it inside. Forcing its process to end (the bench's cleanup did, read on this PC 2026-10-23: a «Configuración» frame
    /// of ApplicationFrameHost with its title bar alone and no SystemSettings running) leaves the frame behind; Windows
    /// shows that frame again when the application is opened, and no process of the application ever draws in it. The
    /// frame is the application's by the identity Windows gives it (its property store's AppUserModelID), never by its
    /// title; it is empty when no window of another process is inside it (FrameHosts). A frame that is still being
    /// filled (a splash) is empty too, so this alone proves nothing: the opening asks it only after its own grace.
    /// </summary>
    internal static bool ShowsEmptyFrame(string appUserModelId)
    {
        if (string.IsNullOrWhiteSpace(appUserModelId))
            return false;
        bool found = false;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsVisibleFrame(window) || FrameHosts(window, static _ => true)
                || !string.Equals(WindowApplicationId(window), appUserModelId, StringComparison.OrdinalIgnoreCase))
                return true;
            found = true;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return found;
    }

    /// <summary>The AppUserModelID of a window's property store (a packaged application's frame carries its
    /// application's), or null when it has none or it cannot be read.</summary>
    internal static unsafe string? WindowApplicationId(nint window)
    {
        Guid iid = PropertyStoreInterface;
        void* store = null;
        if (SHGetPropertyStoreForWindow(window, &iid, &store) != 0 || store is null)
            return null;
        // PROPVARIANT: 16 bytes on x86, 24 on x64; the value's pointer at offset 8.
        byte* value = stackalloc byte[24];
        new Span<byte>(value, 24).Clear();
        try
        {
            void** table = *(void***)store;
            var getValue = (delegate* unmanaged<void*, PropertyKey*, byte*, int>)table[5];
            var key = new PropertyKey(AppUserModelIdFormat, AppUserModelIdProperty);
            if (getValue(store, &key, value) != 0 || *(ushort*)value != VariantWideString)
                return null;
            char* text = *(char**)(value + 8);
            return text == null ? null : new string(text);
        }
        finally
        {
            _ = PropVariantClear(value);
            var release = (delegate* unmanaged<void*, uint>)(*(void***)store)[2];
            _ = release(store);
        }
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    private readonly struct PropertyKey(Guid formatId, uint propertyId)
    {
        private readonly Guid _formatId = formatId;
        private readonly uint _propertyId = propertyId;
    }

    [LibraryImport("shell32.dll")]
    private static unsafe partial int SHGetPropertyStoreForWindow(nint window, Guid* interfaceId, void** store);

    [LibraryImport("ole32.dll")]
    private static unsafe partial int PropVariantClear(byte* value);
}
