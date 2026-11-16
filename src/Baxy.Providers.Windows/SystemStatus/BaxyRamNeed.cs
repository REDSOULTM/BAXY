using System.Globalization;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>
/// INS2: the RAM BAXY needs, MiB: one source for what the installer tells before downloading (MachineGpu, which compiles
/// this file) and what the App tells before it starts anything (StartupRam).
/// </summary>
public static partial class BaxyRamNeed
{
    /// <summary>Windows 11's own minimum, «RAM: 4 gigabyte (GB) or greater» (Microsoft, Windows 11 specifications,
    /// https://www.microsoft.com/windows/windows-11-specifications, read 2026-11-13).</summary>
    public const long WindowsMib = 4096;

    /// <summary>All of BAXY but the server's GPU memory, with its window and the voice loaded: measured on the PC,
    /// 2026-11-05 (INFORME_AUD1 §2).</summary>
    public const long TreeMib = 3748;

    /// <summary>On integrated graphics, whose memory is the RAM, the server in its fewest cells on Vulkan with the mind's
    /// margin (llm_server.card_mib: AMD3 §3, an RX 7600, 2026-11-09).</summary>
    public const long IntegratedServerMib = 3379 + 200;

    /// <summary>All of BAXY with no model of its own (a model by API): the least its tree took with no model and no voice
    /// in three starts on a 4 GB PC, 777 MB private of 777-855 (INFORME_MIN1 §2, HP 15 Ryzen 3 4300U, 2026-11-15), and the
    /// voice it loads at every start, 1,222 MB committed (recognizer 814, synthesis 258, detector 135, Silero 15:
    /// INFORME_AUD1 F10, notebook, 2026-11-02). The least measured, since below it BAXY is held back.</summary>
    public const long WithoutModelMib = 777 + 1222;

    /// <summary>The least RAM installed BAXY fits in, even thinking with a model by API.</summary>
    public const long ByApiMib = WindowsMib + WithoutModelMib;

    /// <summary>The fake of a test of the real executables (installer and App), «installed[/free]» MiB, as the App's
    /// BAXY_TEST_VRAM_* fake its card.</summary>
    public const string TestVariable = "BAXY_TEST_RAM_MIB";

    /// <summary>This PC's RAM, MiB, null where unread: installed as the firmware says it (GetPhysicallyInstalledSystemMemory:
    /// «the amount of RAM that is physically installed on the computer», learn.microsoft.com, sysinfoapi.h), not what
    /// Windows can use; and free now (MEMORYSTATUSEX.ullAvailPhys: «the amount of physical memory currently available»),
    /// told and never decided on, since it moves by the minute (MIN1: 384-568 MB in ten minutes on one PC).</summary>
    public static (long? InstalledMib, long? FreeMib) Read()
    {
        if (Environment.GetEnvironmentVariable(TestVariable) is { Length: > 0 } faked)
        {
            string[] parts = faked.Split('/');
            return (Mib(parts[0]), parts.Length > 1 ? Mib(parts[1]) : null);
        }

        MemoryStatus status = new() { Length = (uint)Marshal.SizeOf<MemoryStatus>() };
        return (
            GetPhysicallyInstalledSystemMemory(out ulong kib) && kib > 0 ? (long)(kib / 1024) : null,
            GlobalMemoryStatusEx(ref status) ? (long)(status.AvailablePhysical / 1024 / 1024) : null);
    }

    private static long? Mib(string text) =>
        long.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out long mib) ? mib : null;

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatus
    {
        internal uint Length;
        internal uint MemoryLoad;
        internal ulong TotalPhysical;
        internal ulong AvailablePhysical;
        internal ulong TotalPageFile;
        internal ulong AvailablePageFile;
        internal ulong TotalVirtual;
        internal ulong AvailableVirtual;
        internal ulong AvailableExtendedVirtual;
    }

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GlobalMemoryStatusEx(ref MemoryStatus status);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetPhysicallyInstalledSystemMemory(out ulong totalMemoryInKilobytes);
}
