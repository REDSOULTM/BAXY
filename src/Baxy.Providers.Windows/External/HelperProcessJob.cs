using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Ronda final 37 (regla: efecto en la ventana de la persona sin pedido): the Core's own helpers (its PowerShell scripts,
/// the UI Automation worker, both tesseracts, the PDF text extractor, winget, yt-dlp and mpv) die with the Core. Since
/// the ronda 36 the App's job lets every process the Core starts leave it (so what the Core opens for the person survives BAXY), and a script halfway
/// through bringing Spotify to the front and clicking went on for up to a minute after BAXY closed. This job is the
/// Core's: kill-on-close, its handle closes when the Core ends, and the helpers' own children leave it silently (the
/// application a script opens for the person, spotify: or a document, is theirs). Assigning is best-effort: a helper
/// that cannot be assigned runs as before.
/// </summary>
internal static class HelperProcessJob
{
    private const uint KillOnJobClose = 0x00002000;
    private const uint SilentBreakawayOk = 0x00001000;
    private const int ExtendedLimitInformation = 9;
    private static readonly Lazy<IntPtr> Job = new(Create);

    internal static void Assign(Process? process)
    {
        if (process is null)
        {
            return;
        }

        try
        {
            IntPtr job = Job.Value;
            if (job != IntPtr.Zero && !process.HasExited)
            {
                _ = AssignProcessToJobObject(job, process.Handle);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
        }
    }

    private static IntPtr Create()
    {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero)
        {
            return IntPtr.Zero;
        }

        var information = new ExtendedLimit
        {
            Basic = new BasicLimit { LimitFlags = KillOnJobClose | SilentBreakawayOk },
        };
        if (!SetInformationJobObject(job, ExtendedLimitInformation, ref information, (uint)Marshal.SizeOf<ExtendedLimit>()))
        {
            CloseHandle(job);
            return IntPtr.Zero;
        }

        return job;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BasicLimit
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IoCounters
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ExtendedLimit
    {
        public BasicLimit Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr attributes, string? name);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimit info, uint length);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr handle);
}
