using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// Renew al máximo (w6-settle): the window events of one application's processes while its cold start settles, so the
/// settle can end as soon as the start goes quiet instead of after two still looks 400 ms apart. It only says when to
/// look again; what the start left is always read from the inventory.
/// </summary>
internal interface IWindowEventWatch : IDisposable
{
    /// <summary>
    /// Waits from now until no window event of the application has come for <paramref name="quiet"/> (an event before
    /// the call counts as one at the call), at most <paramref name="within"/>: whether the quiet came, and how long it
    /// waited. A wait that cannot reach the quiet within its limit returns at once, not quiet.
    /// </summary>
    ValueTask<(bool Quiet, TimeSpan Waited)> QuietAsync(
        TimeSpan quiet,
        TimeSpan within,
        CancellationToken cancellationToken);
}

/// <summary>
/// The events Windows raises for top-level windows being created, shown, hidden or renamed (SetWinEventHook out of
/// context, so nothing is loaded into the application), on a thread of its own that holds the hooks and their message
/// loop and removes them itself when disposed, a cancelled wait included. An event counts when its window belongs to the
/// application's processes, to a process one of them started (a helper that draws its windows, found as it shows up), or
/// is a frame of the shell's frame host (ApplicationFrameHost) hosting one of them.
/// </summary>
internal sealed partial class WindowEventWatch : IWindowEventWatch
{
    private const uint EventObjectCreate = 0x8000;
    private const uint EventObjectDestroy = 0x8001;
    private const uint EventObjectHide = 0x8003;
    private const uint EventObjectNameChange = 0x800C;
    private const uint WinEventOutOfContext = 0x0000;
    private const uint WinEventSkipOwnProcess = 0x0002;
    private const uint WmQuit = 0x0012;
    private const uint GaRoot = 2;
    // A frame host's frame holds the hosted window among its first children; no more are read.
    private const int FrameChildrenRead = 32;
    private static readonly TimeSpan StartBudget = TimeSpan.FromMilliseconds(500);
    private static readonly TimeSpan StopBudget = TimeSpan.FromSeconds(1);
    // How old the process snapshot may be before a process it does not list makes it read again.
    private static readonly TimeSpan ParentsAge = TimeSpan.FromMilliseconds(100);

    // The watch whose hooks this thread holds: Windows calls OnEvent on it.
    [ThreadStatic]
    private static WindowEventWatch? t_watch;

    private readonly Thread _thread;
    private readonly ManualResetEventSlim _ready = new(false);

    // Read and written only on the hook thread.
    private readonly HashSet<uint> _family;
    private readonly HashSet<uint> _foreign = [];
    private readonly HashSet<uint> _frameHosts = [];
    private Dictionary<uint, uint> _parents = [];
    private long _parentsReadAt;

    // Shared with the waits and Dispose.
    private long _lastEvent;
    private int _threadId;
    private int _stopRequested;
    private int _hooked;
    private int _unhooked;

    private WindowEventWatch(IEnumerable<int> processes)
    {
        _family = [.. processes.Where(static process => process > 0).Select(static process => unchecked((uint)process))];
        _thread = new Thread(Run) { IsBackground = true, Name = "BAXY window events" };
    }

    // Whether the hook thread removed both hooks (1), could not (-1), or has not yet (0).
    internal int Unhooked => Volatile.Read(ref _unhooked);

    internal bool Running => _thread.IsAlive;

    /// <summary>The watch, hooked and listening; null when Windows did not take the hooks in time.</summary>
    internal static WindowEventWatch? Start(IEnumerable<int> processes)
    {
        var watch = new WindowEventWatch(processes);
        watch._thread.Start();
        if (watch._ready.Wait(StartBudget) && Volatile.Read(ref watch._hooked) == 1)
            return watch;
        watch.Dispose();
        return null;
    }

    public async ValueTask<(bool Quiet, TimeSpan Waited)> QuietAsync(
        TimeSpan quiet,
        TimeSpan within,
        CancellationToken cancellationToken)
    {
        long start = Stopwatch.GetTimestamp();
        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            TimeSpan waited = Stopwatch.GetElapsedTime(start);
            TimeSpan sinceLast = Stopwatch.GetElapsedTime(Math.Max(start, Volatile.Read(ref _lastEvent)));
            (bool reached, TimeSpan sleep) = Step(waited, sinceLast, quiet, within);
            if (reached || sleep <= TimeSpan.Zero)
                return (reached, waited);
            await Task.Delay(sleep, cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// What a wait does next, from how long it has waited and how long ago the last event came (never before the wait):
    /// the quiet reached; else how long to sleep until it could be, zero when its limit ends first (an event flood).
    /// </summary>
    internal static (bool Quiet, TimeSpan Sleep) Step(TimeSpan waited, TimeSpan sinceLast, TimeSpan quiet, TimeSpan within)
    {
        if (sinceLast >= quiet)
            return (true, TimeSpan.Zero);
        TimeSpan toQuiet = quiet - sinceLast;
        return waited + toQuiet > within ? (false, TimeSpan.Zero) : (false, toQuiet);
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _stopRequested, 1) != 0)
            return;
        // The hook thread reads the stop after it publishes its id: either it sees the stop, or the quit reaches it.
        int thread = Interlocked.CompareExchange(ref _threadId, 0, 0);
        if (thread != 0)
            _ = PostThreadMessageW(unchecked((uint)thread), WmQuit, 0, 0);
        if (_thread.ThreadState != System.Threading.ThreadState.Unstarted && _thread.Join(StopBudget))
            _ready.Dispose();
    }

