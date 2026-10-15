using System.Buffers.Binary;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// When the person last touched the keyboard or the mouse, told apart from BAXY's own input by its mark
/// (<see cref="BaxyInputMark"/>): any event without it is the person's (the live harness's simulated user too, which
/// injects with a mark of its own). The times are <see cref="Environment.TickCount64"/> milliseconds.
/// </summary>
internal interface IUserInputPause
{
    /// <summary>The last input that did not carry BAXY's mark.</summary>
    long LastForeignInputMs { get; }

    /// <summary>
    /// The last input of the person that can move the front to another window: a mouse button going down, or Alt or
    /// the Windows key (a switch, the Start menu, the taskbar). Typing in their own window is not one. When the kind
    /// cannot be told, any input of theirs counts (<see cref="LastForeignInputMs"/>).
    /// </summary>
    long LastFrontMovingInputMs => LastForeignInputMs;

    /// <summary>
    /// The last input of the person that can reach a window's content: a key going down or up, a mouse button or the
    /// wheel. A bare move of the mouse is not one (it types nothing and moves no caret). When the kind cannot be told,
    /// any input of theirs counts (<see cref="LastForeignInputMs"/>).
    /// </summary>
    long LastReachingInputMs => LastForeignInputMs;

    /// <summary>
    /// The last input of the person that Raw Input delivered and that can act on a window other than the one in front:
    /// a mouse button or the wheel (they land under the cursor), Alt or a Windows key going down (a switch, the Start
    /// menu, showing the desktop), or a key the shell routes past the front (the media, browser and launch keys). Keys
    /// typed into the window in front and bare moves are not one. An input the detector missed is of no known kind and
    /// is not one either: the lease judges it by where the cursor is (<see cref="LastPointerOverMs"/>). When the kind
    /// cannot be told, <see cref="LastReachingInputMs"/>.
    /// </summary>
    long LastBeyondFrontInputMs => LastReachingInputMs;

    /// <summary>
    /// The last mouse input of the person (bare moves too) that Raw Input delivered while the cursor was over this
    /// window, a window inside it or one it owns: a pass over a window changes what it draws (a highlight, a fade, a
    /// tooltip) even when nothing is pressed. When it cannot be told, <see cref="LastForeignInputMs"/>.
    /// </summary>
    long LastPointerOverMs(nint window) => LastForeignInputMs;

    /// <summary>
    /// Where the person's last mouse input that Raw Input delivered left the cursor (physical pixels) and when: the
    /// place the lease gives the cursor back to when it went elsewhere after it (BAXY's jump to a click). Null when it
    /// cannot be told, or when an input the detector missed came after it (it may have moved the cursor).
    /// </summary>
    (long AtMs, int X, int Y)? LastPointerAt => null;

    /// <summary>
    /// Windows' last input when it is newer than every input the detector received (one still in flight, or one Raw
    /// Input never delivers), else 0. When nothing is told apart, 0.
    /// </summary>
    long UnexplainedInputMs => 0;

    /// <summary>The last input carrying BAXY's mark that reached the detector (0 when none, or not told apart).</summary>
    long LastOwnInputMs => 0;

    /// <summary>
    /// How many inputs carrying BAXY's mark reached the detector so far: Windows routed each one to its window before
    /// Raw Input delivered it (0 when not told apart).
    /// </summary>
    long OwnInputCount => 0;

    /// <summary>Whether a modifier key (Ctrl, Alt, Shift, Win) or a mouse button is held down now.</summary>
    bool HeldDown();

    /// <summary>Whether BAXY's own input is told apart; when not, only the pause before acting can be waited for.</summary>
    bool TellsOwnInput { get; }

    /// <summary>What watches the input: <c>raw_input</c>, or <c>last_input_info</c> when Raw Input could not start.</summary>
    string Source { get; }
}

/// <summary>
/// The pause detector of the Core process: a thread of its own with a message-only window registered for Raw Input
/// of the keyboard and the mouse with <c>RIDEV_INPUTSINK</c> (it gets the input while other windows are in front).
/// Raw Input is passive (nothing sits in the input path, so Windows never removes it for being slow) and every event
/// carries the <c>dwExtraInfo</c> its sender gave it (measured 2026-10-07 with ForegroundLeaseLiveCheck: a zero move
/// marked by BAXY left the person's last input unchanged, an unmarked one moved it, and the self-check missed
/// nothing), so no low-level hook is needed. Only a time is kept per event, never the key; of the mouse, only the
/// last point the person's own input left the cursor at (overwritten, never logged: where the cursor goes back to).
/// Self-check: Windows' own last-input time (<c>GetLastInputInfo</c>) must not be newer than everything the detector
/// saw; input it missed (for example the input of an elevated window) counts as the person's, so the pause is never
/// judged longer than it is.
/// </summary>
internal sealed unsafe partial class WindowsUserInputPause : IUserInputPause
{
    // An input Windows recorded that the detector has not seen after this long was missed by it.
    private const long DetectorLagMs = 200;
    private const long ToleranceMs = 30;

