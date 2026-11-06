using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Windows;

/// <summary>One running process, with what tells it from a later process that reuses its id.</summary>
internal sealed record ApplicationProcess(int Id, int Parent, string Name, long StartTicks, string? ExecutablePath);

/// <summary>
/// uso-129: which running processes are one application. A process belongs under an ancestor whose executable's folder
/// holds its own executable (an application's helpers live in or under its folder), so no application is named and a
/// launcher's or the shell's other children stay out. Shape only: nothing here reads what a process is for.
/// </summary>
internal static class ApplicationFamily
{
    internal static IReadOnlyDictionary<int, ApplicationProcess> Read()
    {
        Dictionary<uint, uint> parents = VisibleControlSurface.ParentByProcess();
        var read = new Dictionary<int, ApplicationProcess>();
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                try
                {
                    int parent = parents.TryGetValue((uint)process.Id, out uint id) ? (int)id : 0;
                    read[process.Id] = new(process.Id, parent, process.ProcessName, process.StartTime.ToUniversalTime().Ticks,
                        WindowsInstalledApplicationPlatform.ExecutableImagePath(process.Id));
                }
                catch (Exception exception) when (exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception or NotSupportedException)
                {
                    // It exited while being read, or Windows does not let BAXY read it (another user's, a service).
                }
            }
        }
        return read;
    }

    /// <summary>The topmost ancestor of the same application; the process itself when it has none.</summary>
    internal static ApplicationProcess? MainOf(IReadOnlyDictionary<int, ApplicationProcess> processes, int processId)
    {
        if (!processes.TryGetValue(processId, out ApplicationProcess? current))
            return null;
        for (int depth = 0; depth < 32; depth++)
        {
            // A parent younger than its child is another process that reuses the id.
            if (!processes.TryGetValue(current.Parent, out ApplicationProcess? parent)
                || parent.StartTicks > current.StartTicks
                || VisibleControlSurface.WindowsSessionProcess(parent.Name)
                || !Holds(parent, current))
                break;
            current = parent;
        }
        return current;
    }

    /// <summary>The running processes of the application whose main process this is, the main one among them.</summary>
    internal static IReadOnlyList<ApplicationProcess> Members(
        IReadOnlyDictionary<int, ApplicationProcess> processes, ApplicationProcess main) =>
        [.. processes.Values
            .Where(process => process.Id == main.Id
                || (SameExecutable(process, main) && !string.IsNullOrEmpty(main.ExecutablePath))
                || (Holds(main, process) && DescendsFrom(processes, process, main)))
            .OrderBy(static process => process.Id)];

    private static bool DescendsFrom(
        IReadOnlyDictionary<int, ApplicationProcess> processes, ApplicationProcess process, ApplicationProcess ancestor)
    {
        ApplicationProcess current = process;
        for (int depth = 0; depth < 32; depth++)
        {
            if (current.Parent == ancestor.Id)
                return current.StartTicks >= ancestor.StartTicks;
            if (!processes.TryGetValue(current.Parent, out ApplicationProcess? parent) || parent.StartTicks > current.StartTicks)
                return false;
            current = parent;
        }
        return false;
    }

    private static bool SameExecutable(ApplicationProcess one, ApplicationProcess other) =>
        string.Equals(one.ExecutablePath, other.ExecutablePath, StringComparison.OrdinalIgnoreCase);

    // Whether the folder of holder's executable is, or holds, the folder of the other's.
    private static bool Holds(ApplicationProcess holder, ApplicationProcess other)
    {
        if (Path.GetDirectoryName(holder.ExecutablePath) is not { Length: > 0 } outer
            || Path.GetDirectoryName(other.ExecutablePath) is not { Length: > 0 } inner)
            return false;
        return string.Equals(outer, inner, StringComparison.OrdinalIgnoreCase)
            || inner.StartsWith(outer.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>
/// uso-129: asks a running application to quit through Windows' Restart Manager: WM_QUERYENDSESSION with
/// ENDSESSION_CLOSEAPP to its top-level windows, hidden ones too, WM_ENDSESSION when none refuses, and WM_CLOSE to one that
/// stays (Win32 docs: Restart Manager, «Guidelines for Applications»). It is what an application in
/// the notification area answers: closing its window only hides it. An application may refuse, and without
/// RmForceShutdown nothing is forced: no process is ever ended here.
/// </summary>
internal static partial class ApplicationQuit
{
    private static readonly TimeSpan AskLimit = TimeSpan.FromSeconds(12);
    // An application that took the request may need a while to save and go; one that refused does not go.
    private static readonly TimeSpan ExitLimitAccepted = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan ExitLimitRefused = TimeSpan.FromSeconds(2);

    internal static async ValueTask<ApplicationQuitResult> AskAsync(
        IReadOnlyCollection<int> processIds,
        CancellationToken cancellationToken)
    {
        IReadOnlyDictionary<int, ApplicationProcess> before = ApplicationFamily.Read();
        HashSet<int> own = OwnLine(before);
        ApplicationProcess[] mains = [.. processIds
            .Select(processId => ApplicationFamily.MainOf(before, processId))
            .OfType<ApplicationProcess>()
            .DistinctBy(static process => process.Id)
            .Where(process => !own.Contains(process.Id) && !VisibleControlSurface.WindowsSessionProcess(process.Name))];
        if (mains.Length == 0)
            return ApplicationQuitResult.NotTried;

        bool accepted = await Task.Run(() => RequestShutdown(mains, cancellationToken), cancellationToken).ConfigureAwait(false);

        DateTime deadline = DateTime.UtcNow + (accepted ? ExitLimitAccepted : ExitLimitRefused);
        while (mains.Any(Running) && DateTime.UtcNow < deadline)
            await Task.Delay(150, cancellationToken).ConfigureAwait(false);

        IReadOnlyDictionary<int, ApplicationProcess> after = ApplicationFamily.Read();
        // What was of the application when it was asked, and what its executable runs now (one that starts itself again).
        RemainingProcess[] left = [.. mains
            .SelectMany(main => ApplicationFamily.Members(before, main).Where(member => Alive(after, member))
                .Concat(after.Values.Where(process => process.Id != main.Id && !string.IsNullOrEmpty(main.ExecutablePath)
                    && string.Equals(process.ExecutablePath, main.ExecutablePath, StringComparison.OrdinalIgnoreCase))))
            .DistinctBy(static process => process.Id)
            .OrderBy(static process => process.Id)
            .Select(static process => new RemainingProcess(process.Id, process.Name))];
        string? stayed = mains.FirstOrDefault(main => Alive(after, main))?.Name;
        return new(true, stayed, left);
    }

    private static bool Alive(IReadOnlyDictionary<int, ApplicationProcess> processes, ApplicationProcess process) =>
        processes.TryGetValue(process.Id, out ApplicationProcess? now) && now.StartTicks == process.StartTicks;

    private static bool Running(ApplicationProcess process)
    {
        try
        {
            using Process running = Process.GetProcessById(process.Id);
            return !running.HasExited && running.StartTime.ToUniversalTime().Ticks == process.StartTicks;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }

    // BAXY's own process and the ones above it: asking them would end BAXY in the middle of the call.
    private static HashSet<int> OwnLine(IReadOnlyDictionary<int, ApplicationProcess> processes)
    {
        var line = new HashSet<int>();
        int current = Environment.ProcessId;
        while (line.Add(current) && processes.TryGetValue(current, out ApplicationProcess? process))
            current = process.Parent;
        return line;
    }

    private static unsafe bool RequestShutdown(ApplicationProcess[] mains, CancellationToken cancellationToken)
    {
        char* key = stackalloc char[33];
        if (RmStartSession(out uint session, 0, key) != 0)
            return false;
        try
        {
            RmUniqueProcess[] applications = [.. mains.Select(static main => new RmUniqueProcess
            {
                ProcessId = main.Id,
                StartTimeFileTime = new DateTime(main.StartTicks, DateTimeKind.Utc).ToFileTimeUtc(),
            })];
            fixed (RmUniqueProcess* first = applications)
            {
                if (RmRegisterResources(session, 0, 0, (uint)applications.Length, first, 0, 0) != 0)
                    return false;
            }

            // The application may never answer: past the limit, or when the turn is cancelled, the request is withdrawn.
            using var limit = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            limit.CancelAfter(AskLimit);
            using CancellationTokenRegistration withdraw = limit.Token.Register(() => _ = RmCancelCurrentTask(session));
            return RmShutdown(session, 0, 0) == 0;
        }
        finally
        {
            _ = RmEndSession(session);
        }
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    private struct RmUniqueProcess
    {
        public int ProcessId;
        public long StartTimeFileTime;
    }

    [LibraryImport("rstrtmgr.dll")]
    private static unsafe partial int RmStartSession(out uint session, uint flags, char* key);

    [LibraryImport("rstrtmgr.dll")]
    private static unsafe partial int RmRegisterResources(
        uint session, uint files, nint fileNames, uint applications, RmUniqueProcess* processes, uint services, nint serviceNames);

    [LibraryImport("rstrtmgr.dll")]
    private static partial int RmShutdown(uint session, uint flags, nint status);

    [LibraryImport("rstrtmgr.dll")]
    private static partial int RmCancelCurrentTask(uint session);

    [LibraryImport("rstrtmgr.dll")]
    private static partial int RmEndSession(uint session);
}
