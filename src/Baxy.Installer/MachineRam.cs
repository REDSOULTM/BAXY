using System.Runtime.InteropServices;

namespace Baxy.Installer;

/// <summary>VRAM5 (AUD1 F7): the RAM installed in this PC, for what the installer tells before downloading
/// (MachineGpu.WithRam).</summary>
internal static partial class MachineRam
{
    /// <summary>MiB, as the firmware says it (GetPhysicallyInstalledSystemMemory: «the amount of RAM that is physically
    /// installed on the computer», learn.microsoft.com, sysinfoapi.h), not what Windows can use; null when unread.</summary>
    internal static long? InstalledMib() =>
        GetPhysicallyInstalledSystemMemory(out ulong kib) && kib > 0 ? (long)(kib / 1024) : null;

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetPhysicallyInstalledSystemMemory(out ulong totalMemoryInKilobytes);
}
