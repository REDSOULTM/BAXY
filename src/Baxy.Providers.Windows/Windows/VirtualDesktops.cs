using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;

namespace Baxy.Providers.Windows.Windows;

// Ronda final 12 (regla 3): whether a window DWM cloaks is on another virtual desktop, read from the shell's documented
// IVirtualDesktopManager (shobjidl_core.h, Windows 10+: «IsWindowOnCurrentVirtualDesktop»). A cloaked window on this
// desktop (a suspended packaged app, the text input host) is not a window left open elsewhere.
internal static partial class VirtualDesktops
{
    private const uint ClsctxInprocServer = 0x1;
    private const uint ClsctxLocalServer = 0x4;
    private const uint CoinitMultithreaded = 0x0;
    private const int SFalse = 1;
    private static readonly Guid ClsidVirtualDesktopManager = new("aa509086-5ca9-4c25-8f95-589d3c07b48a");
    private static readonly Guid IidVirtualDesktopManager = new("a5cd92ff-29be-454c-8d04-d82879fb3f1b");
    private static readonly StrategyBasedComWrappers ComWrappers = new();

    // For each window, whether it is on another desktop; null for one the shell did not answer (all null when the
    // manager could not be created).
    internal static bool?[] OnAnotherDesktop(IReadOnlyList<nint> windows)
    {
        var answers = new bool?[windows.Count];
        int initialized = CoInitializeEx(0, CoinitMultithreaded);
        try
        {
            if (CoCreateInstance(in ClsidVirtualDesktopManager, 0, ClsctxInprocServer | ClsctxLocalServer,
                    in IidVirtualDesktopManager, out nint pointer) < 0 || pointer == 0)
                return answers;
            try
            {
                var manager = (IVirtualDesktopManager)ComWrappers.GetOrCreateObjectForComInstance(
                    pointer, CreateObjectFlags.UniqueInstance);
                try
                {
                    for (int index = 0; index < windows.Count; index++)
                    {
                        if (manager.IsWindowOnCurrentVirtualDesktop(windows[index], out int onCurrent) >= 0)
                            answers[index] = onCurrent == 0;
                    }
                }
                finally
                {
                    (manager as IDisposable)?.Dispose();
                }
            }
            finally
            {
                Marshal.Release(pointer);
            }
        }
        finally
        {
            if (initialized is 0 or SFalse)
                CoUninitialize();
        }

        return answers;
    }

    [LibraryImport("ole32.dll")]
    private static partial int CoInitializeEx(nint reserved, uint coInit);

    [LibraryImport("ole32.dll")]
    private static partial void CoUninitialize();

    [LibraryImport("ole32.dll")]
    private static partial int CoCreateInstance(
        in Guid classId,
        nint outer,
        uint classContext,
        in Guid interfaceId,
        out nint instance);
}

[GeneratedComInterface(Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("a5cd92ff-29be-454c-8d04-d82879fb3f1b")]
internal partial interface IVirtualDesktopManager
{
    [PreserveSig]
    int IsWindowOnCurrentVirtualDesktop(nint topLevelWindow, out int onCurrentDesktop);

    [PreserveSig]
    int GetWindowDesktopId(nint topLevelWindow, out Guid desktopId);

    [PreserveSig]
    int MoveWindowToDesktop(nint topLevelWindow, in Guid desktopId);
}