    private static readonly Lazy<WindowsUserInputPause> SharedInstance = new(() => new WindowsUserInputPause());
    private static WindowsUserInputPause? _watching;

    private long _lastForeign;
    private long _lastOwn;
    private long _missed;
    private long _lastFrontMoving;
    private long _lastReaching;
    private long _lastBeyondFront;
    private long _ownCount;
    private long _lastMissedAt;
    // The window the person works in and the processes their input reached (goal v3 ventana-misión, ronda 20 P2).
    private readonly PersonWindowBook _book;
    private long _lastOwnUndelivered;
    private readonly MissedInputCheck _selfCheck = new();
    private static int _helpersSending;

    // Where the person's cursor went (interrupcion-fantasma r2): the top-level window under it and when, sampled on the
    // detector's thread from the mouse records Raw Input delivers.
    private readonly Dictionary<nint, long> _hovered = [];
    private long _lastHoverSample;
    // The cursor at the person's last mouse input (molestia-ayudantes r2): replaced whole, read lock-free.
    private PointerSample? _pointer;
    private volatile bool _rawInput;

    private WindowsUserInputPause()
    {
        // What happened before the detector started is not known to be BAXY's: it counts as the person's.
        _lastForeign = LastInputMs();
        _lastFrontMoving = _lastForeign;
        _lastReaching = _lastForeign;
        // Ronda 20 P2 (t-drag-2): that input went to the window in front (keys go there), the window the person works
        // in until the detector sees otherwise. Without it the first look of every process came without the person's
        // window, and a mission with no application read and named the window the person was typing in.
        _book = PersonWindowBook.Seeded(GetForegroundWindow(), _lastForeign, RootOf, ProcessOf);
        // Not disposed: a thread that starts later than the wait still sets it.
        var ready = new ManualResetEventSlim();
        _watching = this;
        var thread = new Thread(() => Pump(ready)) { IsBackground = true, Name = "BAXY user input pause" };
        thread.Start();
        _ = ready.Wait(TimeSpan.FromSeconds(2));
    }

    internal static WindowsUserInputPause Shared => SharedInstance.Value;

    public bool TellsOwnInput => _rawInput;

    public string Source => _rawInput ? "raw_input" : "last_input_info";

    /// <summary>Inputs Windows recorded that Raw Input did not deliver (each one counted as the person's).</summary>
    internal long Missed => Interlocked.Read(ref _missed);

    public long LastForeignInputMs
    {
        get
        {
            long windows = LastInputMs();
            if (!_rawInput)
                return windows;
            long foreign = Interlocked.Read(ref _lastForeign);
            long reconciled;
            lock (_selfCheck)
            {
                reconciled = SelfCheck(
                    _selfCheck, _book, foreign, OwnSeen, windows, Environment.TickCount64,
                    Volatile.Read(ref _helpersSending) > 0, Front);
            }

            if (reconciled != foreign)
            {
                // v3 r22 revisión 3: input the detector missed is the person's and went to the window in front.
                Windows.WindowsPersonInputWitness.NoteReached(Front());
                _ = Interlocked.Increment(ref _missed);
                InterlockedMax(ref _lastForeign, reconciled);
                InterlockedMax(ref _lastMissedAt, reconciled);
            }

            return reconciled;
        }
    }

    public long LastFrontMovingInputMs
    {
        get
        {
            if (!_rawInput)
                return LastInputMs();
            // Reconciled first: an input the detector missed is of no known kind, and counts as one that moves the front.
            _ = LastForeignInputMs;
            return Math.Max(Interlocked.Read(ref _lastFrontMoving), Interlocked.Read(ref _lastMissedAt));
        }
    }

    public long LastReachingInputMs
    {
        get
        {
            if (!_rawInput)
                return LastInputMs();
            // Reconciled first: an input the detector missed is of no known kind, and counts as one that reaches.
            _ = LastForeignInputMs;
            return Math.Max(Interlocked.Read(ref _lastReaching), Interlocked.Read(ref _lastMissedAt));
        }
    }

    // Raw Input only: an input the detector missed is of no known kind; the lease judges it by where the cursor is
    // (IInputBurst.UserActed after the front was given back).
    public long LastBeyondFrontInputMs => _rawInput ? Interlocked.Read(ref _lastBeyondFront) : LastInputMs();

