using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Installer;

/// <summary>
/// REM1 (REV12 A-2): the App's single-instance mutex and its exit event are one per session for every copy of BAXY
/// (src/Baxy.App/App.xaml.cs), so they say that a BAXY is open, not which. Which one is told by the path of each running
/// BAXY's exe, read by PID with QueryFullProcessImageName (Microsoft Learn, «QueryFullProcessImageNameW function»:
/// PROCESS_QUERY_LIMITED_INFORMATION is enough, also for a process of a higher integrity level).
/// </summary>
internal static partial class RunningBaxy
{
    private const uint QueryLimitedInformation = 0x1000;

    /// <summary>The PIDs of the BAXY processes running from <paramref name="app"/> (an installation's app\Baxy.exe).</summary>
    internal static IReadOnlyList<int> From(string app) =>
        Running(app).Where(running => SameFile(running.Path, app)).Select(static running => running.Id).ToList();

    /// <summary>A BAXY runs from another folder, or from one that cannot be read: the exit event could reach it.</summary>
    internal static bool AnyElsewhere(string app) => Running(app).Any(running => !SameFile(running.Path, app));

    /// <summary>Whether any of <paramref name="ids"/> still runs.</summary>
    internal static bool AnyAlive(IEnumerable<int> ids) => ids.Any(static id =>
    {
        try
        {
            using Process process = Process.GetProcessById(id);
            return !process.HasExited;
        }
        catch (Exception gone) when (gone is ArgumentException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    });

    private static bool SameFile(string? path, string app) =>
        path is not null && string.Equals(Path.GetFullPath(path), Path.GetFullPath(app), StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// Every process of this session with the exe name of <paramref name="app"/>, with the path of its exe (null when
    /// unreadable). Another session's BAXY (another user signed in) has its own «Local\» mutex and event, and is not in
    /// the way (revisión ciega de REM1).
    /// </summary>
    private static List<(int Id, string? Path)> Running(string app)
    {
        List<(int, string?)> found = [];
        int session = Process.GetCurrentProcess().SessionId;
        foreach (Process process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(app)))
        {
            using (process)
            {
                if (process.SessionId == session)
                {
                    found.Add((process.Id, ImagePath(process.Id)));
                }
            }
        }

        return found;
    }

    private static unsafe string? ImagePath(int id)
    {
        using SafeProcessHandle handle = OpenProcess(QueryLimitedInformation, false, (uint)id);
        if (handle.IsInvalid)
        {
            return null;
        }

        char[] buffer = new char[32_768];
        int length = buffer.Length;
        fixed (char* name = buffer)
        {
            return QueryFullProcessImageName(handle, 0, name, ref length) ? new string(buffer, 0, length) : null;
        }
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial SafeProcessHandle OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint processId);

    [LibraryImport("kernel32.dll", EntryPoint = "QueryFullProcessImageNameW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool QueryFullProcessImageName(SafeProcessHandle process, uint flags, char* name, ref int size);
}
