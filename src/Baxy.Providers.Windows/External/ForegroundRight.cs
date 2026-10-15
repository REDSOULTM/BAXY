using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Handing the front back to a window from BAXY's process, verified (cu-v3-foco-segunda, v3 point 0). Windows lets a
/// background process set the foreground only while it holds the right (it received the last input, or it was started
/// by the process in front and has not used that yet). Measured live with three packaged applications opened one after
/// another in one process: the first hand-back held (the right a process starts with), the next ones were refused
/// (<c>SetForegroundWindow</c> false with the input attached to the thread in front, error 0), and the opened window
/// kept the front. The right is won the way the UIA worker wins it (BaxyFrontKeeper.Bid in DesktopUiaWorker.ps1): a
/// hotkey of this thread on a virtual key no keyboard has, registered with every modifier combination, and one press
/// of it carrying BAXY's mark. The system takes the press as the hotkey (it never reaches the window in front, and the
/// pointer never moves) and posts WM_HOTKEY to this thread, which then holds the right. Each try is read back, and the
/// tries are bounded.
/// </summary>
internal static partial class ForegroundRight
{
    // The worker's list (BaxyFrontKeeper.BidKeys): unassigned and reserved codes. The worker registers the first free
    // one for its life; this thread takes the first one free at the moment, and only while it hands the front back.
    internal static readonly ushort[] BidKeys = [0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F, 0x88, 0x89, 0x8A, 0x8B];

    // Ids of the worker's are 0x4258.. in its own thread; these are this thread's.
    private const int BidId = 0x4268;

    // Tries of one hand-back, and the pause between them (the opened application may still be activating itself).
    internal const int Attempts = 3;
    internal const int PauseMs = 60;
    internal const int BidBudgetMs = 200;

    /// <summary>What one hand-back did: whether the window holds the front at the end, and the bids it took.</summary>
    internal readonly record struct Outcome(bool Held, int Tries, int Bids);

    /// <summary>
    /// The rule of a hand-back, over its steps: set the front and read it back; when it did not hold, bid for the right
    /// and set it again; up to <paramref name="attempts"/> tries with a pause between them. A bid that is not answered
    /// is not repeated within the try.
    /// </summary>
    internal static Outcome Give(Action set, Func<bool> holds, Func<bool> bid, Action pause, int attempts = Attempts)
    {
        int bids = 0;
        for (int attempt = 1; attempt <= attempts; attempt++)
        {
            if (attempt > 1)
                pause();
            set();
            if (holds())
                return new Outcome(true, attempt, bids);
            bids++;
            if (bid())
            {
                set();
                if (holds())
                    return new Outcome(true, attempt, bids);
            }
        }

        return new Outcome(false, attempts, bids);
    }

    /// <summary>
    /// Hands the front to <paramref name="window"/> on the calling thread; whether it (or a window it owns) holds the
    /// front afterwards. Nothing is done for a window that is gone.
    /// </summary>
    internal static Outcome Give(nint window)
    {
        if (window == 0 || !IsWindow(window))
            return new Outcome(false, 0, 0);
        ushort key = 0;
        try
        {
            return Give(
                () => SetFront(window),
                () => VisibleControlSurface.ForegroundIsOrOwnedBy(window),
                () => Bid(ref key),
                () => Thread.Sleep(PauseMs));
        }
        finally
        {
            if (key != 0)
            {
                for (int modifiers = 0; modifiers < 16; modifiers++)
                    _ = UnregisterHotKey(0, BidId + modifiers);
            }
        }
    }

    // SetForegroundWindow attached to the thread that holds the front (enough while this process has the right).
    private static void SetFront(nint window)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = foreground == 0 ? 0 : GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0
            && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            _ = SetForegroundWindow(window);
        }
        finally
        {
            if (attached)
                _ = AttachThreadInput(currentThread, foregroundThread, false);
        }
    }

    // One marked press of this thread's hotkey (registered on first need) and the wait for its WM_HOTKEY: true once it
    // arrived within the budget.
    private static bool Bid(ref ushort key)
    {
        if (key == 0)
        {
            foreach (ushort candidate in BidKeys)
            {
                if (!RegisterHotKey(0, BidId, 0, candidate))
                    continue;
                // Every modifier combination too: a modifier the person holds never lets the press through.
                for (uint modifiers = 1; modifiers < 16; modifiers++)
                    _ = RegisterHotKey(0, BidId + (int)modifiers, modifiers, candidate);
                key = candidate;
                break;
            }

            if (key == 0)
                return false;
        }

        while (PeekMessage(out _, -1, WmHotKey, WmHotKey, 1))
        {
        }

        Span<Input> press = [Key(key, release: false), Key(key, release: true)];
        if (SendInput(2, press, Marshal.SizeOf<Input>()) != 2)
            return false;
        long started = Environment.TickCount64;
        while (true)
        {
            while (PeekMessage(out Message message, -1, WmHotKey, WmHotKey, 1))
            {
                long id = message.WParam;
                if (id >= BidId && id < BidId + 16)
                    return true;
            }

            long left = BidBudgetMs - (Environment.TickCount64 - started);
            if (left <= 0)
                return false;
            _ = MsgWaitForMultipleObjects(0, 0, false, (uint)left, QsHotKey);
        }
    }

    private static Input Key(ushort key, bool release) => new()
    {
        Type = 1,
        Keyboard = new KeyboardInput
        {
            VirtualKey = key,
            Flags = release ? 0x0002u : 0u,
            // BaxyInputMark: the pause detector and the live harness know it is BAXY's.
            ExtraInfo = (nint)BaxyInputMark.Value,
        },
    };

    private const uint WmHotKey = 0x0312;
    private const uint QsHotKey = 0x0080;

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    // INPUT on x64: the type, then the union (32 bytes, the size of MOUSEINPUT), 40 bytes in all.
    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct Input
    {
        [FieldOffset(0)]
        public uint Type;

        [FieldOffset(8)]
        public KeyboardInput Keyboard;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Message
    {
        public nint Window;
        public uint Value;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
    }

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(uint attach, uint attachTo, [MarshalAs(UnmanagedType.Bool)] bool doAttach);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool RegisterHotKey(nint window, int id, uint modifiers, uint key);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool UnregisterHotKey(nint window, int id);

    [LibraryImport("user32.dll", EntryPoint = "PeekMessageW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PeekMessage(out Message message, nint window, uint first, uint last, uint remove);

    [LibraryImport("user32.dll")]
    private static partial uint MsgWaitForMultipleObjects(uint count, nint handles, [MarshalAs(UnmanagedType.Bool)] bool waitAll, uint milliseconds, uint wakeMask);

    [LibraryImport("user32.dll")]
    private static partial uint SendInput(uint count, Span<Input> inputs, int size);
}