    public long LastPointerOverMs(nint window)
    {
        if (!_rawInput)
            return LastInputMs();
        if (window == 0)
            return 0;
        nint peer = VisibleControlSurface.FamilyPeer(window);
        long last = 0;
        lock (_hovered)
        {
            foreach ((nint root, long at) in _hovered)
            {
                if (at > last && VisibleControlSurface.IsOrOwnedByFamily(window, peer, root, RootOf, OwnerOf))
                    last = at;
            }
        }

        return last;
    }

    public (long AtMs, int X, int Y)? LastPointerAt
    {
        get
        {
            if (!_rawInput || Volatile.Read(ref _pointer) is not { } pointer)
                return null;
            // Reconciled first: an input the detector missed after it may have moved the cursor.
            _ = LastForeignInputMs;
            return Interlocked.Read(ref _lastMissedAt) > pointer.AtMs ? null : (pointer.AtMs, pointer.X, pointer.Y);
        }
    }

    private sealed record PointerSample(long AtMs, int X, int Y);

    public long UnexplainedInputMs
    {
        get
        {
            if (!_rawInput)
                return 0;
            long windows = LastInputMs();
            long seen = Math.Max(Interlocked.Read(ref _lastForeign), OwnSeen);
            return windows > seen + ToleranceMs ? windows : 0;
        }
    }

    // BAXY's own input: what Raw Input delivered with its mark, and what BAXY sent that Raw Input never delivers.
    private long OwnSeen => Math.Max(Interlocked.Read(ref _lastOwn), Interlocked.Read(ref _lastOwnUndelivered));

    /// <summary>
    /// Said right after BAXY's own <c>SendInput</c> of keys Raw Input never delivers, marked or not (Unicode
    /// characters, <c>KEYEVENTF_UNICODE</c>: measured 2026-10-08, each one moves <c>GetLastInputInfo</c> and none
    /// reaches Raw Input). Review of interrupcion-fantasma, bloqueante: without it the self-check took BAXY's own
    /// typing for the person's once it went on for 200 ms, and every text stopped at its 7th character as
    /// interrupted. Nothing before the detector starts.
    /// </summary>
    internal static void NoteOwnUndelivered()
    {
        if (_watching is { } watching)
            InterlockedMax(ref watching._lastOwnUndelivered, Environment.TickCount64);
    }

    /// <summary>
    /// While a helper process of BAXY runs (<see cref="LeasedInput.WatchHelperAsync"/>): it may send Unicode keys of its
    /// own, which Raw Input never delivers and this process cannot note one by one, so input missed across reads
    /// (<see cref="MissedInputCheck"/>) is not escalated meanwhile; the self-check of each read stays as it was.
    /// </summary>
    internal static IDisposable HelperSending()
    {
        _ = Interlocked.Increment(ref _helpersSending);
        return new HelperScope();
    }

    private sealed class HelperScope : IDisposable
    {
        private int _done;

        public void Dispose()
        {
            if (Interlocked.Exchange(ref _done, 1) == 0)
                _ = Interlocked.Decrement(ref _helpersSending);
        }
    }

    public long LastOwnInputMs => _rawInput ? Interlocked.Read(ref _lastOwn) : 0;

    public long OwnInputCount => _rawInput ? Interlocked.Read(ref _ownCount) : 0;

    /// <summary>
    /// Goal v3 ventana-misión: how long ago (ms) the person's last input that reaches a window's content went to this
    /// window (the root of the window in front when it came); null when their last such input went to another window,
    /// or when it cannot be told. Only the window and a time are kept, never the key or the position.
    /// </summary>
    internal long? PersonInputAgoMs(nint window)
    {
        if (!_rawInput || window == 0)
            return null;
        // Reconciled first: an input the detector missed went to the window in front.
        _ = LastForeignInputMs;
        return _book.AgoMs(_rawInput, window, Environment.TickCount64);
    }

    /// <summary>
    /// Ronda 20 P2: without Raw Input no window of the person is known (<see cref="PersonInputAgoMs"/> is null), only
    /// how long ago (ms) Windows' last input of the session came, whoever's and wherever it went; null with Raw Input.
    /// </summary>
    internal long? UnknownInputAgoMs => _rawInput ? null : Math.Max(0, Environment.TickCount64 - LastInputMs());

