using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// N3 (Providers hung with no CPU, 2026-11-04 18:22 and 2026-11-05 04:45, reading baxy-core's stdout). The core's helper
/// PowerShells compile with Add-Type, and csc.exe leaves the core's job (HelperProcessJob: a helper's children leave it, so
/// what a script opens for the person survives BAXY). Measured: when the core ends just as a helper has created the
/// compiler, the helper dies with the job, the compiler stays suspended for ever with no CPU (all its threads
/// Wait/Suspended, 10 of them on the PC that night, the oldest from 06:45 the day before), and with what it inherited: the
/// core's stdout, so its reader never saw the end of the pipe (2 of 100 and 2 of 48 starts on an unreadable profile).
/// </summary>
public static class ChildProcessHandles
{
    private const int StdOutput = -11;
    private const int StdError = -12;
    private const uint HandleFlagInherit = 1;
    private static readonly string[] Compilers = ["csc", "cvtres"];

    /// <summary>
    /// The core's stdout and stderr are the App's pipes, and a process started with them inherits them (CreateProcess,
    /// bInheritHandles: «each inheritable handle in the calling process is inherited by the new process»; Process.Start
    /// always passes it true). None of the core's children writes there: each redirects its own, and an application
    /// opened for the person has no use for them. So nothing the core starts can keep those pipes open once it is gone.
    /// Stdin stays: a helper that does not redirect it gets the core's, as before, and nothing waits on its end.
    /// </summary>
    public static void KeepOutputFromChildren()
    {
        foreach (int which in new[] { StdOutput, StdError })
        {
            IntPtr handle = GetStdHandle(which);
            if (handle != IntPtr.Zero && handle != new IntPtr(-1))
            {
                // A console's handle may refuse it: nothing is held then, and the start goes on.
                _ = SetHandleInformation(handle, HandleFlagInherit, 0);
            }
        }
    }

    /// <summary>
    /// Ends the compilers a helper left behind in an earlier run: suspended, with their parent gone. Nobody can resume one
    /// (the handle to its thread died with the parent), so it would stay until the PC restarts. Each by its process id;
    /// a compiler whose parent lives is that process's. Returns how many ended.
    /// </summary>
    public static int ReapOrphanedCompilers()
    {
        int reaped = 0;
        foreach (string name in Compilers)
        {
            foreach (Process process in Process.GetProcessesByName(name))
            {
                using (process)
                {
                    try
                    {
                        if (IsSuspended(process) && ParentIsGone(process))
                        {
                            process.Kill();
                            reaped++;
                        }
                    }
                    catch (Exception exception) when (exception is Win32Exception or InvalidOperationException
                        or NotSupportedException or ArgumentException)
                    {
                        // It ended meanwhile, or it is not this account's.
                    }
                }
            }
        }

        return reaped;
    }

    private static bool IsSuspended(Process process)
    {
        process.Refresh();
        ProcessThreadCollection threads = process.Threads;
        if (threads.Count == 0)
        {
            return false;
        }

        foreach (ProcessThread thread in threads)
        {
            if (thread.ThreadState != System.Diagnostics.ThreadState.Wait || thread.WaitReason != ThreadWaitReason.Suspended)
            {
                return false;
            }
        }

        return true;
    }

    private static bool ParentIsGone(Process process)
    {
        var information = default(ProcessBasicInformation);
        if (NtQueryInformationProcess(process.Handle, 0, ref information, Marshal.SizeOf<ProcessBasicInformation>(), out _) != 0)
        {
            return false;
        }

        int parent = information.InheritedFromUniqueProcessId.ToInt32();
        try
        {
            using Process alive = Process.GetProcessById(parent);
            // A process id comes back into use: one born after this process is not its parent.
            return alive.StartTime > process.StartTime;
        }
        catch (ArgumentException)
        {
            return true;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessBasicInformation
    {
        public IntPtr ExitStatus;
        public IntPtr PebBaseAddress;
        public IntPtr AffinityMask;
        public IntPtr BasePriority;
        public IntPtr UniqueProcessId;
        public IntPtr InheritedFromUniqueProcessId;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetStdHandle(int which);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

    [DllImport("ntdll.dll")]
    private static extern int NtQueryInformationProcess(
        IntPtr process, int informationClass, ref ProcessBasicInformation information, int length, out int returned);
}
