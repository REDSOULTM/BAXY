using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The keyboard of the window in front, inside this process. Computer use measured
/// about 0.65 s per key while every <c>input.key.press</c> and <c>input.text.type</c>
/// started a PowerShell and compiled its SendInput declarations; the same SendInput
/// call made here costs well under a millisecond. The adapter decides what is sent
/// and builds the receipt; this seam only reads the foreground and sends.
/// </summary>
internal interface IDesktopKeyboard
{
    /// <summary>The window in front (0 when nobody holds the foreground), its process and title.</summary>
    DesktopForeground Foreground();

    /// <summary>The program a view names this window by: a packaged app's own for its frame (never ApplicationFrameHost),
    /// else its process's name; empty when it cannot be read.</summary>
    string ProcessName(nint window);

    /// <summary>
    /// Presses the keys in order, each held the keyboard's pace while <paramref name="keepGoing"/> holds before it, and
    /// releases the ones pressed in reverse; the events Windows accepted, fewer than two per key when it stopped.
    /// </summary>
    uint PressChord(IReadOnlyList<ushort> virtualKeys, Func<bool> keepGoing);

    /// <summary>
    /// Types each UTF-16 unit as a Unicode key down and up while <paramref name="keepGoing"/> holds before each one
    /// (the request is not cancelled and the window that takes the keys is still in front); the events Windows
    /// accepted, fewer than two per unit when it stopped.
    /// </summary>
    uint TypeText(string text, Func<bool> keepGoing);

    /// <summary>Whether this window, a window inside it or a window it owns holds the foreground.</summary>
    bool Holds(nint window);

    /// <summary>
    /// Brings this window to the front inside a burst of the foreground lease (<see cref="IForegroundLease"/>): after
    /// a pause of the person, with what was in front saved. Keys go only while the burst may act, and the burst is
    /// restored once they are sent.
    /// </summary>
    ValueTask<IInputBurst> FrontAsync(nint window, CancellationToken cancellationToken);

    /// <summary>
    /// Hands the front back to a window that had it (the person's) after something of the mission took it: nothing is
    /// taken, so no lease and no pause; whether that window holds the front afterwards.
    /// </summary>
    bool GiveFront(nint window);

    /// <summary>The size of one native INPUT record (40 on x64), checked before anything is sent.</summary>
    int InputSize { get; }

    int LastError();

    /// <summary>Lets the window in front take the keys before its post-read.</summary>
    ValueTask SettleAsync(CancellationToken cancellationToken);

    /// <summary>The clipboard's sequence number (GetClipboardSequenceNumber), which every write moves on; 0: not
    /// known.</summary>
    uint ClipboardSequence() => 0;

    /// <summary>Ajuste c3 (E017): what a shortcut can visibly change of this window (<see cref="WindowWitness"/>); null:
    /// not read.</summary>
    WindowWitness? Witness(nint window) => null;
}

internal readonly record struct DesktopForeground(nint Window, int ProcessId, string Title);

internal sealed partial class WindowsDesktopKeyboard : IDesktopKeyboard
{
    public uint ClipboardSequence() => GetClipboardSequenceNumber();

    public WindowWitness? Witness(nint window) => WindowWitness.Read(window);

    [LibraryImport("user32.dll")]
    private static partial uint GetClipboardSequenceNumber();

    private const uint InputKeyboard = 1;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;
    private const int KeyPace = 35;

    // What the PowerShell path waited before reading the foreground again.
    private static readonly TimeSpan Settle = TimeSpan.FromMilliseconds(40);

    // The Core's lease (and its pause detector) starts with the first mission key, not with the adapter.
    private readonly IForegroundLease? _lease;

    internal WindowsDesktopKeyboard(IForegroundLease? lease = null)
    {
        _lease = lease;
    }

    public int InputSize => Marshal.SizeOf<Input>();

    public DesktopForeground Foreground()
    {
        nint window = GetForegroundWindow();
        if (window == 0)
            return default;
        _ = GetWindowThreadProcessId(window, out uint processId);
        return new DesktopForeground(window, unchecked((int)processId), VisibleControlSurface.WindowTitle(window));
    }

    public string ProcessName(nint window) => VisibleControlSurface.ViewProcess(window).ProcessName;

    public uint PressChord(IReadOnlyList<ushort> virtualKeys, Func<bool> keepGoing) =>
        HoldChord(virtualKeys, keepGoing, (key, up) => Send([Key(key, 0, up ? KeyUp : 0)]), () => Thread.Sleep(KeyPace));