    /// <summary>
    /// Goal v3 ventana-misión (review, finding 1): how long ago (ms) the person's last input that reaches a window's
    /// content went to a window of one of <paramref name="processes"/> (the born window's process, the shell's: where
    /// a person opens, restores or starts a window); null when none did, or when it cannot be told.
    /// </summary>
    internal long? PersonInputToProcessesAgoMs(params uint[] processes) =>
        _book.ProcessesAgoMs(_rawInput, Environment.TickCount64, processes);

    /// <summary>
    /// The self-check of one read (<see cref="MissedInputCheck"/>), and where its answer says the person's input went:
    /// an input the detector missed is of no known kind and counts as one that reaches (<see cref="LastReachingInputMs"/>),
    /// so it went to the window in front then (<paramref name="front"/>), as the keys Raw Input never delivers do
    /// (VK_PACKET typing: ronda 20 P2, t-drag-2). BAXY's own input it was told of (<see cref="NoteOwnUndelivered"/>, in
    /// <paramref name="own"/>) is not missed, and marks no window.
    /// </summary>
    internal static long SelfCheck(
        MissedInputCheck check, PersonWindowBook book, long foreign, long own, long windows, long now, bool helperSending,
        Func<nint> front)
    {
        long reconciled = check.Reconcile(foreign, own, windows, now, helperSending);
        if (reconciled != foreign)
            book.Note(front(), reconciled);
        return reconciled;
    }

    /// <summary>
    /// Goal v3 ventana-misión, ronda 20 P2: the window the person works in (the root of the window in front when their
    /// last input that reaches a window's content came) and when, and when their input last reached a window of each
    /// process (bounded, the oldest forgotten). Only windows, processes and times, never the key or the position. Pure:
    /// the root and the process of a window are given.
    /// </summary>
    internal sealed class PersonWindowBook
    {
        internal const int ProcessesKept = 32;

        private readonly Func<nint, nint> _rootOf;
        private readonly Func<nint, uint> _processOf;
        private readonly System.Collections.Concurrent.ConcurrentDictionary<uint, long> _processAt = new();
        private readonly Lock _gate = new();
        private nint _window;
        private long _at;

        private PersonWindowBook(Func<nint, nint> rootOf, Func<nint, uint> processOf)
        {
            _rootOf = rootOf;
            _processOf = processOf;
        }

        /// <summary>
        /// Seeded when the detector starts (ronda 20 P2, t-drag-2): what came before it (Windows' last input,
        /// <paramref name="lastInput"/>) is the person's and went to the window in front (keys go there), the window they
        /// work in until the detector sees otherwise. Unseeded, the first look of every process came without it.
        /// </summary>
        internal static PersonWindowBook Seeded(nint front, long lastInput, Func<nint, nint> rootOf, Func<nint, uint> processOf)
        {
            var book = new PersonWindowBook(rootOf, processOf);
            book.Note(front, lastInput);
            return book;
        }

        /// <summary>
        /// The person's input came at <paramref name="at"/> with <paramref name="front"/> in front: the root of it is the
        /// window they work in (none when nothing was in front), and the process it reached is that root's, or
        /// <paramref name="reached"/>'s when told (a mouse button reaches the window under the pointer). An older time
        /// never replaces a newer one.
        /// </summary>
        internal void Note(nint front, long at, nint? reached = null)
        {
            nint window = front == 0 ? 0 : _rootOf(front) is var root and not 0 ? root : front;
            lock (_gate)
            {
                if (at < _at)
                    return;
                _window = window;
                _at = at;
            }

            NoteProcess(reached ?? window, at);
        }

        /// <summary>How long ago the person's last input went to <paramref name="window"/>; null when it went to
        /// another one, or when the detector cannot tell (<paramref name="tells"/> false: no Raw Input).</summary>
        internal long? AgoMs(bool tells, nint window, long now)
        {
            if (!tells || window == 0)
                return null;
            lock (_gate)
                return _window == window ? Math.Max(0, now - _at) : null;
        }

        internal long? ProcessesAgoMs(bool tells, long now, params uint[] processes)
        {
            if (!tells)
                return null;
            long latest = 0;
            foreach (uint process in processes)
            {
                if (process != 0 && _processAt.TryGetValue(process, out long at))
                    latest = Math.Max(latest, at);
            }

            return latest == 0 ? null : Math.Max(0, now - latest);
        }

        private void NoteProcess(nint reached, long at)
        {
            uint process = reached == 0 ? 0 : _processOf(reached);
            if (process == 0)
                return;
            if (_processAt.Count >= ProcessesKept && !_processAt.ContainsKey(process))
            {
                uint oldest = _processAt.MinBy(entry => entry.Value).Key;
                _ = _processAt.TryRemove(oldest, out _);
            }

            _processAt[process] = Math.Max(at, _processAt.TryGetValue(process, out long known) ? known : 0);
        }
    }