    private unsafe void Run()
    {
        nint shownHook = 0;
        nint namedHook = 0;
        t_watch = this;
        try
        {
            Message message;
            // PM_NOREMOVE on an empty queue: the queue exists before its id is published, so a quit posted to it lands.
            _ = PeekMessageW(&message, 0, 0, 0, 0);
            _ = Interlocked.Exchange(ref _threadId, unchecked((int)GetCurrentThreadId()));
            delegate* unmanaged[Stdcall]<nint, uint, nint, int, int, uint, uint, void> callback = &OnEvent;
            uint flags = WinEventOutOfContext | WinEventSkipOwnProcess;
            shownHook = SetWinEventHook(EventObjectCreate, EventObjectHide, 0, (nint)callback, 0, 0, flags);
            namedHook = SetWinEventHook(EventObjectNameChange, EventObjectNameChange, 0, (nint)callback, 0, 0, flags);
            _ = Interlocked.Exchange(ref _hooked, shownHook != 0 && namedHook != 0 ? 1 : -1);
            _ready.Set();
            if (Volatile.Read(ref _hooked) != 1)
                return;
            // Out-of-context events are delivered while this thread waits for its messages, until the quit.
            while (Interlocked.CompareExchange(ref _stopRequested, 0, 0) == 0 && GetMessageW(&message, 0, 0, 0) > 0)
            {
            }
        }
        finally
        {
            bool removed = shownHook == 0 || UnhookWinEvent(shownHook);
            removed &= namedHook == 0 || UnhookWinEvent(namedHook);
            Volatile.Write(ref _unhooked, removed ? 1 : -1);
            t_watch = null;
            _ready.Set();
        }
    }

    // Never lets an exception out into Windows.
    [UnmanagedCallersOnly(CallConvs = [typeof(CallConvStdcall)])]
    private static void OnEvent(nint hook, uint eventType, nint window, int objectId, int childId, uint thread, uint time)
    {
        try
        {
            t_watch?.Note(eventType, window, objectId, childId);
        }
        catch (Exception exception) when (exception is not OutOfMemoryException)
        {
            // An unreadable window or process counts as no event.
        }
    }

    // OBJID_WINDOW and CHILDID_SELF: the window itself, not a part of it; only top-level windows (a destroyed one has no
    // process left to tell).
    private void Note(uint eventType, nint window, int objectId, int childId)
    {
        if (eventType == EventObjectDestroy || window == 0 || objectId != 0 || childId != 0
            || GetAncestor(window, GaRoot) != window)
            return;
        _ = GetWindowThreadProcessId(window, out uint process);
        if (process != 0 && Counts(process, window))
            Volatile.Write(ref _lastEvent, Stopwatch.GetTimestamp());
    }

    private bool Counts(uint process, nint window)
    {
        if (_family.Contains(process))
            return true;
        if (_frameHosts.Contains(process))
            return HostsFamily(window, process);
        if (_foreign.Contains(process))
            return false;
        if (string.Equals(
            Path.GetFileName(WindowsInstalledApplicationPlatform.ExecutableImagePath(unchecked((int)process))),
            "ApplicationFrameHost.exe",
            StringComparison.OrdinalIgnoreCase))
        {
            _ = _frameHosts.Add(process);
            return HostsFamily(window, process);
        }

        bool? descends = DescendsFromFamily(process);
        if (descends == true)
            _ = _family.Add(process);
        else if (descends == false)
            _ = _foreign.Add(process);
        return descends == true;
    }

    // Within three generations, a process the family started (true), or not (false); null when the snapshot does not
    // list it yet (a process born after it, asked again on its next event).
    private bool? DescendsFromFamily(uint process)
    {
        if (!_parents.ContainsKey(process) && Stopwatch.GetElapsedTime(_parentsReadAt) >= ParentsAge)
        {
            _parents = External.VisibleControlSurface.ParentByProcess();
            _parentsReadAt = Stopwatch.GetTimestamp();
        }

        if (!_parents.ContainsKey(process))
            return null;
        uint id = process;
        for (int generation = 0; generation < 3 && _parents.TryGetValue(id, out uint parent) && parent != 0; generation++)
        {
            if (_family.Contains(parent))
                return true;
            id = parent;
        }

        return false;
    }

    // A frame of the frame host hosting the family: one of its children is a family process's window.
    private bool HostsFamily(nint frame, uint host)
    {
        nint child = 0;
        for (int read = 0; read < FrameChildrenRead; read++)
        {
            child = FindWindowExW(frame, child, null, null);
            if (child == 0)
                return false;
            _ = GetWindowThreadProcessId(child, out uint owner);
            if (owner != host && _family.Contains(owner))
                return true;
        }

        return false;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Message
    {
        public nint Window;
        public uint Value;
        public nuint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
        public uint Private;
    }

    [LibraryImport("user32.dll")]
    private static partial nint SetWinEventHook(
        uint eventMin, uint eventMax, nint module, nint callback, uint processId, uint threadId, uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool UnhookWinEvent(nint hook);

    [LibraryImport("user32.dll")]
    private static unsafe partial int GetMessageW(Message* message, nint window, uint first, uint last);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool PeekMessageW(Message* message, nint window, uint first, uint last, uint remove);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PostThreadMessageW(uint thread, uint message, nuint wParam, nint lParam);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial nint FindWindowExW(nint parent, nint childAfter, string? className, string? windowName);
}