    /// <summary>
    /// Ajuste c3 (e2e E017, «… y guárdalo como lista.txt»): Ctrl+S sent as one SendInput of its four events reached
    /// Windows 11 Notepad 16 times of 16 on the PC and the notebook (receipt «delivered»), and no «Guardar como» opened
    /// in any of them, nor did an «s» appear in the text; on the VM's classic Notepad the same receipt opened «Save As»
    /// (1 of 1). That editor reads each key when it gets to it (measured 2026-10-07, see <see cref="TypeText"/>: keys
    /// faster than it takes them come out wrong, and virtual keys lose their Shift): by then every key of the chord was
    /// already up. So a chord is held as a person holds it: each key goes down in order with the keyboard's pace after
    /// it, the last one still down, with the ones before it, when the window reads it; then they go up in reverse.
    /// Before each key goes down <paramref name="keepGoing"/> must still hold (the window in front, the person not
    /// acting), as before each typed character: otherwise no other key goes down. Whatever went down always goes up.
    /// </summary>
    internal static uint HoldChord(
        IReadOnlyList<ushort> virtualKeys, Func<bool> keepGoing, Func<ushort, bool, uint> send, Action pause)
    {
        uint accepted = 0;
        var down = new List<ushort>(virtualKeys.Count);
        try
        {
            foreach (ushort key in virtualKeys)
            {
                if (!keepGoing())
                    break;
                accepted += send(key, false);
                down.Add(key);
                pause();
            }
        }
        finally
        {
            for (int index = down.Count - 1; index >= 0; index--)
                accepted += send(down[index], true);
        }

        return accepted;
    }

    public uint TypeText(string text, Func<bool> keepGoing)
    {
        // One character at a time, at a fast typist's pace. Measured on Windows 11 Notepad (2026-10-07, «Querido Ron:
        // mañana a las 5, llevá pan…»): its editor reads each key when it gets to it, so keys sent faster than it takes
        // them come out as the last one repeated («lista: pan» → «lista:nnnn» at 3 ms, «lista:ppan» at 20 ms), and real
        // virtual keys lose their Shift the same way; 25 ms and slower typed every run whole.
        // Safety review 2026-10-07: 4096 characters at this pace take about 143 s, well past the App's step timeout,
        // and a window that takes the front meanwhile would get the rest. Before each character the request must
        // still stand and the window must still be in front; otherwise typing stops there.
        uint accepted = 0;
        for (int index = 0; index < text.Length; index++)
        {
            if (!keepGoing())
                break;
            accepted += Send([Key(0, text[index], Unicode), Key(0, text[index], Unicode | KeyUp)]);
            // Raw Input never delivers a Unicode key: the pause detector is told it was BAXY's.
            WindowsUserInputPause.NoteOwnUndelivered();
            Thread.Sleep(KeyPace);
        }

        return accepted;
    }

    // Its own pop-up or dialog (a window it owns) still takes the keys for it; another top-level window of the same
    // process does not (review of fable/cu-v3-pausa: a second folder window, the shell's taskbar or another browser
    // window is the person's, and the keys of the mission must never land there).
    public bool Holds(nint window) => VisibleControlSurface.ForegroundIsOrOwnedBy(window);

    public ValueTask<IInputBurst> FrontAsync(nint window, CancellationToken cancellationToken) =>
        (_lease ?? ForegroundLease.Shared).AcquireAsync(window, cancellationToken);

    public bool GiveFront(nint window)
    {
        WindowsLeaseDesktop.Instance.GiveFront(window);
        return GetForegroundWindow() == window;
    }

    public int LastError() => Marshal.GetLastPInvokeError();

    public ValueTask SettleAsync(CancellationToken cancellationToken) =>
        new(Task.Delay(Settle, cancellationToken));

    private uint Send(Input[] inputs) =>
        inputs.Length == 0 ? 0 : SendInput(unchecked((uint)inputs.Length), inputs, InputSize);

    private static Input Key(ushort virtualKey, ushort scanCode, uint flags) => new()
    {
        Type = InputKeyboard,
        Data = new InputUnion
        {
            Keyboard = new KeyboardInput
            {
                VirtualKey = virtualKey,
                ScanCode = scanCode,
                Flags = flags,
                ExtraInfo = BaxyInputMark.Value,
            },
        },
    };

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public InputUnion Data;
    }

    // The union carries every member so the record has the native size (40 bytes on x64); a keyboard-only union is
    // shorter and SendInput refuses it.
    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)] public KeyboardInput Keyboard;
        [FieldOffset(0)] public MouseInput Mouse;
        [FieldOffset(0)] public HardwareInput Hardware;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        public int X;
        public int Y;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HardwareInput
    {
        public uint Message;
        public ushort ParameterLow;
        public ushort ParameterHigh;
    }

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial uint SendInput(uint count, [In] Input[] inputs, int size);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);
}