    /// <summary>
    /// Whether one Raw Input record (header and body) can reach a window's content: any keyboard record, or a mouse
    /// record with a button or the wheel (<c>RAWMOUSE.usButtonFlags</c> not zero). A bare move cannot. Only this answer
    /// is kept, never the key or the position.
    /// </summary>
    internal static bool ReachesContent(ReadOnlySpan<byte> record, int header)
    {
        if (record.Length < 4)
            return true;
        uint type = BinaryPrimitives.ReadUInt32LittleEndian(record);
        if (type != 0)
            return true;
        return record.Length < header + 6 || BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 4)..]) != 0;
    }

    /// <summary>
    /// v3 r22 revisión 3: the window one Raw Input record of the person reached (0 when it is BAXY's, carries no window,
    /// or cannot reach a window's content). Every record without BAXY's mark is the person's, injected or not (Synergy,
    /// remote desktops, on-screen keyboards, the live harness's simulated user): a key reaches the window in front
    /// (<paramref name="front"/>), a button or the wheel the window under the pointer (<paramref name="pointed"/>, the
    /// front when it is not known). Only the window is answered, never the key or the position.
    /// </summary>
    internal static nint PersonReachedWindow(ReadOnlySpan<byte> record, int header, nint front, nint pointed)
    {
        if (IsOwn(record, header) is not false || !ReachesContent(record, header))
            return 0;
        return BinaryPrimitives.ReadUInt32LittleEndian(record) == 0 && pointed != 0 ? pointed : front;
    }

    /// <summary>
    /// Whether one Raw Input record (header and body) can move the front: a mouse button going down
    /// (<c>RAWMOUSE.usButtonFlags</c>, 4 bytes into the mouse record) or Alt or a Windows key going down
    /// (<c>RAWKEYBOARD.Flags</c> and <c>VKey</c>, 2 and 6 bytes into the keyboard record). Only this answer is kept,
    /// never the key or the position.
    /// </summary>
    internal static bool MovesFront(ReadOnlySpan<byte> record, int header)
    {
        if (record.Length < 4)
            return false;
        uint type = BinaryPrimitives.ReadUInt32LittleEndian(record);
        if (type == 0)
        {
            if (record.Length < header + 6)
                return false;
            // RI_MOUSE_LEFT/RIGHT/MIDDLE/BUTTON_4/BUTTON_5 _DOWN.
            return (BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 4)..]) & 0x0155) != 0;
        }

        if (type != 1 || record.Length < header + 8)
            return false;
        bool down = (BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 2)..]) & 0x0001) == 0;
        ushort key = BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 6)..]);
        return down && key is 0x12 or 0xA4 or 0xA5 or 0x5B or 0x5C;
    }

    public bool HeldDown()
    {
        foreach (int key in HeldKeys)
        {
            if ((GetAsyncKeyState(key) & 0x8000) != 0)
                return true;
        }

        return false;
    }

    // Shift, Ctrl, Alt, both Win keys, and the five mouse buttons.
    private static readonly int[] HeldKeys = [0x10, 0x11, 0x12, 0x5B, 0x5C, 0x01, 0x02, 0x04, 0x05, 0x06];

    /// <summary>
    /// The self-check: the person's last input given what the detector saw (the person's, BAXY's) and Windows' own
    /// last-input time. An input Windows recorded that the detector has not seen once it had time to is the person's.
    /// </summary>
    internal static long Reconcile(long foreign, long own, long windows, long now) =>
        windows > Math.Max(foreign, own) + ToleranceMs && now - windows >= DetectorLagMs
            ? Math.Max(foreign, windows)
            : foreign;

    /// <summary>
    /// The self-check across reads (interrupcion-fantasma, r9 v3-38 and v3-59). <see cref="Reconcile(long, long, long, long)"/>
    /// alone waits until Windows' last input is <see cref="DetectorLagMs"/> old, so input Raw Input never delivers
    /// that keeps coming (keys sent as <c>VK_PACKET</c> characters, the way on-screen keyboards, remote-input tools
    /// and the live harness's simulated user type; keys another low-level hook swallows: measured 2026-10-08, each one
    /// moves <c>GetLastInputInfo</c> and none reaches Raw Input) was never older than that while it went on: the
    /// person typing at 8 keys a second read as a pause, BAXY clicked in the middle of it, and only once they stopped
    /// did their input appear, newer than the burst, which then stopped as interrupted. Here the first such input seen
    /// is remembered, and once it is that old without the detector having received it, it counts as the person's even
    /// while newer ones keep arriving.
    /// </summary>
    internal sealed class MissedInputCheck
    {
        // The oldest input Windows recorded that the detector had not received when it was first read (0: none).
        private long _pending;

        /// <param name="helperSending">A helper process of BAXY may be sending keys Raw Input never delivers
        /// (<see cref="HelperSending"/>): only the self-check of this read applies.</param>
        internal long Reconcile(long foreign, long own, long windows, long now, bool helperSending = false)
        {
            long seen = Math.Max(foreign, own);
            if (_pending != 0 && _pending <= seen + ToleranceMs)
                _pending = 0;
            long reconciled = WindowsUserInputPause.Reconcile(foreign, own, windows, now);
            if (reconciled != foreign || helperSending)
            {
                _pending = 0;
                return reconciled;
            }

            if (windows <= seen + ToleranceMs)
                return foreign;
            if (_pending == 0)
                _pending = windows;
            if (now - _pending < DetectorLagMs)
                return foreign;
            long missed = _pending;
            _pending = windows > missed + ToleranceMs ? windows : 0;
            return Math.Max(foreign, missed);
        }
    }

    /// <summary>
    /// Whether one Raw Input record (header and body, as <c>GetRawInputData</c> wrote it) is BAXY's own: true with
    /// BAXY's mark, false without it, null when it is neither a mouse nor a keyboard record.
    /// </summary>
    internal static bool? IsOwn(ReadOnlySpan<byte> record, int header)
    {
        if (record.Length < 4)
            return null;
        uint type = BinaryPrimitives.ReadUInt32LittleEndian(record);
        // RAWMOUSE.ulExtraInformation sits 20 bytes into the mouse record, RAWKEYBOARD.ExtraInformation 12 bytes
        // into the keyboard one.
        int offset = type switch
        {
            0 => header + 20,
            1 => header + 12,
            _ => -1,
        };
        if (offset < 0 || record.Length < offset + 4)
            return null;
        if (BaxyInputMark.Carries(BinaryPrimitives.ReadUInt32LittleEndian(record[offset..])))
            return true;
        return type == 1 && IsAutomationForegroundBid(record, header);
    }

    /// <summary>
    /// The key UIAutomationCore injects, unmarked, to win the foreground permission before a pattern method (Invoke,
    /// Select, Toggle, SetValue, SetFocus) when the person has just typed: VK 0xB9, a reserved code no keyboard sends,
    /// injected (<c>RAWINPUTHEADER.hDevice</c> null). The worker drops it at its source (BaxyUiaQuietInput); a helper
    /// script that calls a pattern in its own process (Spotify's, the messaging and Steam ones) cannot, and its key was
    /// taken for the person's and stopped the helper's own burst (t2-r4 c01-1, <c>input_user_interrupted</c> on one
    /// 1 ms input). It is nobody's typing: it counts with BAXY's own input, so the self-check against Windows' last
    /// input does not turn it into the person's either. The same code from a device stays the person's.
    /// </summary>
    internal static bool IsAutomationForegroundBid(ReadOnlySpan<byte> record, int header)
    {
        if (record.Length < header + 8 || header < 8 + IntPtr.Size)
            return false;
        bool injected = IntPtr.Size == 8
            ? BinaryPrimitives.ReadUInt64LittleEndian(record[8..]) == 0
            : BinaryPrimitives.ReadUInt32LittleEndian(record[8..]) == 0;
        return injected && BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 6)..]) == AutomationBidKey;
    }

    /// <summary>The virtual key of UIAutomationCore's foreground bid (reserved in the virtual-key table).</summary>
    internal const ushort AutomationBidKey = 0xB9;

    /// <summary>Windows' last input of the session, in <see cref="Environment.TickCount64"/> milliseconds.</summary>
    internal static long LastInputMs()
    {
        var info = new LastInputInfo { Size = (uint)sizeof(LastInputInfo) };
        long now = Environment.TickCount64;
        if (!GetLastInputInfo(ref info))
            return now;
        uint ago = unchecked((uint)Environment.TickCount - info.Time);
        return now - ago;
    }

    private void Pump(ManualResetEventSlim ready)
    {
        nint window = 0;
        try
        {
            nint instance = GetModuleHandleW(null);
            fixed (char* className = "BaxyUserInputPause")
            {
                var windowClass = new WindowClass
                {
                    Size = (uint)sizeof(WindowClass),
                    Procedure = &WindowProcedure,
                    Instance = instance,
                    ClassName = className,
                };
                _ = RegisterClassExW(ref windowClass);
                window = CreateWindowExW(0, className, null, 0, 0, 0, 0, 0, MessageOnlyParent, 0, instance, 0);
            }

            if (window != 0)
            {
                RawInputDevice* devices = stackalloc RawInputDevice[2];
                devices[0] = new RawInputDevice { UsagePage = 1, Usage = 2, Flags = InputSink, Target = window };
                devices[1] = new RawInputDevice { UsagePage = 1, Usage = 6, Flags = InputSink, Target = window };
                _rawInput = RegisterRawInputDevices(devices, 2, (uint)sizeof(RawInputDevice));
            }
        }
        finally
        {
            ready.Set();
        }

        if (!_rawInput)
            return;
        // Ronda 20 P2: the self-check across reads (MissedInputCheck) runs on its own every SelfCheckMs, so input Raw
        // Input never delivers (VK_PACKET typing) is told while it comes, with the window in front then, and not only
        // when something reads the detector (the first look of a mission had read it once, too early to count it).
        _ = SetTimer(window, 1, SelfCheckMs, 0);
        // The cursor and the window under it are sampled in physical pixels (NoteHover), the unit of the lease's.
        _ = SetThreadDpiAwarenessContext(-4);
        Message message;
        while (GetMessageW(&message, 0, 0, 0) > 0)
            _ = DispatchMessageW(&message);
    }

    [UnmanagedCallersOnly]
    private static nint WindowProcedure(nint window, uint message, nint wParam, nint lParam)
    {
        if (message == WmInput)
            _watching?.Observe(lParam);
        else if (message == WmTimer)
            _watching?.SelfCheckTick();
        return DefWindowProcW(window, message, wParam, lParam);
    }

    // Ronda 20 P2: the self-check of one read, on the detector's own timer (SelfCheckMs), with nobody reading.
    private void SelfCheckTick() => _ = LastForeignInputMs;

    private void Observe(nint handle)
    {
        int header = 8 + 2 * IntPtr.Size;
        byte* buffer = stackalloc byte[64];
        uint size = 64;
        if (GetRawInputData(handle, RidInput, buffer, ref size, (uint)header) is 0 or uint.MaxValue)
            return;
        var record = new ReadOnlySpan<byte>(buffer, (int)Math.Min(size, 64u));
        bool? own = IsOwn(record, header);
        if (own is null)
            return;
        long now = Environment.TickCount64;
        if (own.Value)
        {
            InterlockedMax(ref _lastOwn, now);
            _ = Interlocked.Increment(ref _ownCount);
            return;
        }

        InterlockedMax(ref _lastForeign, now);
        if (MovesFront(record, header))
            InterlockedMax(ref _lastFrontMoving, now);
        if (ReachesContent(record, header))
        {
            InterlockedMax(ref _lastReaching, now);
            // The window the person works in: where this input went (the root of the window in front). The process it
            // reached: a mouse button goes to the window under the pointer (a click on the taskbar or a folder reaches
            // them before the front changes), a key to the window in front.
            nint? reached = null;
            if (record.Length >= 4 && BinaryPrimitives.ReadUInt32LittleEndian(record) == 0 && GetCursorPos(out CursorPoint point))
                reached = WindowFromPoint(point) is var pointed and not 0 ? GetAncestor(pointed, 2) : 0;
            nint front = GetForegroundWindow();
            _book.Note(front, now, reached);
            // v3 r22 revisión 3: the window this input of the person reached, for the launch provenance's witness.
            Windows.WindowsPersonInputWitness.NoteReached(PersonReachedWindow(record, header, front, reached ?? 0));
        }

        bool beyond = ActsBeyondFront(record, header);
        if (beyond)
            InterlockedMax(ref _lastBeyondFront, now);
        if (BinaryPrimitives.ReadUInt32LittleEndian(record) == 0 && GetCursorPos(out CursorPoint cursor))
        {
            // Every mouse input of theirs: where it left the cursor (one BAXY moves it from afterwards goes back here).
            Volatile.Write(ref _pointer, new PointerSample(now, cursor.X, cursor.Y));
            NoteHover(now, beyond, cursor);
        }
    }

    // At most one sample of the window under the cursor every HoverSampleMs while the mouse moves (a pass over a window
    // lasts longer), and always on a button or the wheel. Only the top-level window under the cursor and the time are
    // kept.
    private void NoteHover(long now, bool pressed, CursorPoint point)
    {
        if (!pressed && now - _lastHoverSample < HoverSampleMs)
            return;
        _lastHoverSample = now;
        nint shown = WindowFromPoint(point);
        if (shown == 0)
            return;
        nint root = RootOf(shown);
        lock (_hovered)
        {
            _hovered[root == 0 ? shown : root] = now;
            if (_hovered.Count > 64)
            {
                foreach (nint old in _hovered.Where(entry => now - entry.Value > HoverKeptMs).Select(entry => entry.Key).ToList())
                    _ = _hovered.Remove(old);
            }
        }
    }

    private const long HoverSampleMs = 8;
    private const long HoverKeptMs = 60_000;

    private static nint RootOf(nint window) => GetAncestor(window, 2);

    private static uint ProcessOf(nint window) =>
        GetWindowThreadProcessId(window, out uint process) == 0 ? 0 : process;

    private static nint Front() => GetForegroundWindow();

    private static nint OwnerOf(nint window) => GetWindow(window, 4);

    /// <summary>
    /// Whether one Raw Input record (header and body) can act on a window other than the one in front: a mouse record
    /// with a button or the wheel (<c>RAWMOUSE.usButtonFlags</c> not zero), Alt or a Windows key going down, or a key
    /// the shell routes past the front going down (<c>VK_BROWSER_BACK</c> 0xA6 to <c>VK_LAUNCH_APP2</c> 0xB7: browser,
    /// volume, media and launch keys). Only this answer is kept, never the key or the position.
    /// </summary>
    internal static bool ActsBeyondFront(ReadOnlySpan<byte> record, int header)
    {
        if (record.Length < 4)
            return true;
        uint type = BinaryPrimitives.ReadUInt32LittleEndian(record);
        if (type == 0)
            return record.Length < header + 6 || BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 4)..]) != 0;
        if (type != 1 || record.Length < header + 8)
            return true;
        bool down = (BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 2)..]) & 0x0001) == 0;
        ushort key = BinaryPrimitives.ReadUInt16LittleEndian(record[(header + 6)..]);
        return down && (key is 0x12 or 0xA4 or 0xA5 or 0x5B or 0x5C || key is >= 0xA6 and <= 0xB7);
    }

    private static void InterlockedMax(ref long target, long value)
    {
        long current = Interlocked.Read(ref target);
        while (value > current)
        {
            long seen = Interlocked.CompareExchange(ref target, value, current);
            if (seen == current)
                return;
            current = seen;
        }
    }

    private const uint WmInput = 0x00FF;
    private const uint WmTimer = 0x0113;
    internal const uint SelfCheckMs = 100;
    private const uint RidInput = 0x10000003;
    private const uint InputSink = 0x00000100;
    private static readonly nint MessageOnlyParent = -3;

    [StructLayout(LayoutKind.Sequential)]
    private struct CursorPoint
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct LastInputInfo
    {
        public uint Size;
        public uint Time;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct RawInputDevice
    {
        public ushort UsagePage;
        public ushort Usage;
        public uint Flags;
        public nint Target;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WindowClass
    {
        public uint Size;
        public uint Style;
        public delegate* unmanaged<nint, uint, nint, nint, nint> Procedure;
        public int ClassExtra;
        public int WindowExtra;
        public nint Instance;
        public nint Icon;
        public nint Cursor;
        public nint Background;
        public char* MenuName;
        public char* ClassName;
        public nint SmallIcon;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Message
    {
        public nint Window;
        public uint Id;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
        public uint Private;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetLastInputInfo(ref LastInputInfo info);

    [LibraryImport("user32.dll")]
    private static partial short GetAsyncKeyState(int key);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetCursorPos(out CursorPoint point);

    [LibraryImport("user32.dll")]
    private static partial nint WindowFromPoint(CursorPoint point);

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint window, uint command);

    [LibraryImport("user32.dll")]
    private static partial nint SetThreadDpiAwarenessContext(nint context);

    [LibraryImport("user32.dll")]
    private static partial nuint SetTimer(nint window, nuint id, uint elapse, nint timerProcedure);

    [LibraryImport("kernel32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial nint GetModuleHandleW(string? name);

    [LibraryImport("user32.dll")]
    private static partial ushort RegisterClassExW(ref WindowClass windowClass);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial nint CreateWindowExW(
        uint extendedStyle, char* className, string? title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool RegisterRawInputDevices(RawInputDevice* devices, uint count, uint size);

    [LibraryImport("user32.dll")]
    private static partial uint GetRawInputData(nint handle, uint command, byte* data, ref uint size, uint headerSize);

    [LibraryImport("user32.dll")]
    private static partial int GetMessageW(Message* message, nint window, uint first, uint last);

    [LibraryImport("user32.dll")]
    private static partial nint DispatchMessageW(Message* message);

    [LibraryImport("user32.dll")]
    private static partial nint DefWindowProcW(nint window, uint message, nint wParam, nint lParam);
}
