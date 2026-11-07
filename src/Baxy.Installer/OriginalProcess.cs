using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Installer;

/// <summary>
/// Windows does not let a program delete its own exe, so an uninstall started from the installed copy runs from a copy in
/// TEMP. As Inno Setup's uninstaller does, the copy ends the original with its result (what the script waiting on the
/// original reads as its exit code) and only then deletes what the original held.
/// </summary>
internal static partial class OriginalProcess
{
    /// <summary>The exe the original runs from; null when it is gone or cannot be read.</summary>
    internal static string? PathOf(int processId)
    {
        try
        {
            using Process original = Process.GetProcessById(processId);
            return original.MainModule?.FileName;
        }
        catch (Exception gone) when (gone is ArgumentException or InvalidOperationException or Win32Exception)
        {
            Program.Log(gone.ToString());
            return null;
        }
    }

    /// <summary>False when that process is gone or is not this installer: another program is never ended.</summary>
    internal static bool End(int processId, int exitCode, string expectedName)
    {
        Process original;
        try
        {
            original = Process.GetProcessById(processId);
        }
        catch (ArgumentException)
        {
            return false;
        }

        using (original)
        {
            try
            {
                if (!string.Equals(original.ProcessName, expectedName, StringComparison.OrdinalIgnoreCase)
                    || !TerminateProcess(original.SafeHandle, unchecked((uint)exitCode)))
                {
                    return false;
                }

                return original.WaitForExit(TimeSpan.FromSeconds(30));
            }
            catch (Exception gone) when (gone is InvalidOperationException or Win32Exception)
            {
                Program.Log(gone.ToString());
                return false;
            }
        }
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool TerminateProcess(SafeProcessHandle process, uint exitCode);
}
